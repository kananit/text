import re
from collections import Counter

from models import Chapter, TocEntry


def detect_language(text: str) -> str:
    cyr = len(re.findall(r"[А-Яа-яЁё]", text))
    lat = len(re.findall(r"[A-Za-z]", text))
    return "ru" if cyr > lat else "en"


def clean_line(text: str) -> str:
    text = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]", "", text)
    return text.rstrip()


def clean_paragraph(text: str) -> str:
    text = clean_line(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_title(title: str) -> str:
    title = clean_paragraph(title)
    title = re.sub(r"\s{2,}", " ", title)
    return title[:120]


def is_chapter_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False

    patterns = [
        r"^(глава|часть|раздел)\s+[0-9ivxlcdm]+(?:\s*[\.:\-)])?(?:\s+.*)?$",
        r"^(chapter|part|section)\s+[0-9ivxlcdm]+(?:\s*[\.:\-)])?(?:\s+.*)?$",
        r"^(приложение|appendix)\s+[a-zа-я0-9ivxlcdm]+(?:\s*[\.:\-)])?(?:\s+.*)?$",
    ]
    return any(re.match(pattern, stripped, re.IGNORECASE) for pattern in patterns)


def chapter_number_key(title: str):
    match = re.search(
        r"(?:глава|часть|раздел|chapter|part|section)\s+([0-9ivxlcdm]+)",
        title,
        re.IGNORECASE,
    )
    if not match:
        return None
    return match.group(1).lower()


def extract_toc_entries(text: str) -> list[TocEntry]:
    lines = [clean_line(line) for line in text.split("\n")]
    toc_header = re.compile(
        r"^(содержание|оглавление|contents|table of contents)\s*$",
        re.IGNORECASE,
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

    entries: list[TocEntry] = []
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
        if key in seen or len(title) < 4:
            continue

        seen.add(key)
        entries.append(TocEntry(title=title, page=page))

    return entries


def resolve_title_with_toc(
    raw_title: str, toc_entries: list[TocEntry], used_indices: set[int]
) -> str:
    normalized = normalize_title(raw_title)
    lowered = normalized.lower()

    for idx, item in enumerate(toc_entries):
        if idx in used_indices:
            continue
        toc_title = item.title.lower()
        if (
            lowered == toc_title
            or lowered.startswith(toc_title)
            or toc_title.startswith(lowered)
        ):
            used_indices.add(idx)
            return item.title

    number_key = chapter_number_key(normalized)
    if number_key:
        for idx, item in enumerate(toc_entries):
            if idx in used_indices:
                continue
            item_key = chapter_number_key(item.title)
            if item_key and item_key == number_key:
                used_indices.add(idx)
                return item.title

    return normalized


def identify_chapters(text: str, toc_entries: list[TocEntry]) -> list[Chapter]:
    lines = [clean_line(line) for line in text.split("\n")]
    chapters: list[Chapter] = []
    current_title = None
    current_content: list[str] = []
    used_toc_indices: set[int] = set()

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
                    Chapter(
                        title=current_title, content="\n".join(current_content).strip()
                    )
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
            chapters.append(Chapter(title=current_title, content=final_content))

    return chapters


def fallback_chapters(text: str, language: str) -> list[Chapter]:
    chunk_size = 60000
    chunks = []
    for idx in range(0, len(text), chunk_size):
        chunk = text[idx : idx + chunk_size].strip()
        if len(chunk) > 1200:
            chunks.append(chunk)

    part_prefix = "Часть" if language == "ru" else "Part"
    return [
        Chapter(title=f"{part_prefix} {idx + 1}", content=chunk)
        for idx, chunk in enumerate(chunks)
    ]


def split_columns(line: str) -> list[str]:
    raw_cells = re.split(r"\t+|\s{2,}", line.strip())
    return [clean_paragraph(cell) for cell in raw_cells if cell.strip()]


def parse_table_rows(block_lines: list[str]):
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


def chapter_blocks(content: str) -> list[dict]:
    lines = [clean_line(line) for line in content.split("\n")]
    blocks = []
    buffer_lines: list[str] = []

    def flush_buffer() -> None:
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
