import re
from collections import Counter

from .cleaning import clean_paragraph, is_chapter_heading


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
