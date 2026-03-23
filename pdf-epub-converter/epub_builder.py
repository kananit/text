import re
import shutil
import zipfile
from pathlib import Path

from config import (
    BUILD_DIR,
    COVER_MEDIA_TYPES,
)
from models import BookItem, BookMetadata, Chapter, TocEntry
from parsing import chapter_blocks


def escape_xml(text: str) -> str:
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    return text


def strip_leading_chapter_number(title: str) -> str:
    return re.sub(r"^\s*\d+\.\s+", "", title).strip()


def render_blocks_to_xhtml(blocks: list[dict]) -> str:
    chunks = []
    for block in blocks:
        if block["type"] == "p":
            chunks.append(f"    <p>{escape_xml(block['text'])}</p>")
        elif block["type"] == "h2":
            chunks.append(f"    <h2>{escape_xml(block['text'])}</h2>")
        elif block["type"] == "h3_small":
            chunks.append(
                f"    <h4 class=\"minor-subtitle\">{escape_xml(block['text'])}</h4>"
            )
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
        else [
            TocEntry(title=strip_leading_chapter_number(item.title), page="")
            for item in book_items
        ]
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
    style_src = Path(__file__).with_name("style.css")
    dest = BUILD_DIR / "OEBPS" / "css" / "style.css"
    shutil.copy2(style_src, dest)


def build_cover_page(cover_path: Path, language: str) -> str:
    """Копирует обложку в EPUB и создаёт cover-page.xhtml. Возвращает ID страницы."""
    dest = BUILD_DIR / "OEBPS" / "images" / cover_path.name
    shutil.copy2(cover_path, dest)

    cover_title = "Обложка" if language == "ru" else "Cover"
    cover_xhtml = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{language}">
<head>
  <title>{cover_title}</title>
  <link rel="stylesheet" type="text/css" href="../css/style.css"/>
  <style type="text/css">
    html, body {{ margin: 0; padding: 0; height: 100%; width: 100%; }}
    body {{ display: flex; align-items: center; justify-content: center; }}
    div {{ width: 100%; height: 100%; }}
    .cover-img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
  </style>
</head>
<body>
  <div>
    <img src="../images/{cover_path.name}" alt="{cover_title}" class="cover-img"/>
  </div>
</body>
</html>"""
    (BUILD_DIR / "OEBPS" / "text" / "cover-page.xhtml").write_text(
        cover_xhtml, encoding="utf-8"
    )
    return "cover-page"


def write_opf(
    book_items: list[BookItem],
    toc_page_id: str,
    language: str,
    metadata: BookMetadata,
    cover_path: Path | None = None,
) -> None:
    manifest = "\n".join(
        [
            f'    <item id="{item.id}" href="{item.href}" media-type="application/xhtml+xml"/>'
            for item in book_items
        ]
    )
    spine = "\n".join([f'    <itemref idref="{item.id}"/>' for item in book_items])
    extra_manifest = f'    <item id="{toc_page_id}" href="text/{toc_page_id}.xhtml" media-type="application/xhtml+xml"/>\n'
    extra_spine = f'    <itemref idref="{toc_page_id}"/>\n'

    cover_meta = ""
    cover_manifest = ""
    cover_spine = ""
    if cover_path is not None:
        media_type = COVER_MEDIA_TYPES.get(cover_path.suffix.lower(), "image/jpeg")
        cover_meta = '    <meta name="cover" content="cover-image"/>\n'
        cover_manifest = (
            f'    <item id="cover-image" href="images/{cover_path.name}" media-type="{media_type}"/>\n'
            f'    <item id="cover-page" href="text/cover-page.xhtml" media-type="application/xhtml+xml"/>\n'
        )
        cover_spine = '    <itemref idref="cover-page"/>\n'

    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uuid_id" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
        <dc:title>{escape_xml(metadata.title)}</dc:title>
        <dc:creator>{escape_xml(metadata.creator)}</dc:creator>
        <dc:date>{escape_xml(metadata.year)}</dc:date>
        <dc:publisher>{escape_xml(metadata.publisher)}</dc:publisher>
    <dc:language>{language}</dc:language>
        <dc:identifier id="uuid_id">book-{escape_xml(metadata.year)}</dc:identifier>
        <dc:description>{escape_xml(metadata.description)}</dc:description>
    <dc:rights>Public Domain</dc:rights>
{cover_meta}  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtb+xml"/>
    <item id="css" href="css/style.css" media-type="text/css"/>
{cover_manifest}{extra_manifest}{manifest}  </manifest>
  <spine toc="ncx">
{cover_spine}{extra_spine}{spine}  </spine>
</package>"""
    (BUILD_DIR / "OEBPS" / "content.opf").write_text(opf, encoding="utf-8")


def write_ncx(
    book_items: list[BookItem],
    toc_page_id: str,
    language: str,
    metadata: BookMetadata,
) -> None:
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
            BookItem(
                id=item.id,
                title=strip_leading_chapter_number(item.title),
                href=item.href,
                order=index + 2,
            )
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
    <docTitle><text>{escape_xml(metadata.title)}</text></docTitle>
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


def package_epub(
    book_items: list[BookItem],
    toc_page_id: str,
    output_path: Path,
    cover_path: Path | None = None,
) -> None:
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(BUILD_DIR / "mimetype", "mimetype", zipfile.ZIP_STORED)
        archive.write(
            BUILD_DIR / "META-INF" / "container.xml", "META-INF/container.xml"
        )
        archive.write(BUILD_DIR / "OEBPS" / "content.opf", "OEBPS/content.opf")
        archive.write(BUILD_DIR / "OEBPS" / "toc.ncx", "OEBPS/toc.ncx")
        archive.write(BUILD_DIR / "OEBPS" / "css" / "style.css", "OEBPS/css/style.css")
        if cover_path is not None:
            archive.write(
                BUILD_DIR / "OEBPS" / "images" / cover_path.name,
                f"OEBPS/images/{cover_path.name}",
            )
            archive.write(
                BUILD_DIR / "OEBPS" / "text" / "cover-page.xhtml",
                "OEBPS/text/cover-page.xhtml",
            )
        archive.write(
            BUILD_DIR / "OEBPS" / "text" / f"{toc_page_id}.xhtml",
            f"OEBPS/text/{toc_page_id}.xhtml",
        )
        for item in book_items:
            archive.write(BUILD_DIR / "OEBPS" / item.href, f"OEBPS/{item.href}")
