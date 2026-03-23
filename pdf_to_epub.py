#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF to EPUB Converter - Public Domain
Преобразует PDF в структурированный EPUB с оглавлением,
поддержкой русских глав и базовым распознаванием таблиц.
"""

import os
import re
import shutil
import zipfile
from collections import Counter
from datetime import datetime
import subprocess
import sys

# Настройки
BASE_DIR = "/Users/sollidy/Desktop/git/my-projects/text"
PDF_DIR = f"{BASE_DIR}/pdf-epub"
PDF_FILE = f"{PDF_DIR}/WarOnTheSaints.pdf"
OUTPUT_DIR = f"{PDF_DIR}/epub_from_pdf"
TEMP_TXT = "/tmp/war_saints_extracted.txt"
EPUB_OUTPUT = f"{PDF_DIR}/WarOnTheSaints_Professional.epub"


def cleanup_temp_files():
    """Удаляет временные файлы и промежуточную папку сборки."""
    if os.path.exists(TEMP_TXT):
        os.remove(TEMP_TXT)
    if os.path.isdir(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR, ignore_errors=True)


# Инициализация
cleanup_temp_files()
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/OEBPS/text", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/OEBPS/css", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/META-INF", exist_ok=True)

print("=" * 70)
print("🚀 PDF to EPUB Converter - War with the Saints")
print("=" * 70)

# Проверяем pdftotext
print("\n🔍 Проверяем доступность инструментов...")
result = subprocess.run(["which", "pdftotext"], capture_output=True)
if result.returncode != 0:
    print("❌ pdftotext не найден. Установите: brew install poppler")
    sys.exit(1)

print("✓ pdftotext найден")

# Извлекаем текст
print(f"\n📄 Извлекаю текст из PDF...")
result = subprocess.run(
    ["pdftotext", "-layout", PDF_FILE, TEMP_TXT], capture_output=True
)

if result.returncode != 0:
    print("❌ Ошибка при извлечении текста")
    sys.exit(1)

with open(TEMP_TXT, "r", encoding="utf-8", errors="replace") as f:
    full_text = f.read()

char_count = len(full_text)
word_count = len(full_text.split())
print(f"✓ Извлечено: {char_count:,} символов, ~{word_count // 250} страниц")


def detect_language(text):
    """Грубое определение языка для метаданных EPUB."""
    cyr = len(re.findall(r"[А-Яа-яЁё]", text))
    lat = len(re.findall(r"[A-Za-z]", text))
    return "ru" if cyr > lat else "en"


def clean_line(text):
    """Очищает строку от контрольных символов."""
    text = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]", "", text)
    return text.rstrip()


def clean_paragraph(text):
    """Нормализация пробелов в параграфе."""
    text = clean_line(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_title(title):
    """Нормализует заголовок главы."""
    title = clean_paragraph(title)
    title = re.sub(r"\s{2,}", " ", title)
    return title[:120]


def is_chapter_heading(line):
    """Проверяет, похоже ли на заголовок главы (RU/EN)."""
    stripped = line.strip()
    if not stripped:
        return False

    patterns = [
        r"^(глава|часть|раздел)\s+[0-9ivxlcdm]+(?:\s*[\.:\-)])?(?:\s+.*)?$",
        r"^(chapter|part|section)\s+[0-9ivxlcdm]+(?:\s*[\.:\-)])?(?:\s+.*)?$",
        r"^(приложение|appendix)\s+[a-zа-я0-9ivxlcdm]+(?:\s*[\.:\-)])?(?:\s+.*)?$",
    ]

    for pattern in patterns:
        if re.match(pattern, stripped, re.IGNORECASE):
            return True

    return False


def chapter_number_key(title):
    """Извлекает ключ номера главы для сопоставления с оглавлением."""
    match = re.search(
        r"(?:глава|часть|раздел|chapter|part|section)\s+([0-9ivxlcdm]+)",
        title,
        re.IGNORECASE,
    )
    if not match:
        return None
    return match.group(1).lower()


def extract_toc_entries(text):
    """Пытается выделить оглавление из исходного текста PDF."""
    lines = [clean_line(line) for line in text.split("\n")]
    toc_header = re.compile(
        r"^(содержание|оглавление|contents|table of contents)\s*$", re.IGNORECASE
    )
    toc_entry_patterns = [
        re.compile(r"^(?P<title>.+?)\s*\.{2,}\s*(?P<page>\d{1,4})\s*$"),
        re.compile(
            r"^(?P<title>(?:глава|часть|раздел)\s+[0-9ivxlcdm].*?)\s{2,}(?P<page>\d{1,4})\s*$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^(?P<title>(?:chapter|part|section)\s+[0-9ivxlcdm].*?)\s{2,}(?P<page>\d{1,4})\s*$",
            re.IGNORECASE,
        ),
    ]

    start_idx = None
    for idx, line in enumerate(lines[:500]):
        if toc_header.match(line.strip()):
            start_idx = idx
            break

    scan_start = start_idx + 1 if start_idx is not None else 0
    scan_end = min(len(lines), scan_start + 320)

    entries = []
    seen = set()
    for line in lines[scan_start:scan_end]:
        stripped = line.strip()
        if not stripped:
            continue

        matched = None
        for pattern in toc_entry_patterns:
            matched = pattern.match(stripped)
            if matched:
                break

        if not matched:
            if len(entries) > 4 and is_chapter_heading(stripped):
                break
            continue

        title = normalize_title(matched.group("title"))
        page = matched.group("page")
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)

        if len(title) < 4:
            continue

        entries.append({"title": title, "page": page})

    return entries


def resolve_title_with_toc(raw_title, toc_entries, used_indices):
    """Сопоставляет заголовок главы с пунктом оглавления, если возможно."""
    normalized = normalize_title(raw_title)
    lowered = normalized.lower()

    for idx, item in enumerate(toc_entries):
        if idx in used_indices:
            continue
        toc_title = item["title"].lower()
        if (
            lowered == toc_title
            or lowered.startswith(toc_title)
            or toc_title.startswith(lowered)
        ):
            used_indices.add(idx)
            return item["title"]

    number_key = chapter_number_key(normalized)
    if number_key:
        for idx, item in enumerate(toc_entries):
            if idx in used_indices:
                continue
            item_key = chapter_number_key(item["title"])
            if item_key and item_key == number_key:
                used_indices.add(idx)
                return item["title"]

    return normalized


def identify_chapters(text, toc_entries):
    """Определяет главы и разбивает текст с учетом RU/EN заголовков."""
    lines = [clean_line(line) for line in text.split("\n")]
    chapters = []
    current_title = None
    current_content = []
    used_toc_indices = set()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_content:
                current_content.append("")
            continue

        if is_chapter_heading(stripped):
            accumulated_len = len("\n".join(current_content).strip())
            if current_title and accumulated_len > 2500:
                chapters.append(
                    {
                        "title": current_title,
                        "content": "\n".join(current_content).strip(),
                    }
                )
                current_content = []
            elif current_title and accumulated_len <= 2500:
                current_content.append(line)
                continue

            current_title = resolve_title_with_toc(
                stripped, toc_entries, used_toc_indices
            )
            continue

        if current_title:
            current_content.append(line)

    if current_title and current_content:
        final_content = "\n".join(current_content).strip()
        if len(final_content) > 300:
            chapters.append({"title": current_title, "content": final_content})

    return chapters


def split_columns(line):
    """Делит строку таблицы на ячейки по большим отступам."""
    raw_cells = re.split(r"\t+|\s{2,}", line.strip())
    cells = [clean_paragraph(cell) for cell in raw_cells if cell.strip()]
    return cells


def parse_table_rows(block_lines):
    """Определяет таблицу в текстовом блоке и возвращает строки ячеек."""
    rows = []
    for line in block_lines:
        cells = split_columns(line)
        if len(cells) >= 2:
            rows.append(cells)

    if len(rows) < 2:
        return None

    counts = Counter(len(row) for row in rows)
    target_cols, freq = counts.most_common(1)[0]
    if target_cols < 2 or freq < 2:
        return None

    normalized_rows = []
    for row in rows:
        if len(row) < target_cols:
            row = row + [""] * (target_cols - len(row))
        elif len(row) > target_cols:
            row = row[:target_cols]
        normalized_rows.append(row)

    return normalized_rows


def chapter_blocks(content):
    """Разбивает текст главы на блоки: заголовки, параграфы, таблицы."""
    lines = [clean_line(line) for line in content.split("\n")]
    blocks = []
    buffer_lines = []

    def flush_buffer():
        if not buffer_lines:
            return

        non_empty = [line for line in buffer_lines if line.strip()]
        buffer_lines.clear()
        if not non_empty:
            return

        rows = parse_table_rows(non_empty)
        if rows:
            blocks.append({"type": "table", "rows": rows})
            return

        if len(non_empty) == 1:
            one = clean_paragraph(non_empty[0])
            if one and len(one) < 90 and not re.search(r"[\.!?…:]$", one):
                blocks.append({"type": "h2", "text": one})
                return

        paragraph = clean_paragraph(" ".join(non_empty))
        if paragraph:
            blocks.append({"type": "p", "text": paragraph})

    for line in lines:
        if line.strip() == "":
            flush_buffer()
            continue
        buffer_lines.append(line)

    flush_buffer()
    return blocks


print("\n🔎 Определяю структуру глав...")
toc_entries = extract_toc_entries(full_text)
if toc_entries:
    print(f"✓ Найдено пунктов в оглавлении: {len(toc_entries)}")
else:
    print("⚠️  Отдельное оглавление не распознано")

chapters = identify_chapters(full_text, toc_entries)

if not chapters or len(chapters) < 2:
    print("⚠️  Автоматическое определение глав не удалось")
    print("   Разбиваю по частям...")

    language = detect_language(full_text)
    chunk_size = 60000
    chunks = []
    for i in range(0, len(full_text), chunk_size):
        chunk = full_text[i : i + chunk_size].strip()
        if len(chunk) > 1200:
            chunks.append(chunk)

    part_prefix = "Часть" if language == "ru" else "Part"
    chapters = [
        {"title": f"{part_prefix} {i+1}", "content": chunk}
        for i, chunk in enumerate(chunks)
    ]

print(f"✓ Найдено {len(chapters)} глав/частей\n")

# Показываем структуру
print("📚 СТРУКТУРА ОГЛАВЛЕНИЯ:")
for i, ch in enumerate(chapters[:10], 1):
    title = ch["title"]
    words = len(ch["content"].split())
    print(f"   {i:2d}. {title:60s} ({words:5d} слов)")

if len(chapters) > 10:
    print(f"   ... и еще {len(chapters) - 10} глав")


def escape_xml(text):
    """Экранирует XML символы."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    return text


