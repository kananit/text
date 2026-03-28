import re
import subprocess
import sys
from pathlib import Path


SUPPORTED_SOURCE_EXTENSIONS = {".pdf", ".doc", ".docx"}


def _is_pymupdf_available() -> bool:
    try:
        import fitz  # type: ignore

        _ = fitz
        return True
    except Exception:
        return False


def ensure_pymupdf() -> None:
    if not _is_pymupdf_available():
        print("❌ PyMuPDF не найден. Установите: python3 -m pip install PyMuPDF")
        sys.exit(1)


def _format_pdf_span(text: str, is_bold: bool) -> str:
    if not text or not is_bold or not text.strip():
        return text

    leading_len = len(text) - len(text.lstrip())
    trailing_len = len(text) - len(text.rstrip())
    core = text[leading_len : len(text) - trailing_len if trailing_len else len(text)]
    return f"{text[:leading_len]}**{core}**{text[len(text) - trailing_len:]}"


def ensure_textutil() -> None:
    result = subprocess.run(["which", "textutil"], capture_output=True)
    if result.returncode != 0:
        print(
            "❌ textutil не найден. Для DOC/DOCX нужен textutil (обычно встроен в macOS)."
        )
        sys.exit(1)


def ensure_extractor_available(source_file: Path) -> None:
    suffix = source_file.suffix.lower()
    if suffix not in SUPPORTED_SOURCE_EXTENSIONS:
        print(f"❌ Неподдерживаемый формат: {source_file.suffix}")
        sys.exit(1)

    if suffix == ".pdf":
        ensure_pymupdf()
    else:
        ensure_textutil()


def _extract_pdf_text_pymupdf(
    source_file: Path,
    extracted_text_file: Path,
    start_page: int | None = None,
    end_page: int | None = None,
) -> str:
    import fitz  # type: ignore

    doc = fitz.open(source_file)

    start_idx = max(0, (start_page - 1) if start_page is not None else 0)
    end_idx = min(len(doc), end_page) if end_page is not None else len(doc)

    pages_text: list[str] = []
    for page_idx in range(start_idx, end_idx):
        page = doc[page_idx]
        page_dict = page.get_text("dict")
        lines_out: list[str] = []

        for block in page_dict.get("blocks", []):
            block_lines = block.get("lines", [])
            if not block_lines:
                continue
            for line in block_lines:
                parts: list[str] = []
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    if not span_text:
                        continue
                    font_name = str(span.get("font", ""))
                    flags = int(span.get("flags", 0))
                    is_bold = ("bold" in font_name.lower()) or bool(flags & 16)
                    parts.append(_format_pdf_span(span_text, is_bold))

                rendered_line = "".join(parts).rstrip()
                if rendered_line:
                    lines_out.append(rendered_line)

        pages_text.append("\n".join(lines_out))

    text = "\n\n".join(page for page in pages_text if page.strip())
    extracted_text_file.write_text(text, encoding="utf-8")
    return text


def _extract_pdf_text(
    source_file: Path,
    extracted_text_file: Path,
    start_page: int | None = None,
    end_page: int | None = None,
) -> str:
    ensure_pymupdf()
    return _extract_pdf_text_pymupdf(
        source_file,
        extracted_text_file,
        start_page,
        end_page,
    )


def _extract_doc_text(source_file: Path) -> str:
    command = ["textutil", "-convert", "txt", "-stdout", str(source_file)]
    result = subprocess.run(command, capture_output=True)
    if result.returncode != 0:
        print("❌ Ошибка при извлечении текста из DOC/DOCX")
        sys.exit(1)

    text = result.stdout.decode("utf-8", errors="replace")
    # Convert Unicode line/paragraph separators to real newlines
    text = text.replace("\u2028", "\n").replace("\u2029", "\n")
    # textutil sometimes omits paragraph breaks before chapter headings;
    # inject a newline before any heading that is mid-line (not preceded by \n or \u200f)
    text = re.sub(
        r"(?<![\n\u200f])((?:глава|часть|раздел|chapter|part|section)\s+\d+)",
        r"\n\1",
        text,
        flags=re.IGNORECASE,
    )
    return text


def extract_text(
    source_file: Path,
    extracted_text_file: Path,
    start_page: int | None = None,
    end_page: int | None = None,
) -> str:
    suffix = source_file.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf_text(source_file, extracted_text_file, start_page, end_page)
    if suffix in {".doc", ".docx"}:
        return _extract_doc_text(source_file)

    print(f"❌ Неподдерживаемый формат: {source_file.suffix}")
    sys.exit(1)
