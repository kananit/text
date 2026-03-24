import re
from collections import Counter

from config import (
    MINOR_SUBHEADING_ENABLED,
    MINOR_SUBHEADING_MAX_LEN,
    MINOR_SUBHEADING_UPPERCASE_RATIO,
)

from .cleaning import clean_line, clean_paragraph, is_chapter_heading


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

    def strip_trailing_subheading_period(text: str) -> str:
        stripped = clean_paragraph(text)
        stripped = re.sub(r"\.(?=(?:[\"'»”’)]*)\s*$)", "", stripped)
        return stripped.strip()

    def is_period_terminated_heading_candidate(text: str, line_count: int) -> bool:
        stripped = text.strip()
        if not stripped.endswith("."):
            return False

        words = [word for word in re.split(r"\s+", stripped.rstrip(".")) if word]
        if len(words) < 2 or len(words) > 14:
            return False
        if re.search(r"[;:!?…\)]", stripped):
            return False
        if re.search(r"\d{4,}|https?://|www\.", stripped, flags=re.IGNORECASE):
            return False

        first_word = words[0].lstrip('"«(“”')
        if not first_word:
            return False
        if not re.match(r"^[A-ZА-ЯЁ]", first_word):
            return False

        if line_count == 1 and not any(ch in stripped for ch in [",", "«", "»", '"']):
            if len(words) > 7:
                return False

        if line_count > 3:
            return False

        return True

    def is_subheading_candidate(text: str, line_count: int) -> bool:
        stripped = text.strip()
        if not stripped:
            return False
        if len(stripped) >= MINOR_SUBHEADING_MAX_LEN:
            return False
        if is_chapter_heading(stripped):
            return False

        ends_with_strong_terminal_punct = bool(
            re.search(r"[!?…:»\"'\u201d\u2019]$", stripped)
        )
        if ends_with_strong_terminal_punct:
            return False

        if stripped.endswith("."):
            return is_period_terminated_heading_candidate(stripped, line_count)

        return line_count <= 3

    def should_merge_soft_break(prev_line: str, next_line: str) -> bool:
        prev = prev_line.strip()
        nxt = next_line.strip()
        if not prev or not nxt:
            return False
        if is_chapter_heading(prev) or is_chapter_heading(nxt):
            return False
        if re.search(r"[.!?…:;»\"'\u201d\u2019\)]$", prev):
            return False
        return bool(re.match(r"^[a-zа-яё0-9\"'«\(]", nxt))

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

        if 1 <= len(non_empty) <= 3:
            candidate = clean_paragraph(" ".join(non_empty))
            if is_subheading_candidate(candidate, len(non_empty)):
                cleaned_heading = strip_trailing_subheading_period(candidate)
                if is_minor_subheading(cleaned_heading):
                    blocks.append({"type": "h3_small", "text": cleaned_heading})
                else:
                    blocks.append({"type": "h2", "text": cleaned_heading})
                return

        paragraph = clean_paragraph(" ".join(non_empty))
        if paragraph:
            blocks.append({"type": "p", "text": paragraph})

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip() == "":
            prev_non_empty = None
            if buffer_lines:
                for candidate in reversed(buffer_lines):
                    if candidate.strip():
                        prev_non_empty = candidate
                        break

            next_non_empty = None
            j = i + 1
            while j < len(lines):
                if lines[j].strip():
                    next_non_empty = lines[j]
                    break
                j += 1

            if (
                prev_non_empty is not None
                and next_non_empty is not None
                and should_merge_soft_break(prev_non_empty, next_non_empty)
            ):
                i += 1
                continue

            flush_buffer()
            i += 1
            continue

        buffer_lines.append(line)
        i += 1

    flush_buffer()
    return blocks