def render_blocks_to_xhtml(blocks):
    """Рендерит блоки главы в XHTML."""
    chunks = []
    for block in blocks:
        if block["type"] == "p":
            chunks.append(f"    <p>{escape_xml(block['text'])}</p>")
        elif block["type"] == "h2":
            chunks.append(f"    <h2>{escape_xml(block['text'])}</h2>")
        elif block["type"] == "table":
            rows = block["rows"]
            chunks.append('    <div class="table-wrap">\n    <table>')
            for row_idx, row in enumerate(rows):
                tag = "th" if row_idx == 0 else "td"
                row_html = "".join(
                    [f"<{tag}>{escape_xml(cell)}</{tag}>" for cell in row]
                )
                chunks.append(f"      <tr>{row_html}</tr>")
            chunks.append("    </table>\n    </div>")
    return "\n".join(chunks)


language = detect_language(full_text)


print("\n✍️  Создаю XHTML файлы...")

book_items = []
toc_items = []

for idx, chapter in enumerate(chapters, 1):
    file_id = f"chapter-{idx:03d}"
    title = chapter["title"].strip()
    content = chapter["content"]

    blocks = chapter_blocks(content)
    html_content = render_blocks_to_xhtml(blocks)

    # XHTML шаблон
    xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xml:lang="{language}" xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
