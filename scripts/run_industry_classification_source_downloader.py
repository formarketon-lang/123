
"""Collect official NSE classification and CM-UDiFF evidence.

This script downloads source material only.
It never infers or approves company-level sector mappings.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from data.providers.nse_universe import fetch_nse_equity_universe
from data.providers.nifty_constituents import fetch_sector_constituents


CLASSIFICATION_PAGE = (
    "https://www.niftyindices.com/resources/industry-classification"
)

UDIFF_FORMAT_PAGE = (
    "https://www.nseindia.com/static/resources/forms-formats-members"
)

NSE_REPORTS_PAGE = "https://www.nseindia.com/all-reports"

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "nse"
    / "industry_classification_sources"
)

REPORT_DIR = (
    PROJECT_ROOT
    / "reports"
    / "industry_classification"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/pdf,application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet,application/zip,*/*"
    ),
    "Referer": "https://www.nseindia.com/",
}


CLASSIFICATION_FALLBACKS = {
    "structure": (
        "https://www.niftyindices.com/docs/default-source/"
        "default-document-library/industry-classification/"
        "nse-indices_industry-classification-structure-2023-07.pdf"
        "?sfvrsn=c89dd39_1"
    ),
    "guidelines": (
        "https://www.niftyindices.com/docs/default-source/"
        "default-document-library/industry-classification/"
        "nse-indices_industry-classification-guideline-2023-07.pdf"
        "?sfvrsn=76449434_2"
    ),
}


class AnchorParser(HTMLParser):
    """Extract links and their visible anchor text."""

    def __init__(self):
        super().__init__()
        self.links = []
        self.href = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self.href = dict(attrs).get("href")
            self.text = []

    def handle_data(self, data):
        if self.href is not None:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.href is not None:
            self.links.append({
                "href": self.href,
                "text": " ".join(" ".join(self.text).split()),
            })
            self.href = None
            self.text = []


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def extract_links(html: str, base_url: str) -> list[dict]:
    parser = AnchorParser()
    parser.feed(html)

    return [
        {
            "url": urljoin(base_url, item["href"]),
            "text": item["text"],
        }
        for item in parser.links
        if item["href"]
    ]


def find_link(
    links: list[dict],
    keywords: tuple[str, ...],
) -> str | None:
    """Find a link only when its visible label matches the requested asset."""

    for item in links:
        label = item["text"].lower()

        if all(word.lower() in label for word in keywords):
            return item["url"]

    return None


def download_bytes(
    session: requests.Session,
    url: str,
    timeout: int = 60,
) -> bytes:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()

    content = response.content

    if not content:
        raise ValueError(f"Empty download: {url}")

    return content


def save_asset(
    session: requests.Session,
    url: str,
    filename: str,
    expected_type: str,
) -> dict:
    """Download and validate a source file before saving it."""

    content = download_bytes(session, url)

    if expected_type == "pdf":
        valid = content.startswith(b"%PDF")

    elif expected_type == "xlsx":
        valid = content.startswith(b"PK")

    elif expected_type == "zip":
        valid = content.startswith(b"PK")

    else:
        raise ValueError(f"Unsupported file type: {expected_type}")

    if not valid:
        raise ValueError(
            f"Downloaded content failed {expected_type.upper()} validation: "
            f"{url}"
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    path = OUTPUT_DIR / filename
    path.write_bytes(content)

    return {
        "status": "DOWNLOADED",
        "url": url,
        "path": str(path.relative_to(PROJECT_ROOT)),
        "size_bytes": len(content),
        "sha256": sha256_bytes(content),
        "file_type": expected_type,
    }


def save_dataframe(frame: pd.DataFrame, filename: str) -> dict:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ValueError(f"Empty dataset: {filename}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    path = OUTPUT_DIR / filename
    frame.to_csv(path, index=False, encoding="utf-8-sig")

    content = path.read_bytes()

    return {
        "status": "DOWNLOADED",
        "path": str(path.relative_to(PROJECT_ROOT)),
        "rows": int(len(frame)),
        "columns": list(frame.columns),
        "size_bytes": len(content),
        "sha256": sha256_bytes(content),
    }


def run_downloader() -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(HEADERS)

    report = {
        "project": "TradeLab Pro",
        "audit_type": "NSE Official Classification and UDiFF Evidence",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {},
        "files": {},
        "company_mapping": {
            "status": "PENDING",
            "verified_company_mappings": 0,
            "sector_mapping_enabled": False,
            "note": (
                "Downloading official evidence does not approve "
                "company-level sector mappings."
            ),
        },
    }

    # ---------------------------------------------------------
    # 1. NSE Indices classification source page
    # ---------------------------------------------------------

    classification_response = session.get(
        CLASSIFICATION_PAGE,
        timeout=60,
    )
    classification_response.raise_for_status()

    classification_html = classification_response.text

    classification_links = extract_links(
        classification_html,
        CLASSIFICATION_PAGE,
    )

    classification_page_path = (
        OUTPUT_DIR / "nse_industry_classification_source.html"
    )

    classification_page_path.write_text(
        classification_html,
        encoding="utf-8",
    )

    report["files"]["classification_source_page"] = {
        "status": "DOWNLOADED",
        "url": CLASSIFICATION_PAGE,
        "path": str(
            classification_page_path.relative_to(PROJECT_ROOT)
        ),
        "sha256": sha256_bytes(
            classification_page_path.read_bytes()
        ),
    }

    # ---------------------------------------------------------
    # 2. Official classification PDFs
    # ---------------------------------------------------------

    for name, fallback_url in CLASSIFICATION_FALLBACKS.items():
        discovered = find_link(
            classification_links,
            ("industry classification", name),
        )

        url = discovered or fallback_url

        try:
            report["files"][f"classification_{name}"] = save_asset(
                session,
                url,
                f"nse_industry_classification_{name}.pdf",
                "pdf",
            )
        except Exception as exc:
            report["files"][f"classification_{name}"] = {
                "status": "FAILED",
                "url": url,
                "error": f"{type(exc).__name__}: {exc}",
            }

    # ---------------------------------------------------------
    # 3. NSE UDiFF Catalogue Version 4.0
    # ---------------------------------------------------------

    try:
        format_response = session.get(
            UDIFF_FORMAT_PAGE,
            timeout=60,
        )
        format_response.raise_for_status()

        format_html = format_response.text

        format_links = extract_links(
            format_html,
            UDIFF_FORMAT_PAGE,
        )

        report["files"]["udiff_catalogue_page"] = {
            "status": "DOWNLOADED",
            "url": UDIFF_FORMAT_PAGE,
            "sha256": sha256_bytes(
                format_html.encode("utf-8")
            ),
        }

        catalogue_url = find_link(
            format_links,
            ("version 4.0",),
        )

        if catalogue_url is None:
            catalogue_url = find_link(
                format_links,
                ("udiff catalogue",),
            )

        if catalogue_url is None:
            raise ValueError(
                "Official UDiFF Catalogue Version 4.0 link "
                "was not discovered."
            )

        report["files"]["udiff_catalogue_v4"] = save_asset(
            session,
            catalogue_url,
            "nse_udiff_catalogue_v4",
            "xlsx",
        )

    except Exception as exc:
        report["files"]["udiff_catalogue_v4"] = {
            "status": "FAILED",
            "error": f"{type(exc).__name__}: {exc}",
        }

    # ---------------------------------------------------------
    # 4. NSE Daily Reports page: README and CM sample ZIP
    # ---------------------------------------------------------

    try:
        reports_response = session.get(
            NSE_REPORTS_PAGE,
            timeout=60,
        )
        reports_response.raise_for_status()

        reports_html = reports_response.text

        reports_links = extract_links(
            reports_html,
            NSE_REPORTS_PAGE,
        )

        report["files"]["nse_daily_reports_page"] = {
            "status": "DOWNLOADED",
            "url": NSE_REPORTS_PAGE,
            "sha256": sha256_bytes(
                reports_html.encode("utf-8")
            ),
        }

        readme_url = find_link(
            reports_links,
            ("new bhavcopy format readme",),
        )

        if readme_url is None:
            readme_url = find_link(
                reports_links,
                ("readme.xlsx",),
            )

        if readme_url is None:
            raise ValueError(
                "NSE Bhavcopy Format README link not found."
            )

        report["files"]["udiff_readme"] = save_asset(
            session,
            readme_url,
            "nse_new_bhavcopy_format_readme.xlsx",
            "xlsx",
        )

        sample_url = find_link(
            reports_links,
            ("cm-udiff common bhavcopy final",),
        )

        if sample_url is None:
            raise ValueError(
                "NSE CM-UDiFF Common Bhavcopy sample link not found."
            )

        report["files"]["cm_udiff_sample"] = save_asset(
            session,
            sample_url,
            "nse_cm_udiff_daily_sample.zip",
            "zip",
        )

    except Exception as exc:
        report["files"]["nse_udiff_daily_evidence"] = {
            "status": "FAILED",
            "error": f"{type(exc).__name__}: {exc}",
        }

    # ---------------------------------------------------------
    # 5. NSE MII equity universe
    # ---------------------------------------------------------

    try:
        universe = fetch_nse_equity_universe(
            session=session,
            lookback_days=7,
        )

        report["files"]["nse_equity_universe"] = save_dataframe(
            universe,
            "nse_mii_equity_universe.csv",
        )

        if "Source" in universe.columns:
            report["files"]["nse_equity_universe"][
                "source_labels"
            ] = (
                universe["Source"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )

    except Exception as exc:
        report["files"]["nse_equity_universe"] = {
            "status": "FAILED",
            "error": f"{type(exc).__name__}: {exc}",
        }

    # ---------------------------------------------------------
    # 6. Official Nifty FMCG constituents
    # ---------------------------------------------------------

    try:
        fmcg = fetch_sector_constituents(
            "FMCG",
            session=session,
            deduplicate=False,
        )

        report["files"]["nifty_fmcg_constituents"] = save_dataframe(
            fmcg,
            "nifty_fmcg_official_constituents.csv",
        )

        report["files"]["nifty_fmcg_constituents"][
            "classification_role"
        ] = "SUPPORTING_INDEX_CONSTITUENTS_ONLY"

    except Exception as exc:
        report["files"]["nifty_fmcg_constituents"] = {
            "status": "FAILED",
            "error": f"{type(exc).__name__}: {exc}",
        }

    # ---------------------------------------------------------
    # 7. Evidence summary. Never approve mapping automatically.
    # ---------------------------------------------------------

    required_assets = [
        "classification_guidelines",
        "udiff_catalogue_v4",
        "udiff_readme",
        "cm_udiff_sample",
    ]

    required_assets_ok = all(
        report["files"].get(name, {}).get("status") == "DOWNLOADED"
        for name in required_assets
    )

    downloaded = sum(
        item.get("status") == "DOWNLOADED"
        for item in report["files"].values()
    )

    failed = sum(
        item.get("status") == "FAILED"
        for item in report["files"].values()
    )

    report["summary"] = {
        "downloaded_sources": int(downloaded),
        "failed_sources": int(failed),
        "required_udiff_evidence_complete": required_assets_ok,
        "company_mapping_status": "PENDING",
        "udiff_schema_mapping_status": "UNVERIFIED",
        "sector_mapping_enabled": False,
        "overall_status": (
            "PASS" if required_assets_ok else "REVIEW"
        ),
    }

    report_path = (
        REPORT_DIR
        / "nse_official_classification_source_audit.json"
    )

    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(report["summary"], indent=2))
    print(f"Full evidence report: {report_path}")

    return report


if __name__ == "__main__":
    run_downloader()
