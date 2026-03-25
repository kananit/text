import re
from collections import Counter
from dataclasses import dataclass
from typing import Callable

from config import (
    MINOR_SUBHEADING_ENABLED,
    MINOR_SUBHEADING_MAX_LEN,
    MINOR_SUBHEADING_UPPERCASE_RATIO,
)

from .cleaning import clean_line, clean_paragraph, is_chapter_heading


_LIST_MARKER_RE = re.compile(
    r"^(?P<marker>(?:\(\d{1,3}\)|\d{1,3}[\.)]|\([A-Za-zА-Яа-яЁё]\)|[A-Za-zА-Яа-яЁё][\.)]|[•●▪◦‣∙·]))\s+(?P<rest>.+)$"
)
_URL_OR_LONG_NUMBER_RE = re.compile(r"\d{4,}|https?://|www\.", re.IGNORECASE)
_UPPERCASE_START_RE = re.compile(r"^[A-ZА-ЯЁ]")
_LIST_TEXT_UPPER_START_RE = re.compile(r'^[A-ZА-ЯЁ"«(]')
_SOFT_BREAK_NEXT_START_RE = re.compile(r'^[a-zа-яё0-9"\'«\(]')
_STRONG_TERMINAL_PUNCT_RE = re.compile(r"[!?…:;»\"'\u201d\u2019]$")
_SOFT_BREAK_BLOCKING_PUNCT_RE = re.compile(r"[.!?…:;»\"'\u201d\u2019\)]$")
_PERIOD_HEADING_SINGLE_LINE_BLOCK_RE = re.compile(r"[;!?…\)]")
_PERIOD_HEADING_MULTI_LINE_BLOCK_RE = re.compile(r"[!?…\)]")
_ITALIC_LEAD_BLOCKING_PUNCT_RE = re.compile(r"[!?…:;]$")
_LIST_ITEM_COMPLETE_TERMINAL_RE = re.compile(r"[.!?…]$")
_HAS_DIGIT_RE = re.compile(r"\d")
_FIRST_NUMBER_RE = re.compile(r"\d+")
_ALPHA_PAREN_MARKER_RE = re.compile(r"\([A-Za-zА-Яа-яЁё]\)")
_INLINE_NUMERIC_MARKER_RE = re.compile(r"(?<!\S)\d{1,3}[\.)]\s+")
_STANDALONE_PAGE_NUMBER_RE = re.compile(r"^\d{1,4}$")
_OCR_ONE_MARKER_RE = re.compile(
    r"^(?P<alias>[Il|])\s*(?P<punct>[\.)])\s*(?P<rest>\S.*)$"
)


@dataclass
class ListParsingState:
    current_item: dict[str, str] | None = None
    current_item_text: str = ""
    current_marker: str = ""
    marker_count: int = 0
    list_kind: str | None = None
    list_start: int | None = None
    has_non_marker_continuation: bool = False
    is_numbered_list: bool = False


