import zipfile
from datetime import datetime

from config import (
    BOOK_CONTRIBUTOR,
    BOOK_CREATOR,
    BOOK_DESCRIPTION,
    BOOK_TITLE,
    BUILD_DIR,
    EPUB_OUTPUT,
)
from models import BookItem, Chapter, TocEntry
from parsing import chapter_blocks


def escape_xml(text: str) -> str:
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    return text


def render_blocks_to_xhtml(blocks: list[dict]) -> str:
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


def build_chapter_documents(chapters: list[Chapter], language: str) -> list[BookItem]:
    book_items: list[BookItem] = []
    for idx, chapter in enumerate(chapters, 1):
        file_id = f"chapter-{idx:03d}"
        title = chapter.title.strip()
        html_content = render_blocks_to_xhtml(chapter_blocks(chapter.content))

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

        xhtml_file = BUILD_DIR / "OEBPS" / "text" / f"{file_id}.xhtml"
        xhtml_file.write_text(xhtml, encoding="utf-8")
        book_items.append(
            BookItem(id=file_id, href=f"text/{file_id}.xhtml", title=title, order=idx)
        )

    return book_items


def build_toc_page(
    book_items: list[BookItem], toc_entries: list[TocEntry], language: str
) -> str:
    toc_page_id = "parsed-toc"
    toc_rows = []
    toc_source = (
        toc_entries
        if toc_entries
        else [TocEntry(title=item.title, page="") for item in book_items]
    )

    for idx, entry in enumerate(toc_source, 1):
        if idx <= len(book_items):
            target = f"chapter-{idx:03d}.xhtml"
            title_html = f'<a href="{target}">{escape_xml(entry.title)}</a>'
        else:
            title_html = escape_xml(entry.title)
        page = escape_xml(entry.page)
        toc_rows.append(
            f'    <li><span class="toc-title">{title_html}</span><span class="toc-page">{page}</span></li>'
        )

    title_text = "Оглавление" if language == "ru" else "Contents"
    toc_xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xml:lang="{language}" xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
<meta charset="UTF-8"/>
<title>{title_text}</title>
<link rel="stylesheet" href="../css/style.css" type="text/css"/>
</head>
<body>
<div class="chapter">
<h1 class="chapter-title">{title_text}</h1>
<ol class="toc-list">
{'\n'.join(toc_rows)}
</ol>
</div>
</body>
</html>"""

    (BUILD_DIR / "OEBPS" / "text" / f"{toc_page_id}.xhtml").write_text(
        toc_xhtml,
        encoding="utf-8",
    )
    return toc_page_id


def write_stylesheet() -> None:
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
    (BUILD_DIR / "OEBPS" / "css" / "style.css").write_text(css, encoding="utf-8")


def write_opf(book_items: list[BookItem], toc_page_id: str, language: str) -> None:
    manifest = "\n".join(
        [
            f'    <item id="{item.id}" href="{item.href}" media-type="application/xhtml+xml"/>'
            for item in book_items
        ]
    )
    spine = "\n".join([f'    <itemref idref="{item.id}"/>' for item in book_items])
    extra_manifest = f'    <item id="{toc_page_id}" href="text/{toc_page_id}.xhtml" media-type="application/xhtml+xml"/>\n'
    extra_spine = f'    <itemref idref="{toc_page_id}"/>\n'

    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uuid_id" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>{BOOK_TITLE}</dc:title>
    <dc:creator>{BOOK_CREATOR}</dc:creator>
    <dc:contributor>{BOOK_CONTRIBUTOR}</dc:contributor>
    <dc:date>{datetime.now().strftime('%Y-%m-%d')}</dc:date>
    <dc:language>{language}</dc:language>
    <dc:identifier id="uuid_id">war-with-saints-{datetime.now().strftime('%Y%m%d%H%M%S')}</dc:identifier>
    <dc:description>{BOOK_DESCRIPTION}</dc:description>
    <dc:rights>Public Domain</dc:rights>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtb+xml"/>
    <item id="css" href="css/style.css" media-type="text/css"/>
{extra_manifest}{manifest}  </manifest>
  <spine toc="ncx">
{extra_spine}{spine}  </spine>
</package>"""
    (BUILD_DIR / "OEBPS" / "content.opf").write_text(opf, encoding="utf-8")


def write_ncx(book_items: list[BookItem], toc_page_id: str, language: str) -> None:
    nav_source_items = [
        BookItem(
            id=toc_page_id,
            title="Оглавление" if language == "ru" else "Contents",
            href=f"text/{toc_page_id}.xhtml",
            order=1,
        )
    ]
    nav_source_items.extend(
        [
            BookItem(id=item.id, title=item.title, href=item.href, order=index + 2)
            for index, item in enumerate(book_items)
        ]
    )

    nav_points = "\n".join(
        [
            f"""    <navPoint id="{item.id}" playOrder="{item.order}">
      <navLabel><text>{escape_xml(item.title)}</text></navLabel>
      <content src="{item.href}"/>
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
  <docTitle><text>{BOOK_TITLE}</text></docTitle>
  <navMap>
{nav_points}  </navMap>
</ncx>"""
    (BUILD_DIR / "OEBPS" / "toc.ncx").write_text(ncx, encoding="utf-8")


def write_container() -> None:
    container = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""
    (BUILD_DIR / "META-INF" / "container.xml").write_text(container, encoding="utf-8")


def write_mimetype() -> None:
    (BUILD_DIR / "mimetype").write_text("application/epub+zip", encoding="utf-8")


def package_epub(book_items: list[BookItem], toc_page_id: str) -> None:
    with zipfile.ZipFile(EPUB_OUTPUT, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(BUILD_DIR / "mimetype", "mimetype", zipfile.ZIP_STORED)
        archive.write(
            BUILD_DIR / "META-INF" / "container.xml", "META-INF/container.xml"
        )
        archive.write(BUILD_DIR / "OEBPS" / "content.opf", "OEBPS/content.opf")
        archive.write(BUILD_DIR / "OEBPS" / "toc.ncx", "OEBPS/toc.ncx")
        archive.write(BUILD_DIR / "OEBPS" / "css" / "style.css", "OEBPS/css/style.css")
        archive.write(
            BUILD_DIR / "OEBPS" / "text" / f"{toc_page_id}.xhtml",
            f"OEBPS/text/{toc_page_id}.xhtml",
        )
        for item in book_items:
            archive.write(BUILD_DIR / "OEBPS" / item.href, f"OEBPS/{item.href}")
