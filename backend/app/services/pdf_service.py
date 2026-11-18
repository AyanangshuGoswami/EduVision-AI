from pathlib import Path
import fitz


def extract_pdf_text(pdf_path: str | Path) -> tuple[int, str]:
    # OCR for scanned pages will be added in a later phase.
    document = fitz.open(str(pdf_path))
    page_count = len(document)
    chunks = []
    for page_number, page in enumerate(document, start=1):
        page_text = page.get_text("text").strip()
        if page_text:
            chunks.append(f"[PAGE {page_number}]\n{page_text}")
    document.close()
    return page_count, "\n\n".join(chunks)
