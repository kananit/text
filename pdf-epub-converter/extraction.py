import re
import subprocess
import sys
from pathlib import Path


SUPPORTED_SOURCE_EXTENSIONS = {".pdf", ".doc", ".docx"}


def ensure_pdftotext() -> None:
    result = subprocess.run(["which", "pdftotext"], capture_output=True)
    if result.returncode != 0:
        print("❌ pdftotext не найден. Установите: brew install poppler")
        sys.exit(1)


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
        ensure_pdftotext()
    else:
        ensure_textutil()


def _extract_pdf_text(
    source_file: Path,
    extracted_text_file: Path,
    start_page: int | None = None,
    end_page: int | None = None,
) -> str:
    command = ["pdftotext", "-layout"]
    if start_page is not None:
        command.extend(["-f", str(start_page)])
    if end_page is not None:
        command.extend(["-l", str(end_page)])
    command.extend([str(source_file), str(extracted_text_file)])

    result = subprocess.run(command, capture_output=True)
    if result.returncode != 0:
        print("❌ Ошибка при извлечении текста из PDF-файла")
        sys.exit(1)

    return extracted_text_file.read_text(encoding="utf-8", errors="replace")


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
