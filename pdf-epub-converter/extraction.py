import subprocess
import sys
from pathlib import Path


def ensure_pdftotext() -> None:
    result = subprocess.run(["which", "pdftotext"], capture_output=True)
    if result.returncode != 0:
        print("❌ pdftotext не найден. Установите: brew install poppler")
        sys.exit(1)


def extract_text(pdf_file: Path, temp_txt: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_file), str(temp_txt)],
        capture_output=True,
    )
    if result.returncode != 0:
        print("❌ Ошибка при извлечении текста")
        sys.exit(1)

    return temp_txt.read_text(encoding="utf-8", errors="replace")
