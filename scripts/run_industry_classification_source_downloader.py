"""Download official NSE Indices classification source material.

This downloader collects source documents and supporting NSE data.
It does NOT invent or infer company-level industry classifications.
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


SOURCE_PAGE = (
    "https://www.niftyindices.com/resources/industry-classification"
)

SOURCE_FILES = {
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
        "text/html,application/pdf,text/csv,"
        "application/octet-stream,*/*"
    ),
    "Referer": "https://www.niftyindices.com/",
}


class AnchorParser(HTMLParser):
    """Extract anchor text and href values from an HTML page."""

    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return

        self._href = dict(attrs).get("href")
        self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() != "a" or self._href is None:
            return

        self.links.append({
            "href": self._href,
            "text": " ".join(" ".join(self._text).split()),
        })

        self._href = None
        self._text = []


def sha256_bytes(content: bytes) -> str:
    """Return the SHA-256 digest of file content."""
    return hashlib.sha256(content).hexdigest()


def discover_classification_pdf_links(html: str) -> dict:
    """Discover official PDF links from the NSE Indices page."""
    parser = AnchorParser()
    parser.feed(html)

    discovered = {}

    for link in parser.links:
        label = link["text"].lower()
        href = link["href"]

        if not href:
            continue

        if "industry classification guidelines" in label:
            discovered["guidelines"] = urljoin(SOURCE_PAGE, href)

        elif "industry classification structure" in label:
            discovered["structure"] = urljoin(SOURCE_PAGE, href)

    return discovered


def download_bytes(
    session: requests.Session,
    url: str,
    timeout: int = 45,
) -> bytes:
    """Download a non-empty response."""
    response = session.get(url, timeout=timeout)
    response.raise_for_status()

    content = response.content

    if not content:
        raise ValueError(f"Downloaded file is empty: {url}")

    return content


def download_pdf(
    session: requests.Session,
    url: str,
    output_path: Path,
) -> dict:
    """Download and validate an official PDF."""
    content = download_bytes(session, url)

    if not content.startswith(b"%PDF"):
        raise ValueError(
            f"Response is not a valid PDF file: {url}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(content)

    return {
        "status": "DOWNLOADED",
        "url": url,
        "path": str(output_path.relative_to(PROJECT_ROOT)),
        "size_bytes": len(content),
        "sha256": sha256_bytes(content),
    }


def save_dataframe(frame: pd.DataFrame, path: Path) -> dict:
    """Save a collected official dataset and return its metadata."""
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ValueError(f"Dataset is empty: {path.name}")

    path.parent.mkdir(parents=True, exist_ok=True)
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
    """Collect official source documents and supporting datasets."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(HEADERS)

    report = {
        "project": "TradeLab Pro",
        "audit_type": "NSE Official Classification Source Collection",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_page": SOURCE_PAGE,
        "files": {},
        "company_mapping": {
            "status": "PENDING",
            "verified_company_mappings": 0,
            "note": (
                "The discovered public classification page exposes "
                "the taxonomy documents, not a complete company-level "
                "classification dataset. No company mapping is inferred."
            ),
            "next_action": (
                "Confirm availability through NSE Indices data "
                "subscription or official company-level feed."
            ),
            "contact": "indices@nse.co.in",
        },
    }

    # 1. Download the official classification page.
    page_response = session.get(SOURCE_PAGE, timeout=45)
    page_response.raise_for_status()

    page_html = page_response.text
    page_path = OUTPUT_DIR / "nse_industry_classification_source.html"
    page_path.write_text(page_html, encoding="utf-8")

    report["files"]["classification_source_page"] = {
        "status": "DOWNLOADED",
        "url": SOURCE_PAGE,
        "path": str(page_path.relative_to(PROJECT_ROOT)),
        "sha256": sha256_bytes(page_path.read_bytes()),
    }

    # 2. Discover official PDF URLs from the page.
    discovered = discover_classification_pdf_links(page_html)

    pdf_urls = {
        name: discovered.get(name, fallback)
        for name, fallback in SOURCE_FILES.items()
    }

    # 3. Download both official classification documents.
    for name, url in pdf_urls.items():
        output_path = OUTPUT_DIR / f"nse_industry_classification_{name}.pdf"

        try:
            report["files"][f"classification_{name}"] = download_pdf(
                session,
                url,
                output_path,
            )
        except Exception as exc:
            report["files"][f"classification_{name}"] = {
                "status": "FAILED",
                "url": url,
                "error": f"{type(exc).__name__}: {exc}",
            }

    # 4. Download NSE MII equity universe through the existing provider.
    try:
        universe = fetch_nse_equity_universe(
            session=session,
            lookback_days=7,
        )

        report["files"]["nse_equity_universe"] = save_dataframe(
            universe,
            OUTPUT_DIR / "nse_mii_equity_universe.csv",
        )

        sources = (
            universe["Source"].dropna().astype(str).unique().tolist()
            if "Source" in universe.columns
            else []
        )

        report["files"]["nse_equity_universe"]["source_labels"] = sources

    except Exception as exc:
        report["files"]["nse_equity_universe"] = {
            "status": "FAILED",
            "error": f"{type(exc).__name__}: {exc}",
        }

    # 5. Download the official Nifty FMCG constituent list.
    # This is supporting index data, NOT the complete company mapping.
    try:
        fmcg = fetch_sector_constituents(
            "FMCG",
            session=session,
            deduplicate=False,
        )

        report["files"]["nifty_fmcg_constituents"] = save_dataframe(
            fmcg,
            OUTPUT_DIR / "nifty_fmcg_official_constituents.csv",
        )

        report["files"]["nifty_fmcg_constituents"][
            "classification_role"
        ] = "SUPPORTING_INDEX_CONSTITUENTS_ONLY"

    except Exception as exc:
        report["files"]["nifty_fmcg_constituents"] = {
            "status": "FAILED",
            "error": f"{type(exc).__name__}: {exc}",
        }

    # 6. Summarize results without approving any company mapping.
    downloaded = sum(
        1
        for item in report["files"].values()
        if item.get("status") == "DOWNLOADED"
    )

    failed = sum(
        1
        for item in report["files"].values()
        if item.get("status") == "FAILED"
    )

    required_pdfs_ok = all(
        report["files"].get(f"classification_{name}", {}).get("status")
        == "DOWNLOADED"
        for name in ("structure", "guidelines")
    )

    report["summary"] = {
        "downloaded_sources": downloaded,
        "failed_sources": failed,
        "required_classification_pdfs_downloaded": required_pdfs_ok,
        "company_mapping_status": "PENDING",
        "sector_mapping_enabled": False,
        "overall_status": (
            "PASS"
            if required_pdfs_ok
            else "REVIEW"
        ),
    }

    report_path = (
        REPORT_DIR / "nse_official_classification_source_audit.json"
    )

    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(report["summary"], indent=2))

    print(f"Full report: {report_path}")

    if not required_pdfs_ok:
        raise RuntimeError(
            "One or more required official classification PDFs "
            "could not be downloaded."
        )

    return report


if __name__ == "__main__":
    run_downloader()