<meta charset="UTF-8"/>
<title>{escape_xml(title)}</title>
<link rel="stylesheet" href="../css/style.css" type="text/css"/>
</head>
<body>
<div class="chapter">
<h1 class="chapter-title">{escape_xml(title)}</h1>
<div class="chapter-content">
{html_content}</div>
</div>
</body>
</html>"""

    # Сохраняем
    xhtml_file = f"{OUTPUT_DIR}/OEBPS/text/{file_id}.xhtml"
    with open(xhtml_file, "w", encoding="utf-8") as f:
        f.write(xhtml)

    book_items.append({"id": file_id, "href": f"text/{file_id}.xhtml", "title": title})

    toc_items.append({"id": file_id, "title": title, "order": idx})

    if idx <= 5 or idx % 5 == 0:
        print(f"   ✓ {file_id}: {title[:50]}")

print(f"✓ Создано {len(book_items)} XHTML файлов")

toc_page_id = "parsed-toc"
toc_rows = []
toc_source = (
    toc_entries
    if toc_entries
    else [{"title": item["title"], "page": ""} for item in book_items]
)

for idx, entry in enumerate(toc_source, 1):
    if idx <= len(book_items):
        target = f"chapter-{idx:03d}.xhtml"
        title_html = f'<a href="{target}">{escape_xml(entry["title"])}</a>'
    else:
        title_html = escape_xml(entry["title"])
    page = escape_xml(entry.get("page", ""))
    toc_rows.append(
        f'    <li><span class="toc-title">{title_html}</span><span class="toc-page">{page}</span></li>'
    )

toc_xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xml:lang="{language}" xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
<meta charset="UTF-8"/>
<title>Оглавление</title>
<link rel="stylesheet" href="../css/style.css" type="text/css"/>
</head>
<body>
<div class="chapter">
<h1 class="chapter-title">Оглавление</h1>
<ol class="toc-list">
{os.linesep.join(toc_rows)}
</ol>
</div>
</body>
</html>"""

