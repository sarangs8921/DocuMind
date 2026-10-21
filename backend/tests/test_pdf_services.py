
from pathlib import Path

import pytest

from app.services.chunking_service import chunk_pages
from app.services.pdf_service import extract_pdf_pages


def test_chunk_pages_preserves_page_number():
    pages = [
        {
            "page_number": 3,
            "text": "A" * 1200,
        }
    ]

    chunks = chunk_pages(pages, chunk_size=1000, overlap=150)

    assert len(chunks) == 2
    assert chunks[0]["page_number"] == 3
    assert chunks[1]["page_number"] == 3
    assert chunks[0]["text"][-150:] == chunks[1]["text"][:150]


def test_chunk_pages_rejects_invalid_overlap():
    with pytest.raises(ValueError):
        chunk_pages(
            [{"page_number": 1, "text": "Some text"}],
            chunk_size=100,
            overlap=100,
        )


def test_extract_pdf_pages_rejects_missing_file(tmp_path: Path):
    missing_file = tmp_path / "missing.pdf"

    with pytest.raises(FileNotFoundError):
        extract_pdf_pages(missing_file)


def test_extract_pdf_pages_rejects_non_pdf(tmp_path: Path):
    text_file = tmp_path / "sample.txt"
    text_file.write_text("This is not a PDF.", encoding="utf-8")

    with pytest.raises(ValueError, match="Only PDF files"):
        extract_pdf_pages(text_file)
