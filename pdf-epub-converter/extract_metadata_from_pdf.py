#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path

from config import METADATA_EXAMPLE_FILE, METADATA_FILE, resolve_pdf_file
from extraction import ensure_pdftotext, extract_text
from metadata import (
    CREATOR_PATTERNS,
    TITLE_PATTERNS,
    YEAR_PATTERNS,
    guess_metadata_from_text,
    load_example_metadata,
    save_book_metadata,
)

META_TEMP_TXT = Path("/tmp/pdf_meta_extracted.txt")


def main() -> None:
    ensure_pdftotext()
    fallback = load_example_metadata(METADATA_EXAMPLE_FILE)

    try:
        pdf_file = resolve_pdf_file()
    except FileNotFoundError as exc:
        print(f"❌ {exc}")
        return

    print("🔎 Извлекаю первые страницы PDF для определения меты...")
    text = extract_text(pdf_file, META_TEMP_TXT, start_page=1, end_page=8)

    metadata, missing_required = guess_metadata_from_text(text, fallback)
    save_book_metadata(METADATA_FILE, metadata)

    if META_TEMP_TXT.exists():
        META_TEMP_TXT.unlink()

    print(f"✓ Исходный PDF: {pdf_file.name}")
    print(f"✓ Файл метаданных сохранён: {METADATA_FILE}")
    print(f"  title: {metadata.title}")
    print(f"  creator: {metadata.creator}")
    print(f"  publisher: {metadata.publisher}")
    print(f"  year: {metadata.year}")
    if missing_required:
        print(
            "⚠️  Обязательные поля не найдены в PDF и заполнены из meta.example.json: "
            + ", ".join(missing_required)
        )
    print("ℹ️  Проверьте файл и при необходимости отредактируйте вручную.")


if __name__ == "__main__":
    main()