with open(f"{OUTPUT_DIR}/OEBPS/text/{toc_page_id}.xhtml", "w", encoding="utf-8") as f:
    f.write(toc_xhtml)

if toc_entries:
    print("✓ Добавлена отдельная страница оглавления (из PDF)")
else:
    print("✓ Добавлена отдельная страница оглавления (из распознанных глав)")


# CSS стили
print("\n📝 Создаю CSS стили...")

css = """/* War with the Saints - EPUB Stylesheet */

html, body {
    margin: 0;
    padding: 0;
}

body {
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 1em;
    line-height: 1.6;
    background-color: #ffffff;
    color: #333333;
}

.chapter {
    margin: 0;
    padding: 1em;
}

.chapter-title {
    font-size: 1.8em;
    font-weight: bold;
    margin: 0.5em 0 1.5em 0;
    color: #1a1a1a;
    page-break-after: avoid;
    page-break-inside: avoid;
    text-align: center;
    border-bottom: 2px solid #cccccc;
    padding-bottom: 0.5em;
}

.chapter-content {
    text-align: justify;
}

p {
    margin: 0.5em 0;
    text-align: justify;
    text-indent: 1.5em;
    orphans: 2;
    widows: 2;
}

p:first-of-type {
    text-indent: 0;
}

h1, h2, h3, h4, h5, h6 {
    font-weight: bold;
    margin-top: 1em;
    margin-bottom: 0.5em;
    page-break-after: avoid;
    text-align: left;
}

h2 {
    font-size: 1.4em;
    border-bottom: 1px solid #dddddd;
    padding-bottom: 0.3em;
}

.table-wrap {
    overflow-x: auto;
    margin: 1em 0;
}

table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.95em;
}

th, td {
    border: 1px solid #d9d9d9;
    padding: 0.35em 0.45em;
    vertical-align: top;
}

th {
    font-weight: bold;
    background: #f7f7f7;
}

.toc-list {
    list-style: none;
    margin: 0;
    padding: 0;
}

.toc-list li {
    display: flex;
    justify-content: space-between;
    gap: 1em;
    border-bottom: 1px dotted #d3d3d3;
    padding: 0.25em 0;
}

.toc-title {
    flex: 1;
}

.toc-page {
    min-width: 2.5em;
    text-align: right;
}

em, i {
    font-style: italic;
}

strong, b {
    font-weight: bold;
}

a {
    color: #0066cc;
    text-decoration: none;
}

a:visited {
    color: #660066;
}

blockquote {
    margin: 1em 0;
    padding-left: 1.5em;
    border-left: 3px solid #cccccc;
    color: #555555;
    font-style: italic;
}

@media (max-width: 600px) {
    body {
        font-size: 90%;
    }
    
    .chapter {
        padding: 0.75em;
    }
}
"""

with open(f"{OUTPUT_DIR}/OEBPS/css/style.css", "w", encoding="utf-8") as f:
    f.write(css)

print("✓ CSS создан")


# content.opf
print("📦 Создаю метаданные EPUB...")

manifest = "\n".join(
    [
        f'    <item id="{item["id"]}" href="{item["href"]}" media-type="application/xhtml+xml"/>'
        for item in book_items
    ]
)

spine = "\n".join([f'    <itemref idref="{item["id"]}"/>' for item in book_items])

extra_manifest = ""
extra_spine = ""
if toc_page_id:
    extra_manifest = f'    <item id="{toc_page_id}" href="text/{toc_page_id}.xhtml" media-type="application/xhtml+xml"/>\n'
    extra_spine = f'    <itemref idref="{toc_page_id}"/>\n'

opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uuid_id" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>War with the Saints</dc:title>
    <dc:creator>Jessie Penn-Lewis</dc:creator>
    <dc:contributor>Evan Roberts</dc:contributor>
    <dc:date>{datetime.now().strftime('%Y-%m-%d')}</dc:date>
        <dc:language>{language}</dc:language>
    <dc:identifier id="uuid_id">war-with-saints-{datetime.now().strftime('%Y%m%d%H%M%S')}</dc:identifier>
    <dc:description>A classic work on spiritual warfare, deliverance from demonic oppression, and Christian victory.</dc:description>
    <dc:rights>Public Domain</dc:rights>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtb+xml"/>
    <item id="css" href="css/style.css" media-type="text/css"/>
{extra_manifest}{manifest}  </manifest>
  <spine toc="ncx">
{extra_spine}{spine}  </spine>
</package>"""

with open(f"{OUTPUT_DIR}/OEBPS/content.opf", "w", encoding="utf-8") as f:
    f.write(opf)

print("✓ content.opf создан")


# toc.ncx
nav_source_items = []
play_order = 1

if toc_page_id:
    nav_source_items.append(
        {
            "id": toc_page_id,
            "title": "Оглавление" if language == "ru" else "Contents",
            "src": f"text/{toc_page_id}.xhtml",
            "order": play_order,
        }
    )
    play_order += 1

for item in toc_items:
    nav_source_items.append(
        {
            "id": item["id"],
            "title": item["title"],
            "src": f"text/{item['id']}.xhtml",
            "order": play_order,
        }
    )
    play_order += 1

nav_points = "\n".join(
    [
        f"""    <navPoint id="{item["id"]}" playOrder="{item["order"]}">
      <navLabel><text>{escape_xml(item["title"])}</text></navLabel>
      <content src="{item["src"]}"/>
    </navPoint>"""
        for item in nav_source_items
    ]
)

ncx = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="war-with-saints"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>War with the Saints</text></docTitle>
  <navMap>
{nav_points}  </navMap>
</ncx>"""

with open(f"{OUTPUT_DIR}/OEBPS/toc.ncx", "w", encoding="utf-8") as f:
    f.write(ncx)

print("✓ toc.ncx (оглавление) создан")


# container.xml
container = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""

with open(f"{OUTPUT_DIR}/META-INF/container.xml", "w", encoding="utf-8") as f:
    f.write(container)

print("✓ container.xml создан")


# mimetype
with open(f"{OUTPUT_DIR}/mimetype", "w", encoding="utf-8") as f:
    f.write("application/epub+zip")

print("✓ mimetype создан")


# Упаковываем в EPUB
print(f"\n📦 Упаковываю в EPUB архив...")

with zipfile.ZipFile(EPUB_OUTPUT, "w", zipfile.ZIP_DEFLATED) as z:
    # mimetype без сжатия (должен быть первым)
    z.write(f"{OUTPUT_DIR}/mimetype", "mimetype", zipfile.ZIP_STORED)

    # META-INF
    z.write(f"{OUTPUT_DIR}/META-INF/container.xml", "META-INF/container.xml")

    # OEBPS
    z.write(f"{OUTPUT_DIR}/OEBPS/content.opf", "OEBPS/content.opf")
    z.write(f"{OUTPUT_DIR}/OEBPS/toc.ncx", "OEBPS/toc.ncx")
    z.write(f"{OUTPUT_DIR}/OEBPS/css/style.css", "OEBPS/css/style.css")

    if toc_page_id:
        z.write(
            f"{OUTPUT_DIR}/OEBPS/text/{toc_page_id}.xhtml",
            f"OEBPS/text/{toc_page_id}.xhtml",
        )

    # XHTML файлы
    for item in book_items:
        xhtml_file = f'{OUTPUT_DIR}/OEBPS/{item["href"]}'
        z.write(xhtml_file, f'OEBPS/{item["href"]}')

# Очищаем временные файлы
cleanup_temp_files()

# Статистика
file_size = os.path.getsize(EPUB_OUTPUT) / (1024 * 1024)

print("\n" + "=" * 70)
print("✅ EPUB УСПЕШНО СОЗДАН!")
print("=" * 70)
print(f"📍 Файл:     {EPUB_OUTPUT}")
print(f"📊 Размер:   {file_size:.2f} MB")
print(f"📚 Глав:     {len(book_items)}")
print(f"📖 Слов:     {word_count:,}")
if toc_entries:
    print(f"📑 Оглавл.:  Отдельное + NCX ({len(toc_entries)} пунктов из PDF)")
else:
    print(f"📑 Оглавл.:  Отдельное + NCX ({len(book_items)} пунктов по главам)")
print("🧹 Временные файлы: удалены")
print("=" * 70)
print("\n✨ Готово! Откройте в:")
print("   • Apple Books (macOS/iOS)")
print("   • Kindle (преобразовать в AZW через Calibre)")
print("   • Librera/Moon+ Reader (Android)")
print("   • Calibre (любая ОС)")
print("\n🎉 Наслаждайтесь чтением!")
