import re
from collections import Counter

from config import (
    MINOR_SUBHEADING_ENABLED,
    MINOR_SUBHEADING_MAX_LEN,
    MINOR_SUBHEADING_UPPERCASE_RATIO,
)

from .cleaning import clean_line, clean_paragraph, is_chapter_heading


_LIST_MARKER_RE = re.compile(
    r"^(?P<marker>(?:\(\d{1,3}\)|\d{1,3}[\.)]|\([A-Za-zА-Яа-яЁё]\)|[A-Za-zА-Яа-яЁё][\.)]))\s+(?P<rest>.+)$"
)


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
    italic_lead_prefixes = (
        "извлечения ",
        "извлечение ",
        "из статьи",
        "цитата",
        "примечание ",
        "перепечатано ",
        "опубликовано ",
    )

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
        if line_count == 1:
            if re.search(r"[;:!?…\)]", stripped):
                return False
        elif re.search(r"[!?…\)]", stripped):
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
        if _LIST_MARKER_RE.match(stripped):
            return False
        if stripped[0] in (
            '"',
            "\u201c",
        ):  # typographic or straight left quote → quoted speech, not heading
            return False

        ends_with_strong_terminal_punct = bool(
            re.search(r"[!?…:;»\"'\u201d\u2019]$", stripped)
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

    def starts_like_paragraph_sentence(text: str) -> bool:
        stripped = text.lstrip()
        if not stripped:
            return False
        return bool(re.match(r'^[A-ZА-ЯЁ"«(]', stripped))

    def marker_kind(marker: str) -> str:
        if re.search(r"\d", marker):
            return "ordered"
        return "alpha"

    def marker_start_number(marker: str) -> int | None:
        match = re.search(r"\d+", marker)
        if not match:
            return None
        try:
            return int(match.group(0))
        except ValueError:
            return None

    def build_heading_block(text: str) -> dict:
        cleaned_heading = strip_trailing_subheading_period(text)
        if is_minor_subheading(cleaned_heading):
            return {"type": "h3_small", "text": cleaned_heading}
        return {"type": "h2", "text": cleaned_heading}

    def is_italic_lead_candidate(lines_after_heading: list[str]) -> bool:
        if not lines_after_heading or len(lines_after_heading) > 4:
            return False
        joined = clean_paragraph(" ".join(lines_after_heading))
        if not joined:
            return False
        if len(joined) > 260:
            return False
        if _LIST_MARKER_RE.match(lines_after_heading[0]):
            return False
        first_non_space = joined.lstrip()
        if first_non_space:
            lowered = first_non_space.lower()
            has_editorial_prefix = any(
                lowered.startswith(prefix) for prefix in italic_lead_prefixes
            )
            if not first_non_space.startswith("(") and not has_editorial_prefix:
                return False
        if len(lines_after_heading) == 1 and not joined.startswith("("):
            return False
        if re.search(r"[!?…:;]$", joined):
            return False
        return True

    def build_list_block(block_lines: list[str]) -> dict | None:
        items: list[dict[str, str]] = []
        current_item: dict[str, str] | None = None
        marker_count = 0
        list_kind: str | None = None
        list_start: int | None = None

        for raw_line in block_lines:
            normalized = clean_paragraph(raw_line)
            if not normalized:
                continue

            marker_match = _LIST_MARKER_RE.match(normalized)
            if marker_match:
                marker = marker_match.group("marker")
                rest = marker_match.group("rest")

                current_kind = marker_kind(marker)
                if (
                    current_item
                    and list_kind == "ordered"
                    and current_kind == "alpha"
                    and marker.startswith("(")
                    and re.search(r"\([A-Za-zА-Яа-яЁё]\)", current_item["text"])
                ):
                    current_item["text"] = f"{current_item['text']} {marker} {rest}"
                    continue

                if current_item:
                    items.append(current_item)
                current_item = {"marker": marker, "text": rest}

                if list_kind is None:
                    list_kind = current_kind
                    if current_kind == "ordered":
                        list_start = marker_start_number(marker)
                elif current_kind != list_kind:
                    list_kind = "mixed"

                marker_count += 1
                continue

            if current_item:
                current_item["text"] = f"{current_item['text']} {normalized}"
            else:
                return None

        if current_item:
            items.append(current_item)

        if marker_count < 2:
            return None

        result = {
            "type": "list",
            "ordered": list_kind == "ordered",
            "show_markers": list_kind != "ordered",
            "items": items,
        }
        if list_kind == "ordered" and list_start is not None:
            result["start"] = list_start
        return result

    def split_prefix_and_list(block_lines: list[str]) -> tuple[list[str], dict] | None:
        first_marker_index = None
        for index, raw_line in enumerate(block_lines):
            normalized = clean_paragraph(raw_line)
            if _LIST_MARKER_RE.match(normalized):
                first_marker_index = index
                break

        if first_marker_index is None or first_marker_index == 0:
            return None

        prefix_lines = [
            line for line in block_lines[:first_marker_index] if line.strip()
        ]
        list_lines = block_lines[first_marker_index:]
        list_block = build_list_block(list_lines)
        if not prefix_lines or not list_block:
            return None

        return prefix_lines, list_block

    def split_list_and_tail(block_lines: list[str]) -> tuple[dict, list[str]] | None:
        marker_count = 0
        current_item_text = ""

        for index, raw_line in enumerate(block_lines):
            normalized = clean_paragraph(raw_line)
            if not normalized:
                continue

            marker_match = _LIST_MARKER_RE.match(normalized)
            if marker_match:
                marker_count += 1
                current_item_text = marker_match.group("rest")
                continue

            if marker_count >= 2 and current_item_text:
                item_looks_complete = bool(re.search(r"[.!?…]$", current_item_text))
                if item_looks_complete and starts_like_paragraph_sentence(normalized):
                    list_lines = block_lines[:index]
                    tail_lines = [line for line in block_lines[index:] if line.strip()]
                    list_block = build_list_block(list_lines)
                    if list_block and tail_lines:
                        return list_block, tail_lines

            if current_item_text:
                current_item_text = clean_paragraph(f"{current_item_text} {normalized}")

        return None

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

        if len(non_empty) >= 3:
            heading_candidate = clean_paragraph(non_empty[0])
            tail_lines = [
                clean_paragraph(line) for line in non_empty[1:] if line.strip()
            ]
            if (
                heading_candidate.endswith(".")
                and is_subheading_candidate(heading_candidate, 1)
                and is_italic_lead_candidate(tail_lines)
            ):
                blocks.append(build_heading_block(heading_candidate))
                blocks.append(
                    {"type": "p_italic", "text": clean_paragraph(" ".join(tail_lines))}
                )
                return

        if len(non_empty) >= 2:
            heading_candidate = clean_paragraph(non_empty[0])
            tail_lines = [
                clean_paragraph(line) for line in non_empty[1:] if line.strip()
            ]
            if (
                heading_candidate.endswith(".")
                and is_subheading_candidate(heading_candidate, 1)
                and tail_lines
                and starts_like_paragraph_sentence(tail_lines[0])
                and not is_italic_lead_candidate(tail_lines)
                and not _LIST_MARKER_RE.match(tail_lines[0])
            ):
                blocks.append(build_heading_block(heading_candidate))
                blocks.append(
                    {"type": "p", "text": clean_paragraph(" ".join(tail_lines))}
                )
                return

        if len(non_empty) == 3:
            combined_three_line_heading = clean_paragraph(" ".join(non_empty))
            second_line = clean_paragraph(non_empty[1])
            third_line = clean_paragraph(non_empty[2])
            if (
                not _LIST_MARKER_RE.match(second_line)
                and not _LIST_MARKER_RE.match(third_line)
                and not third_line.startswith("(")
                and is_subheading_candidate(combined_three_line_heading, 3)
            ):
                blocks.append(build_heading_block(combined_three_line_heading))
                return

        if len(non_empty) >= 3:
            first_line = clean_paragraph(non_empty[0])
            second_line = clean_paragraph(non_empty[1])
            if second_line and not _LIST_MARKER_RE.match(second_line):
                combined_heading = clean_paragraph(f"{first_line} {second_line}")
                tail_lines = [
                    clean_paragraph(line) for line in non_empty[2:] if line.strip()
                ]
                if is_subheading_candidate(
                    combined_heading, 2
                ) and is_italic_lead_candidate(tail_lines):
                    blocks.append(build_heading_block(combined_heading))
                    blocks.append(
                        {
                            "type": "p_italic",
                            "text": clean_paragraph(" ".join(tail_lines)),
                        }
                    )
                    return

        if len(non_empty) >= 2:
            heading_candidate = clean_paragraph(non_empty[0])
            tail_lines = [
                clean_paragraph(line) for line in non_empty[1:] if line.strip()
            ]
            if (
                heading_candidate.endswith(".")
                and is_subheading_candidate(heading_candidate, 1)
                and is_italic_lead_candidate(tail_lines)
            ):
                blocks.append(build_heading_block(heading_candidate))
                blocks.append(
                    {"type": "p_italic", "text": clean_paragraph(" ".join(tail_lines))}
                )
                return

        if len(non_empty) >= 3:
            heading_candidate = clean_paragraph(non_empty[0])
            tail_lines = non_empty[1:]
            if _LIST_MARKER_RE.match(clean_paragraph(tail_lines[0])):
                if is_subheading_candidate(heading_candidate, 1):
                    blocks.append(build_heading_block(heading_candidate))

                    list_block = build_list_block(tail_lines)
                    if list_block:
                        blocks.append(list_block)
                        return

                    blocks.append(
                        {"type": "p", "text": clean_paragraph(" ".join(tail_lines))}
                    )
                    return

        prefix_and_list = split_prefix_and_list(non_empty)
        if prefix_and_list:
            prefix_lines, list_block = prefix_and_list
            blocks.append(
                {"type": "p", "text": clean_paragraph(" ".join(prefix_lines))}
            )
            blocks.append(list_block)
            return

        list_and_tail = split_list_and_tail(non_empty)
        if list_and_tail:
            list_block, tail_lines = list_and_tail
            blocks.append(list_block)

            tail_prefix_and_list = split_prefix_and_list(tail_lines)
            if tail_prefix_and_list:
                tail_prefix_lines, tail_list_block = tail_prefix_and_list
                blocks.append(
                    {"type": "p", "text": clean_paragraph(" ".join(tail_prefix_lines))}
                )
                blocks.append(tail_list_block)
                return

            tail_list_block = build_list_block(tail_lines)
            if tail_list_block:
                blocks.append(tail_list_block)
                return

            blocks.append({"type": "p", "text": clean_paragraph(" ".join(tail_lines))})
            return

        list_block = build_list_block(non_empty)
        if list_block:
            blocks.append(list_block)
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
