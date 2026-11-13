from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import pytest

from data.providers.nse_bhavcopy_provenance import (
    NSEBhavcopyProvenanceError,
    _validate_bhavcopy_archive,
    audit_nse_bhavcopy_provenance,
)


def make_zip(files=None):
    files = files or {"bhavcopy.csv": "Symbol,ISIN\nABC,INE000A01001\n"}
    buffer = BytesIO()

    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)

    return buffer.getvalue()


def test_valid_archive_has_one_csv():
    _validate_bhavcopy_archive(make_zip())


def test_rejects_invalid_zip():
    with pytest.raises(NSEBhavcopyProvenanceError):
        _validate_bhavcopy_archive(b"not-a-zip")


def test_rejects_archive_without_csv():
    with pytest.raises(NSEBhavcopyProvenanceError):
        _validate_bhavcopy_archive(
            make_zip({"readme.txt": "not a bhavcopy"})
        )


def test_rejects_multiple_csv_files():
    with pytest.raises(NSEBhavcopyProvenanceError):
        _validate_bhavcopy_archive(
            make_zip({
                "first.csv": "A\n1\n",
                "second.csv": "B\n2\n",
            })
        )


def test_rejects_empty_csv():
    with pytest.raises(NSEBhavcopyProvenanceError):
        _validate_bhavcopy_archive(
            make_zip({"bhavcopy.csv": ""})
        )


def test_rejects_unsafe_archive_path():
    with pytest.raises(NSEBhavcopyProvenanceError):
        _validate_bhavcopy_archive(
            make_zip({"../bhavcopy.csv": "A\n1\n"})
        )


def test_rejects_empty_source_bytes():
    with pytest.raises(NSEBhavcopyProvenanceError):
        _validate_bhavcopy_archive(b"")


def test_audit_rejects_invalid_filename():
    with pytest.raises(NSEBhavcopyProvenanceError):
        audit_nse_bhavcopy_provenance(
            bhavcopy=pd.DataFrame({"Symbol": ["ABC"]}),
            universe=pd.DataFrame({"Symbol": ["ABC"]}),
            source_bytes=make_zip(),
            source_filename="../bhavcopy.zip",
        )