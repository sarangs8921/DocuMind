
from pathlib import Path

from pypdf import PdfReader


def extract_pdf_pages(file_path: str | Path) -> list[dict]:
    """
    Extract text page by page.

    Page numbers returned by this function are 1-based.
    """
    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"PDF file not found: {path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError("Only PDF files are supported.")

    reader = PdfReader(str(path))

    if reader.is_encrypted:
        raise ValueError("Encrypted PDFs are not supported.")

    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""

        if text.strip():
            pages.append({
                "page_number": page_number,
                "text": text.strip(),
            })

    if not pages:
        raise ValueError(
            "No extractable text found. "
            "The PDF may be scanned or contain no readable text."
        )

    return pages
