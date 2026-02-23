try:
    import fitz

    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


def extract_text_from_pdf(pdf_path: str) -> str:
    if not PYMUPDF_AVAILABLE:
        raise ImportError(
            "PyMuPDF (fitz) is not installed. Please install it with: pip install pymupdf"
        )

    doc = fitz.open(pdf_path)
    text_parts = []
    for page_num, page in enumerate(doc):
        text = page.get_text()
        if text.strip():
            text_parts.append(f"--- 第 {page_num + 1} 页 ---\n{text}")
    doc.close()
    return "\n\n".join(text_parts)


def extract_text_from_bytes(pdf_bytes: bytes) -> str:
    if not PYMUPDF_AVAILABLE:
        raise ImportError(
            "PyMuPDF (fitz) is not installed. Please install it with: pip install pymupdf"
        )

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text_parts = []
    for page_num, page in enumerate(doc):
        text = page.get_text()
        if text.strip():
            text_parts.append(f"--- 第 {page_num + 1} 页 ---\n{text}")
    doc.close()
    return "\n\n".join(text_parts)