@dataclass(frozen=True)
class BlockRule:
    name: str
    handler: Callable[[list[str]], bool]


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
    bullet_markers = {"•", "●", "▪", "◦", "‣", "∙", "·"}
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
            if _PERIOD_HEADING_SINGLE_LINE_BLOCK_RE.search(stripped):
                return False
        elif _PERIOD_HEADING_MULTI_LINE_BLOCK_RE.search(stripped):
            return False
        if _URL_OR_LONG_NUMBER_RE.search(stripped):
            return False

        first_word = words[0].lstrip('"«(“”')
        if not first_word:
            return False
        if not _UPPERCASE_START_RE.match(first_word):
            return False

        if line_count == 1 and not any(ch in stripped for ch in [",", "«", "»", '"']):
            if len(words) > 7:
                return False

        if line_count > 3:
            return False

        return True

    def is_question_terminated_heading_candidate(text: str, line_count: int) -> bool:
        stripped = text.strip()
        if not stripped.endswith("?"):
            return False

        words = [word for word in re.split(r"\s+", stripped.rstrip("?")) if word]
        if len(words) < 2 or len(words) > 14:
            return False
        if line_count > 2:
            return False
        if _URL_OR_LONG_NUMBER_RE.search(stripped):
            return False

        first_word = words[0].lstrip('"«(“”')
        if not first_word or not _UPPERCASE_START_RE.match(first_word):
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
        if match_list_marker(stripped):
            return False
        if stripped[0] in (
            '"',
            "\u201c",
        ) and not stripped.endswith("."):
            return False

        ends_with_strong_terminal_punct = bool(
            _STRONG_TERMINAL_PUNCT_RE.search(stripped)
        )
        if ends_with_strong_terminal_punct:
            if stripped.endswith("?"):
                return is_question_terminated_heading_candidate(stripped, line_count)
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

        if _SOFT_BREAK_BLOCKING_PUNCT_RE.search(prev):
            return False
        return bool(_SOFT_BREAK_NEXT_START_RE.match(nxt))

    def starts_with_sentence_case(text: str) -> bool:
        stripped = text.lstrip()
        if not stripped:
            return False
        return bool(_LIST_TEXT_UPPER_START_RE.match(stripped))

    def marker_kind(marker: str) -> str:
        if marker in bullet_markers:
            return "bullet"
        if _HAS_DIGIT_RE.search(marker):
            return "ordered"
        return "alpha"

    def extract_marker_start_number(marker: str) -> int | None:
        match = _FIRST_NUMBER_RE.search(marker)
        if not match:
            return None
        try:
            return int(match.group(0))
        except ValueError:
            return None

    def is_standalone_numeric_marker(marker: str, rest: str) -> bool:
        """Numeric markers like (2), 2. require rest to start uppercase.
        Prevents inline enumerations 'text, (2) continue...' from being list items."""
        if re.match(r"^\(\d{1,3}\)$", marker):
            return False
        if re.match(r"^\d+\.$", marker):
            return bool(rest.strip())
        if _HAS_DIGIT_RE.search(marker):
            return bool(_LIST_TEXT_UPPER_START_RE.match(rest))
        return True

    def normalize_leading_numeric_marker_spacing(text: str) -> str:
        """Normalize malformed numeric markers like '1 .Text' -> '1. Text'."""
        match = re.match(r"^(?P<num>\d{1,3})\s*(?P<punct>[.)])\s*(?P<rest>\S.*)$", text)
        if not match:
            return text
        return f"{match.group('num')}{match.group('punct')} {match.group('rest')}"

    def normalize_leading_ocr_one_marker(text: str) -> str:
        """Normalize OCR-like leading markers such as 'I. text' or 'l. text' to '1. text'."""
        match = _OCR_ONE_MARKER_RE.match(text)
        if not match:
            return text
        return f"1{match.group('punct')} {match.group('rest')}"

    def match_list_marker(
        text: str,
        require_standalone_numeric: bool = False,
        allow_ocr_numeric_aliases: bool = False,
    ):
        normalized_text = normalize_leading_numeric_marker_spacing(text)
        if allow_ocr_numeric_aliases:
            normalized_text = normalize_leading_ocr_one_marker(normalized_text)
        marker_match = _LIST_MARKER_RE.match(normalized_text)
        if not marker_match:
            return None
        if require_standalone_numeric and not is_standalone_numeric_marker(
            marker_match.group("marker"), marker_match.group("rest")
        ):
            return None
        return marker_match

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
        if match_list_marker(lines_after_heading[0]):
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
        if _ITALIC_LEAD_BLOCKING_PUNCT_RE.search(joined):
            return False
        return True

    def extract_numbered_subheading_with_tail(
        block_lines: list[str],
    ) -> tuple[str, list[str]] | None:
        if not block_lines or len(block_lines) > 4:
            return None

        first_line = clean_paragraph(block_lines[0])
        first_match = match_list_marker(first_line)
        if not first_match:
            return None

        marker = first_match.group("marker")
        if not re.match(r"^\d+\.$", marker):
            return None

        heading_body_parts = [first_match.group("rest")]
        consumed = 1

        while consumed < len(block_lines):
            heading_body = clean_paragraph(" ".join(heading_body_parts))
            if heading_body.endswith("."):
                break

            next_line = clean_paragraph(block_lines[consumed])
            if not next_line or match_list_marker(next_line):
                return None
            heading_body_parts.append(next_line)
            consumed += 1

        heading_body = clean_paragraph(" ".join(heading_body_parts))
        if not heading_body.endswith("."):
            return None
        if not is_period_terminated_heading_candidate(heading_body, consumed):
            return None

        tail_lines = [
            clean_paragraph(line) for line in block_lines[consumed:] if line.strip()
        ]
        if tail_lines and match_list_marker(tail_lines[0]):
            return None
        if tail_lines and not is_italic_lead_candidate(tail_lines):
            return None

        heading_text = clean_paragraph(f"{marker} {heading_body}")
        return heading_text, tail_lines

    def build_list_block(block_lines: list[str]) -> dict | None:
        def restore_broken_numbered_list(
            items: list[dict[str, str]],
        ) -> tuple[list[dict[str, str]], int] | None:
            if len(items) < 2:
                return None

            marker_numbers = [
                extract_marker_start_number(item["marker"]) for item in items
            ]
            if any(number is None for number in marker_numbers):
                return None

            numbers = [number for number in marker_numbers if number is not None]
            if not numbers:
                return None
            if any(curr < prev for prev, curr in zip(numbers, numbers[1:])):
                return None

            break_count = sum(
                1 for prev, curr in zip(numbers, numbers[1:]) if curr != prev + 1
            )
            if break_count == 0:
                return items, numbers[0]

            if len(items) < 3:
                return None

            max_breaks = max(1, len(items) // 6)
            if break_count > max_breaks:
                return None

            repaired_items: list[dict[str, str]] = []
            start_number = numbers[0]
            for offset, item in enumerate(items):
                repaired_item = dict(item)
                repaired_item["marker"] = f"{start_number + offset}."
                repaired_items.append(repaired_item)

            return repaired_items, start_number

        def expand_inline_numeric_markers(line: str) -> list[str]:
            normalized = clean_paragraph(line)
            if not normalized:
                return []

            matches = list(_INLINE_NUMERIC_MARKER_RE.finditer(normalized))
            if len(matches) < 2 or matches[0].start() != 0:
                return [normalized]

            parts: list[str] = []
            for index, match in enumerate(matches):
                start = match.start()
                end = (
                    matches[index + 1].start()
                    if index + 1 < len(matches)
                    else len(normalized)
                )
                chunk = clean_paragraph(normalized[start:end])
                if chunk:
                    parts.append(chunk)

            return parts or [normalized]

        def split_embedded_next_ordered_marker(
            text: str,
            expected_number: int | None,
        ) -> list[str]:
            normalized = clean_paragraph(text)
            if not normalized or expected_number is None:
                return [normalized] if normalized else []

            marker_pattern = rf"(?P<prefix>.+?[.!?…])\s+(?P<marker>{expected_number}[\.)])\s*(?P<rest>\S.*)$"
            match = re.match(marker_pattern, normalized)
            if not match:
                return [normalized]

            prefix = clean_paragraph(match.group("prefix"))
            marker_line = normalize_leading_numeric_marker_spacing(
                f"{match.group('marker')} {match.group('rest')}"
            )
            result = []
            if prefix:
                result.append(prefix)
            if marker_line:
                result.extend(expand_inline_numeric_markers(marker_line))
            return result or [normalized]

        items: list[dict[str, str]] = []
        state = ListParsingState()

        for raw_line in block_lines:
            expanded_segments = expand_inline_numeric_markers(raw_line)
            processed_segments: list[str] = []
            for segment in expanded_segments:
                expected_next_number = None
                if state.current_item and state.list_kind == "ordered":
                    current_number = extract_marker_start_number(
                        state.current_item["marker"]
                    )
                    if current_number is not None:
                        expected_next_number = current_number + 1
                processed_segments.extend(
                    split_embedded_next_ordered_marker(segment, expected_next_number)
                )

            for normalized in processed_segments:
                if state.current_item and _STANDALONE_PAGE_NUMBER_RE.match(normalized):
                    continue

                marker_match = match_list_marker(
                    normalized,
                    require_standalone_numeric=True,
                    allow_ocr_numeric_aliases=True,
                )
                if marker_match:
                    marker = marker_match.group("marker")
                    rest = marker_match.group("rest")

                    current_kind = marker_kind(marker)
                    if (
                        state.current_item
                        and state.list_kind == "ordered"
                        and current_kind == "alpha"
                        and marker.startswith("(")
                        and _ALPHA_PAREN_MARKER_RE.search(state.current_item["text"])
                    ):
                        state.current_item["text"] = (
                            f"{state.current_item['text']} {marker} {rest}"
                        )
                        continue

                    if state.current_item:
                        items.append(state.current_item)
                    state.current_item = {"marker": marker, "text": rest}

                    if state.list_kind is None:
                        state.list_kind = current_kind
                        if current_kind == "ordered":
                            state.list_start = extract_marker_start_number(marker)
                    elif current_kind != state.list_kind:
                        state.list_kind = "mixed"

                    state.marker_count += 1
                    continue

                if state.current_item:
                    state.current_item["text"] = (
                        f"{state.current_item['text']} {normalized}"
                    )
                    state.has_non_marker_continuation = True
                else:
                    return None

        if state.current_item:
            items.append(state.current_item)

        if state.list_kind == "ordered":
            restored_numbered_list = restore_broken_numbered_list(items)
            if not restored_numbered_list:
                return None
            items, state.list_start = restored_numbered_list

        if state.marker_count < 2:
            return None

        result = {
            "type": "list",
            "ordered": state.list_kind == "ordered",
            "show_markers": state.list_kind not in {"ordered", "bullet"},
            "items": items,
        }
        if state.list_kind == "ordered" and state.list_start is not None:
            result["start"] = state.list_start
        return result

    def split_prefix_and_list(
        block_lines: list[str],
    ) -> tuple[list[str], dict, list[str]] | None:
        first_marker_index = None
        first_marker_match = None
        for index, raw_line in enumerate(block_lines):
            normalized = clean_paragraph(raw_line)
            m = match_list_marker(normalized, require_standalone_numeric=True)
            if m:
                first_marker_index = index
                first_marker_match = m
                break

        if first_marker_index is None or first_marker_index == 0:
            return None

        prefix_lines = [
            line for line in block_lines[:first_marker_index] if line.strip()
        ]
        if prefix_lines and first_marker_match:
            prefix_tail = clean_paragraph(prefix_lines[-1]).lower()
            marker = first_marker_match.group("marker")
            if marker.startswith("(") and _HAS_DIGIT_RE.search(marker):
                if prefix_tail.endswith(",") or prefix_tail.endswith("то есть,"):
                    return None

        list_lines = block_lines[first_marker_index:]
        list_block = build_list_block(list_lines)
        if not prefix_lines or not list_block:
            return None

        return prefix_lines, list_block, list_lines

    def split_list_and_tail(
        block_lines: list[str],
    ) -> tuple[dict, list[str], list[str]] | None:
        state = ListParsingState()

        for index, raw_line in enumerate(block_lines):
            normalized = clean_paragraph(raw_line)
            if not normalized:
                continue

            marker_match = match_list_marker(
                normalized,
                require_standalone_numeric=True,
                allow_ocr_numeric_aliases=True,
            )
            if marker_match:
                if (
                    state.marker_count >= 2
                    and state.is_numbered_list
                    and state.current_marker
                ):
                    current_number_match = _FIRST_NUMBER_RE.search(state.current_marker)
                    next_number_match = _FIRST_NUMBER_RE.search(
                        marker_match.group("marker")
                    )
                    if current_number_match and next_number_match:
                        current_number = int(current_number_match.group(0))
                        next_number = int(next_number_match.group(0))
                        if next_number != current_number + 1:
                            list_lines = block_lines[:index]
                            tail_lines = [
                                line for line in block_lines[index:] if line.strip()
                            ]
                            list_block = build_list_block(list_lines)
                            if list_block and tail_lines:
                                return list_block, list_lines, tail_lines

                state.marker_count += 1
                state.current_marker = marker_match.group("marker")
                state.current_item_text = marker_match.group("rest")
                if _HAS_DIGIT_RE.search(state.current_marker):
                    state.is_numbered_list = True
                continue

            if state.marker_count >= 2 and state.current_item_text:
                item_looks_complete = bool(
                    _LIST_ITEM_COMPLETE_TERMINAL_RE.search(state.current_item_text)
                )
                if item_looks_complete and starts_with_sentence_case(normalized):
                    tail_lines = [line for line in block_lines[index:] if line.strip()]

                    next_marker_match = None
                    for tail_raw_line in tail_lines:
                        tail_normalized = clean_paragraph(tail_raw_line)
                        tail_marker_match = match_list_marker(tail_normalized)
                        if tail_marker_match:
                            next_marker_match = tail_marker_match
                            break

                    if next_marker_match and state.is_numbered_list:
                        current_number_match = _FIRST_NUMBER_RE.search(
                            state.current_marker
                        )
                        next_number_match = _FIRST_NUMBER_RE.search(
                            next_marker_match.group("marker")
                        )
                        if current_number_match and next_number_match:
                            current_number = int(current_number_match.group(0))
                            next_number = int(next_number_match.group(0))
                            if next_number == current_number + 1:
                                state.current_item_text = clean_paragraph(
                                    f"{state.current_item_text} {normalized}"
                                )
                                continue

                    if next_marker_match and not state.is_numbered_list:
                        state.current_item_text = clean_paragraph(
                            f"{state.current_item_text} {normalized}"
                        )
                        continue

                    # For numbered lists, only split if the next line is a new marker
                    # Otherwise keep merging text - don't split the list
                    if state.is_numbered_list:
                        if match_list_marker(
                            clean_paragraph(tail_lines[0]) if tail_lines else ""
                        ):
                            list_lines = block_lines[:index]
                            list_block = build_list_block(list_lines)
                            if list_block and tail_lines:
                                return list_block, list_lines, tail_lines
                        list_lines = block_lines[:index]
                        list_block = build_list_block(list_lines)
                        if list_block and tail_lines:
                            return list_block, list_lines, tail_lines
                        continue
                    else:
                        list_lines = block_lines[:index]
                        list_block = build_list_block(list_lines)
                        if list_block and tail_lines:
                            return list_block, list_lines, tail_lines

            if state.current_item_text:
                state.current_item_text = clean_paragraph(
                    f"{state.current_item_text} {normalized}"
                )

        return None

    blocks = []
    buffer_lines: list[str] = []

    def split_last_list_item_overflow(
        source_lines: list[str],
        list_block: dict,
    ) -> tuple[dict, list[str]]:
        def split_after_first_sentence(text: str) -> tuple[str, list[str]]:
            normalized = clean_paragraph(text)
            if not normalized:
                return "", []

            sentence_match = re.match(
                r"^(?P<first>.+?[.!?…])(?=\s+[A-ZА-ЯЁ]|\s*$)(?:\s+(?P<tail>\S.*))?$",
                normalized,
            )
            if not sentence_match:
                return normalized, []

            kept = clean_paragraph(sentence_match.group("first"))
            tail = clean_paragraph(sentence_match.group("tail") or "")
            return kept, ([tail] if tail else [])

        if list_block.get("type") != "list":
            return list_block, []

        items = list_block.get("items") or []
        if len(items) < 2:
            return list_block, []

        normalized_lines = [
            clean_paragraph(line) for line in source_lines if clean_paragraph(line)
        ]
        marker_positions: list[tuple[int, str]] = []
        for index, normalized in enumerate(normalized_lines):
            marker_match = match_list_marker(
                normalized,
                require_standalone_numeric=True,
                allow_ocr_numeric_aliases=True,
            )
            if marker_match:
                marker_positions.append((index, marker_match.group("rest")))

        if len(marker_positions) < 2:
            return list_block, []

        last_marker_index, last_marker_rest = marker_positions[-1]
        trailing_lines = normalized_lines[last_marker_index + 1 :]
        last_item_text = clean_paragraph(items[-1].get("text", ""))

        has_overflow_lines = bool(trailing_lines)
        is_large_last_item = len(last_item_text) >= 260
        starts_like_new_paragraph = bool(
            trailing_lines and starts_with_sentence_case(trailing_lines[0])
        )

        if not has_overflow_lines and not is_large_last_item:
            return list_block, []

        if has_overflow_lines and not (is_large_last_item or starts_like_new_paragraph):
            return list_block, []

        kept_text = clean_paragraph(last_marker_rest) or last_item_text
        overflow_lines = [line for line in trailing_lines if line]

        if overflow_lines:
            sentence_kept_text, sentence_tail = split_after_first_sentence(
                clean_paragraph(" ".join([kept_text, *overflow_lines]))
            )
            if sentence_tail:
                kept_text = sentence_kept_text
                overflow_lines = sentence_tail
            elif not _LIST_ITEM_COMPLETE_TERMINAL_RE.search(kept_text):
                return list_block, []
        elif len(kept_text) >= 220:
            sentence_kept_text, sentence_tail = split_after_first_sentence(kept_text)
            if sentence_tail:
                kept_text = sentence_kept_text
                overflow_lines = sentence_tail

        overflow_lines = [clean_paragraph(line) for line in overflow_lines if line]
        if not overflow_lines:
            return list_block, []

        updated_block = dict(list_block)
        updated_items = [dict(item) for item in items]
        updated_items[-1]["text"] = kept_text
        updated_block["items"] = updated_items
        return updated_block, overflow_lines

    def append_list_block_with_tail(source_lines: list[str], list_block: dict) -> None:
        adjusted_list_block, tail_paragraphs = split_last_list_item_overflow(
            source_lines,
            list_block,
        )
        blocks.append(adjusted_list_block)
        tail_text = clean_paragraph(" ".join(tail_paragraphs))
        if tail_text:
            blocks.append({"type": "p", "text": tail_text})

    def try_emit_table(non_empty: list[str]) -> bool:
        rows = parse_table_rows(non_empty)
        if not rows:
            return False
        blocks.append({"type": "table", "rows": rows})
        return True

    def try_emit_heading_dot_with_italic_tail(
        non_empty: list[str],
        min_lines: int,
    ) -> bool:
        if len(non_empty) < min_lines:
            return False
        heading_candidate = clean_paragraph(non_empty[0])
        tail_lines = [clean_paragraph(line) for line in non_empty[1:] if line.strip()]
        if (
            heading_candidate.endswith(".")
            and is_subheading_candidate(heading_candidate, 1)
            and is_italic_lead_candidate(tail_lines)
        ):
            blocks.append(build_heading_block(heading_candidate))
            blocks.append(
                {"type": "p_italic", "text": clean_paragraph(" ".join(tail_lines))}
            )
            return True
        return False

    def try_emit_heading_dot_with_paragraph_tail(non_empty: list[str]) -> bool:
        if len(non_empty) < 2:
            return False
        heading_candidate = clean_paragraph(non_empty[0])
        tail_lines = [clean_paragraph(line) for line in non_empty[1:] if line.strip()]
        if (
            heading_candidate.endswith(".")
            and is_subheading_candidate(heading_candidate, 1)
            and tail_lines
            and starts_with_sentence_case(tail_lines[0])
            and not is_italic_lead_candidate(tail_lines)
            and not match_list_marker(tail_lines[0])
        ):
            blocks.append(build_heading_block(heading_candidate))
            blocks.append({"type": "p", "text": clean_paragraph(" ".join(tail_lines))})
            return True
        return False

    def try_emit_chapter_heading_with_paragraph_tail(non_empty: list[str]) -> bool:
        if len(non_empty) < 2:
            return False

        heading_candidate = clean_paragraph(non_empty[0])
        if not is_chapter_heading(heading_candidate):
            return False

        tail_lines = [clean_paragraph(line) for line in non_empty[1:] if line.strip()]
        if not tail_lines:
            return False
        if match_list_marker(tail_lines[0]):
            return False

        blocks.append({"type": "h2", "text": heading_candidate})
        blocks.append({"type": "p", "text": clean_paragraph(" ".join(tail_lines))})
        return True

    def try_emit_numbered_subheading_with_tail(non_empty: list[str]) -> bool:
        numbered_subheading_with_tail = extract_numbered_subheading_with_tail(non_empty)
        if not numbered_subheading_with_tail:
            return False

        heading_text, tail_lines = numbered_subheading_with_tail
        blocks.append(build_heading_block(heading_text))

        if tail_lines:
            blocks.append(
                {
                    "type": "p_italic",
                    "text": clean_paragraph(" ".join(tail_lines)),
                }
            )
        return True

    def try_emit_three_line_heading(non_empty: list[str]) -> bool:
        if len(non_empty) != 3:
            return False
        combined_three_line_heading = clean_paragraph(" ".join(non_empty))
        second_line = clean_paragraph(non_empty[1])
        third_line = clean_paragraph(non_empty[2])
        if (
            not match_list_marker(second_line)
            and not match_list_marker(third_line)
            and not third_line.startswith("(")
            and is_subheading_candidate(combined_three_line_heading, 3)
        ):
            blocks.append(build_heading_block(combined_three_line_heading))
            return True
        return False

    def try_emit_two_line_heading_with_italic_tail(non_empty: list[str]) -> bool:
        if len(non_empty) < 3:
            return False
        first_line = clean_paragraph(non_empty[0])
        second_line = clean_paragraph(non_empty[1])
        if not second_line or match_list_marker(second_line):
            return False

        combined_heading = clean_paragraph(f"{first_line} {second_line}")
        tail_lines = [clean_paragraph(line) for line in non_empty[2:] if line.strip()]
        if is_subheading_candidate(combined_heading, 2) and is_italic_lead_candidate(
            tail_lines
        ):
            blocks.append(build_heading_block(combined_heading))
            blocks.append(
                {
                    "type": "p_italic",
                    "text": clean_paragraph(" ".join(tail_lines)),
                }
            )
            return True
        return False

    def try_emit_heading_plus_list(non_empty: list[str]) -> bool:
        if len(non_empty) < 3:
            return False
        heading_candidate = clean_paragraph(non_empty[0])
        tail_lines = non_empty[1:]
        if not match_list_marker(
            clean_paragraph(tail_lines[0]),
            allow_ocr_numeric_aliases=True,
        ):
            return False
        if not is_subheading_candidate(heading_candidate, 1):
            return False

        blocks.append(build_heading_block(heading_candidate))
        list_block = build_list_block(tail_lines)
        if list_block:
            append_list_block_with_tail(tail_lines, list_block)
            return True

        list_and_tail = split_list_and_tail(tail_lines)
        if list_and_tail:
            split_list_block, split_list_lines, remaining_tail_lines = list_and_tail
            append_list_block_with_tail(split_list_lines, split_list_block)
            if remaining_tail_lines:
                blocks.append(
                    {
                        "type": "p",
                        "text": clean_paragraph(" ".join(remaining_tail_lines)),
                    }
                )
            return True

        blocks.append({"type": "p", "text": clean_paragraph(" ".join(tail_lines))})
        return True

    def try_emit_prefix_and_list(non_empty: list[str]) -> bool:
        prefix_and_list = split_prefix_and_list(non_empty)
        if not prefix_and_list:
            return False

        prefix_lines, list_block, list_lines = prefix_and_list
        prefix_text = clean_paragraph(" ".join(prefix_lines))
        if len(prefix_lines) == 1 and is_subheading_candidate(prefix_text, 1):
            blocks.append(build_heading_block(prefix_text))
        else:
            blocks.append({"type": "p", "text": prefix_text})
        append_list_block_with_tail(list_lines, list_block)
        return True

    def try_emit_split_list_and_tail(non_empty: list[str]) -> bool:
        list_and_tail = split_list_and_tail(non_empty)
        if not list_and_tail:
            return False

        list_block, list_lines, tail_lines = list_and_tail
        append_list_block_with_tail(list_lines, list_block)

        tail_prefix_and_list = split_prefix_and_list(tail_lines)
        if tail_prefix_and_list:
            tail_prefix_lines, tail_list_block, tail_list_lines = tail_prefix_and_list
            blocks.append(
                {"type": "p", "text": clean_paragraph(" ".join(tail_prefix_lines))}
            )
            append_list_block_with_tail(tail_list_lines, tail_list_block)
            return True

        tail_list_block = build_list_block(tail_lines)
        if tail_list_block:
            append_list_block_with_tail(tail_lines, tail_list_block)
            return True

        blocks.append({"type": "p", "text": clean_paragraph(" ".join(tail_lines))})
        return True

    def try_emit_single_numeric_marker_list(non_empty: list[str]) -> bool:
        first_line_str = clean_paragraph(non_empty[0]) if non_empty else ""
        single_marker_match = match_list_marker(first_line_str)
        if not (
            single_marker_match
            and re.match(r"^\d+\.$", single_marker_match.group("marker"))
            and len(non_empty) <= 2
        ):
            return False

        marker_text = single_marker_match.group("marker")
        rest_text = single_marker_match.group("rest")
        if not rest_text:
            return False

        remaining = " ".join(
            [rest_text] + [clean_paragraph(line) for line in non_empty[1:]]
        )
        full_text = clean_paragraph(remaining)
        if full_text.endswith(".") and is_period_terminated_heading_candidate(
            full_text, len(non_empty)
        ):
            return False

        single_item_list = {
            "type": "list",
            "ordered": True,
            "show_markers": False,
            "items": [{"marker": marker_text, "text": full_text}],
        }
        start_num = extract_marker_start_number(marker_text)
        if start_num is not None:
            single_item_list["start"] = start_num
        blocks.append(single_item_list)
        return True

    def try_emit_short_subheading(non_empty: list[str]) -> bool:
        if not (1 <= len(non_empty) <= 3):
            return False
        candidate = clean_paragraph(" ".join(non_empty))
        if not is_subheading_candidate(candidate, len(non_empty)):
            return False

        cleaned_heading = strip_trailing_subheading_period(candidate)
        if is_minor_subheading(cleaned_heading):
            blocks.append({"type": "h3_small", "text": cleaned_heading})
        else:
            blocks.append({"type": "h2", "text": cleaned_heading})
        return True

    def try_emit_list_block(non_empty: list[str]) -> bool:
        list_block = build_list_block(non_empty)
        if not list_block:
            return False
        append_list_block_with_tail(non_empty, list_block)
        return True

    def emit_paragraph(non_empty: list[str]) -> None:
        paragraph = clean_paragraph(" ".join(non_empty))
        if paragraph:
            blocks.append({"type": "p", "text": paragraph})

    block_rules = (
        BlockRule("table", try_emit_table),
        BlockRule(
            "heading-dot-italic-tail-3",
            lambda lines: try_emit_heading_dot_with_italic_tail(lines, min_lines=3),
        ),
        BlockRule(
            "heading-dot-paragraph-tail", try_emit_heading_dot_with_paragraph_tail
        ),
        BlockRule(
            "chapter-heading-paragraph-tail",
            try_emit_chapter_heading_with_paragraph_tail,
        ),
        BlockRule("numbered-subheading-tail", try_emit_numbered_subheading_with_tail),
        BlockRule("three-line-heading", try_emit_three_line_heading),
        BlockRule(
            "two-line-heading-italic-tail", try_emit_two_line_heading_with_italic_tail
        ),
        BlockRule(
            "heading-dot-italic-tail-2",
            lambda lines: try_emit_heading_dot_with_italic_tail(lines, min_lines=2),
        ),
        BlockRule("heading-plus-list", try_emit_heading_plus_list),
        BlockRule("prefix-and-list", try_emit_prefix_and_list),
        BlockRule("split-list-and-tail", try_emit_split_list_and_tail),
        BlockRule("list-block", try_emit_list_block),
        BlockRule("short-subheading", try_emit_short_subheading),
    )

    def flush_buffer() -> None:
        if not buffer_lines:
            return

        non_empty = [line for line in buffer_lines if line.strip()]
        buffer_lines.clear()
        if not non_empty:
            return

        for rule in block_rules:
            if rule.handler(non_empty):
                return

        emit_paragraph(non_empty)

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
