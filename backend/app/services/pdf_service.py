
from pathlib import Path
import fitz


def extract_pdf_pages(pdf_path: str | Path) -> tuple[int, list[dict]]:
    """
    Extract text and a rendered image for every PDF page.

    Text preserves selectable content.
    Images allow Gemini to inspect slide headings, diagrams,
    equations, labels and other visual information.
    """

    document = fitz.open(str(pdf_path))
    pages = []

    try:
        page_count = len(document)

        for page_number, page in enumerate(document, start=1):
            page_text = page.get_text("text").strip()

            # Render the complete slide as an image.
            # A moderate resolution keeps image sizes manageable.
            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(1.5, 1.5),
                alpha=False,
            )

            page_image = pixmap.tobytes("png")

            pages.append({
                "page_number": page_number,
                "text": page_text,
                "image": page_image,
            })

        return page_count, pages

    finally:
        document.close()


def extract_pdf_text(pdf_path: str | Path) -> tuple[int, str]:
    """
    Keep the original text extraction function for existing
    parts of the application that still use it.
    """

    document = fitz.open(str(pdf_path))

    try:
        page_count = len(document)
        chunks = []

        for page_number, page in enumerate(document, start=1):
            page_text = page.get_text("text").strip()

            if page_text:
                chunks.append(
                    f"[PAGE {page_number}]\n{page_text}"
                )

        return page_count, "\n\n".join(chunks)

    finally:
        document.close()
