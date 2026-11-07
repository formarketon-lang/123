from scripts.run_industry_classification_source_downloader import (
    discover_classification_pdf_links,
    sha256_bytes,
)


def test_discovers_official_classification_pdf_links():
    html = """
    <html>
      <body>
        <a href="/docs/guidelines.pdf">
          NSE Indices Industry Classification Guidelines
        </a>
        <a href="/docs/structure.pdf">
          NSE Indices Industry Classification Structure
        </a>
      </body>
    </html>
    """

    result = discover_classification_pdf_links(html)

    assert result["guidelines"].endswith("/docs/guidelines.pdf")
    assert result["structure"].endswith("/docs/structure.pdf")


def test_ignores_unrelated_links():
    html = """
    <html>
      <body>
        <a href="/docs/other.pdf">Annual Report</a>
      </body>
    </html>
    """

    result = discover_classification_pdf_links(html)

    assert result == {}


def test_sha256_is_deterministic():
    content = b"TradeLab Pro official source audit"

    first = sha256_bytes(content)
    second = sha256_bytes(content)

    assert first == second
    assert len(first) == 64


def test_sha256_changes_when_content_changes():
    first = sha256_bytes(b"official source")
    second = sha256_bytes(b"modified source")

    assert first != second
