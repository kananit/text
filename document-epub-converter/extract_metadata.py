#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path

from config import METADATA_EXAMPLE_FILE, METADATA_FILE, resolve_source_file
from extraction import ensure_extractor_available, extract_text
from metadata import (
    guess_metadata_from_text,
    load_example_metadata,
    save_book_metadata,
)

METADATA_TEMP_TEXT_FILE = Path("/tmp/document_epub_meta_extracted.txt")


def main() -> None:
    fallback = load_example_metadata(METADATA_EXAMPLE_FILE)

    try:
        source_file = resolve_source_file()
    except FileNotFoundError as exc:
        print(f"❌ {exc}")
        return

    ensure_extractor_available(source_file)
    print("🔎 Извлекаю текст из исходного файла для определения меты...")
    text = extract_text(
        source_file,
        METADATA_TEMP_TEXT_FILE,
        start_page=1,
        end_page=8,
    )

    metadata, missing_required = guess_metadata_from_text(text, fallback)
    save_book_metadata(METADATA_FILE, metadata)

    if METADATA_TEMP_TEXT_FILE.exists():
        METADATA_TEMP_TEXT_FILE.unlink()

    print(f"✓ Исходный файл: {source_file.name}")
    print(f"✓ Файл метаданных сохранён: {METADATA_FILE}")
    print(f"  title: {metadata.title}")
    print(f"  creator: {metadata.creator}")
    print(f"  publisher: {metadata.publisher}")
    print(f"  year: {metadata.year}")
    if missing_required:
        print(
            "⚠️  Обязательные поля не найдены в исходном файле и заполнены из meta.example.json: "
            + ", ".join(missing_required)
        )
    print("ℹ️  Проверьте файл и при необходимости отредактируйте вручную.")


if __name__ == "__main__":
    main()
