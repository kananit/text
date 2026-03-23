import re
from collections import Counter

from config import (
    MINOR_SUBHEADING_ENABLED,
    MINOR_SUBHEADING_MAX_LEN,
    MINOR_SUBHEADING_UPPERCASE_RATIO,
)

from .cleaning import clean_line, clean_paragraph


def split_columns(line: str) -> list[str]:
    raw_cells = re.split(r"\t+|\s{2,}", line.strip())
    return [clean_paragraph(cell) for cell in raw_cells if cell.strip()]


def is_minor_subheading(text: str) -> bool:
    if not MINOR_SUBHEADING_ENABLED:
        return False

    letters = re.findall(r"[A-Za-zА-Яа-яЁё]", text)
    if len(letters) < 8:
        return False

    uppercase = [ch for ch in letters if ch.isupper()]
    uppercase_ratio = len(uppercase) / len(letters)
    return uppercase_ratio >= MINOR_SUBHEADING_UPPERCASE_RATIO


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
            if (
                one
                and len(one) < MINOR_SUBHEADING_MAX_LEN
                and not re.search(r"[.!?…:»\"'\u201d\u2019]$", one)
            ):
                if is_minor_subheading(one):
                    blocks.append({"type": "h3_small", "text": one})
                else:
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
