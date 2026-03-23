#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from config import (
    METADATA_EXAMPLE_FILE,
    METADATA_FILE,
    TEMP_TXT,
    cleanup_temp_files,
    ensure_build_dirs,
    resolve_epub_output,
    resolve_pdf_file,
    resolve_cover_image,
)
from epub_builder import (
    build_chapter_documents,
    build_cover_page,
    build_toc_page,
    package_epub,
    write_container,
    write_mimetype,
    write_ncx,
    write_opf,
    write_stylesheet,
)
from extraction import ensure_pdftotext, extract_text
from metadata import ensure_metadata_files, load_book_metadata, load_example_metadata
from parsing import (
    detect_language,
    extract_toc_entries,
    fallback_chapters,
    identify_chapters,
)


def main() -> None:
    try:
        pdf_file = resolve_pdf_file()
    except FileNotFoundError as exc:
        print(f"❌ {exc}")
        return

    epub_output = resolve_epub_output(pdf_file)

    ensure_build_dirs()
    example_created, metadata_created, bootstrap_example_fields = ensure_metadata_files(
        METADATA_FILE,
        METADATA_EXAMPLE_FILE,
        pdf_file,
    )
    example_metadata = load_example_metadata(METADATA_EXAMPLE_FILE)
    metadata, metadata_from_file, example_fields_used = load_book_metadata(
        METADATA_FILE,
        example_metadata,
    )

    print("=" * 70)
    print(f"🚀 PDF to EPUB Converter - {metadata.title}")
    print("=" * 70)
    if example_created:
        print(f"✓ Создан шаблон метаданных: {METADATA_EXAMPLE_FILE.name}")
    if metadata_created:
        print(
            f"✓ Создан файл меты: {METADATA_FILE.name} (источник: PDF → fallback meta.example.json)"
        )
    if bootstrap_example_fields:
        fields = ", ".join(bootstrap_example_fields)
        print(
            "⚠️  При создании meta.json обязательные поля не найдены в PDF и взяты из meta.example.json: "
            f"{fields}"
        )
    if metadata_from_file:
        print(f"✓ Мета загружена из файла: {METADATA_FILE.name}")
    else:
        print(
            f"⚠️  Файл меты не найден или повреждён, использую defaults: {METADATA_FILE.name}"
        )
    if example_fields_used:
        fields = ", ".join(example_fields_used)
        print(
            "⚠️  Обязательные поля меты взяты из meta.example.json "
            f"(не найдены в PDF/meta.json): {fields}"
        )
    print(f"✓ Исходный PDF: {pdf_file.name}")

    print("\n🔍 Проверяем доступность инструментов...")
    ensure_pdftotext()
    print("✓ pdftotext найден")

    print("\n📄 Извлекаю текст из PDF...")
    full_text = extract_text(pdf_file, TEMP_TXT)
    char_count = len(full_text)
    word_count = len(full_text.split())
    print(f"✓ Извлечено: {char_count:,} символов, ~{word_count // 250} страниц")

    print("\n🔎 Определяю структуру глав...")
    toc_entries = extract_toc_entries(full_text)
    if toc_entries:
        print(f"✓ Найдено пунктов в оглавлении: {len(toc_entries)}")
    else:
        print("⚠️  Отдельное оглавление не распознано")

    language = detect_language(full_text)
    chapters = identify_chapters(full_text, toc_entries)
    if not chapters or len(chapters) < 2:
        print("⚠️  Автоматическое определение глав не удалось")
        print("   Разбиваю по частям...")
        chapters = fallback_chapters(full_text, language)

    print(f"✓ Найдено {len(chapters)} глав/частей\n")
    print("📚 СТРУКТУРА ОГЛАВЛЕНИЯ:")
    for index, chapter in enumerate(chapters[:10], 1):
        words = len(chapter.content.split())
        print(f"   {index:2d}. {chapter.title:60s} ({words:5d} слов)")
    if len(chapters) > 10:
        print(f"   ... и еще {len(chapters) - 10} глав")

    print("\n✍️  Создаю XHTML файлы...")
    book_items = build_chapter_documents(chapters, language)
    for item in book_items[:5]:
        print(f"   ✓ {item.id}: {item.title[:50]}")
    print(f"✓ Создано {len(book_items)} XHTML файлов")

    toc_page_id = build_toc_page(book_items, toc_entries, language)
    if toc_entries:
        print("✓ Добавлена отдельная страница оглавления (из PDF)")
    else:
        print("✓ Добавлена отдельная страница оглавления (из распознанных глав)")

    print("\n📝 Создаю CSS стили...")
    write_stylesheet()
    print("✓ CSS создан")

    print("\n🖼️  Проверяю обложку...")
    cover_path = resolve_cover_image(pdf_file)
    if cover_path:
        build_cover_page(cover_path, language)
        print(f"✓ Обложка: {cover_path.name}")
    else:
        print(
            "⚠️  Обложка не найдена — положите cover.jpeg (или cover.jpg/cover.png) в папку pdf-epub/"
        )

    print("📦 Создаю метаданные EPUB...")
    write_opf(book_items, toc_page_id, language, metadata, cover_path)
    print("✓ content.opf создан")
    write_ncx(book_items, toc_page_id, language, metadata)
    print("✓ toc.ncx (оглавление) создан")
    write_container()
    print("✓ container.xml создан")
    write_mimetype()
    print("✓ mimetype создан")

    print("\n📦 Упаковываю в EPUB архив...")
    package_epub(book_items, toc_page_id, epub_output, cover_path)
    cleanup_temp_files()

    file_size = epub_output.stat().st_size / (1024 * 1024)
    print("\n" + "=" * 70)
    print("✅ EPUB УСПЕШНО СОЗДАН!")
    print("=" * 70)
    print(f"📍 Файл:     {epub_output}")
    print(f"📊 Размер:   {file_size:.2f} MB")
    print(f"📚 Глав:     {len(book_items)}")
    print(f"📖 Слов:     {word_count:,}")
    if toc_entries:
        print(f"📑 Оглавл.:  Отдельное + NCX ({len(toc_entries)} пунктов из PDF)")
    else:
        print(f"📑 Оглавл.:  Отдельное + NCX ({len(book_items)} пунктов по главам)")
    print("🧹 Временные файлы: удалены")
    print("=" * 70)


if __name__ == "__main__":
    main()
