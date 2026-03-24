import re
from collections import Counter

from .cleaning import clean_paragraph, is_chapter_heading


def is_standalone_page_number_line(line: str) -> bool:
    return bool(re.fullmatch(r"\d{1,4}", clean_paragraph(line)))


def detect_probable_page_number_line_indices(
    lines: list[str],
    min_candidates: int = 20,
    min_gap: int = 3,
    max_gap: int = 120,
) -> set[int]:
    candidates: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        normalized = clean_paragraph(line)
        if not re.fullmatch(r"\d{1,4}", normalized):
            continue
        candidates.append((index, int(normalized)))

    if len(candidates) < min_candidates:
        return set()

    probable_indices: set[int] = set()
    for pos, (index, number) in enumerate(candidates):
        has_sequence_neighbor = False

        if pos > 0:
            prev_index, prev_number = candidates[pos - 1]
            if min_gap <= index - prev_index <= max_gap and number == prev_number + 1:
                has_sequence_neighbor = True

        if pos + 1 < len(candidates):
            next_index, next_number = candidates[pos + 1]
            if min_gap <= next_index - index <= max_gap and next_number == number + 1:
                has_sequence_neighbor = True

        if has_sequence_neighbor:
            probable_indices.add(index)

    if len(probable_indices) < min_candidates:
        return set()

    return probable_indices


def detect_running_footer_titles(
    lines: list[str], min_occurrences: int = 5
) -> set[str]:
    counts: Counter[str] = Counter()
    for line in lines:
        normalized = clean_paragraph(line)
        if not normalized:
            continue

        match = re.match(r"^(?P<title>.+?)\s+(?P<page>\d{1,4})$", normalized)
        if not match:
            continue

        title = match.group("title").strip()
        if len(title) < 6:
            continue
        if is_chapter_heading(title):
            continue
        if re.match(
            r"^(содержание|оглавление|contents|table of contents)$",
            title,
            re.IGNORECASE,
        ):
            continue

        counts[title.lower()] += 1

    return {title for title, count in counts.items() if count >= min_occurrences}


def detect_repeated_noise_lines(lines: list[str], min_occurrences: int = 5) -> set[str]:
    counts: Counter[str] = Counter()
    for line in lines:
        normalized = clean_paragraph(line)
        if not normalized:
            continue
        lowered = normalized.lower()
        counts[lowered] += 1

    repeated_noise: set[str] = set()
    for lowered, count in counts.items():
        if count < min_occurrences:
            continue
        if re.fullmatch(r"\d{1,4}", lowered):
            continue
        if re.fullmatch(r"[\W_]+", lowered):
            continue
        if is_chapter_heading(lowered):
            continue
        repeated_noise.add(lowered)

    return repeated_noise


def is_running_footer_line(line: str, footer_titles: set[str]) -> bool:
    if not footer_titles:
        return False
    normalized = clean_paragraph(line)
    match = re.match(r"^(?P<title>.+?)\s+(?P<page>\d{1,4})$", normalized)
    if not match:
        return False
    return match.group("title").strip().lower() in footer_titles
