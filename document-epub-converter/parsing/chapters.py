import re

from config import FOOTER_MIN_OCCURRENCES
from models import Chapter, TocEntry

from .cleaning import (
    clean_line,
    clean_paragraph,
    normalize_title,
    is_chapter_heading,
    chapter_number_key,
)
from .noise import (
    detect_running_footer_titles,
    detect_repeated_noise_lines,
    is_running_footer_line,
)


def extract_toc_entries(text: str) -> list[TocEntry]:
    lines = [clean_line(line) for line in text.split("\n")]
    footer_titles = detect_running_footer_titles(
        lines,
        min_occurrences=FOOTER_MIN_OCCURRENCES,
    )
    lines = [line for line in lines if not is_running_footer_line(line, footer_titles)]
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


def collect_profile_heading_parts(
    lines: list[str],
    start_index: int,
    repeated_noise_lines: set[str],
) -> tuple[str, str, int] | None:
    parts: list[str] = []
    index = start_index + 1

    while index < len(lines) and len(parts) < 2 and index <= start_index + 8:
        candidate = lines[index].strip()
        index += 1

        if not candidate:
            continue
        if clean_paragraph(candidate).lower() in repeated_noise_lines:
            continue
        if re.fullmatch(r"[❖•·*]+", candidate):
            continue

        parts.append(candidate)

    if len(parts) < 2:
        return None

    subtitle_line, names_line = parts[0], parts[1]
    if not re.search(r"[A-Za-zА-Яа-яЁё]", subtitle_line):
        return None
    if not re.search(r"[A-Za-zА-Яа-яЁё]", names_line):
        return None
    if len(subtitle_line) > 120 or len(names_line) > 120:
        return None
    if not re.search(r"\b(и|and)\b", names_line, flags=re.IGNORECASE):
        return None

    return subtitle_line, names_line, index


def identify_numbered_profile_chapters(
    lines: list[str], repeated_noise_lines: set[str]
) -> list[Chapter]:
    candidates: list[tuple[int, int, str, int]] = []

    for i in range(len(lines) - 1):
        number_line = lines[i].strip()
        if not re.fullmatch(r"\d{1,3}", number_line):
            continue

        number = int(number_line)
        if number < 1 or number > 40:
            continue

        parts = collect_profile_heading_parts(lines, i, repeated_noise_lines)
        if not parts:
            continue

        subtitle_line, names_line, body_start = parts
        subtitle = normalize_title(subtitle_line)
        names = normalize_title(names_line)
        title = f"{number}. {subtitle} — {names}"
        candidates.append((i, number, title, body_start))

    if len(candidates) < 2:
        return []

    start_pos = next((idx for idx, item in enumerate(candidates) if item[1] == 1), 0)
    filtered: list[tuple[int, int, str, int]] = [candidates[start_pos]]

    for start_idx, number, title, body_start in candidates[start_pos + 1 :]:
        if number == filtered[-1][1] + 1:
            filtered.append((start_idx, number, title, body_start))

    if len(filtered) < 2:
        return []

    chapters: list[Chapter] = []
    for idx, (start_idx, _number, title, content_start) in enumerate(filtered):
        content_end = filtered[idx + 1][0] if idx + 1 < len(filtered) else len(lines)
        content = "\n".join(lines[content_start:content_end]).strip()
        if len(content) > 300:
            chapters.append(Chapter(title=title, content=content))

    return chapters


def _is_subtitle_candidate(line: str) -> bool:
    """True если строка похожа на подзаголовок главы (короткая, не сама заголовок)."""
    stripped = line.strip()
    if not stripped or len(stripped) > 80:
        return False
    if is_chapter_heading(stripped):
        return False
    if re.search(r"\d{4,}", stripped):
        return False
    return bool(re.search(r"[A-Za-zА-Яа-яЁё]", stripped))


def identify_chapters(text: str, toc_entries: list[TocEntry]) -> list[Chapter]:
    lines = [clean_line(line) for line in text.split("\n")]
    footer_titles = detect_running_footer_titles(
        lines,
        min_occurrences=FOOTER_MIN_OCCURRENCES,
    )
    repeated_noise_lines = detect_repeated_noise_lines(
        lines,
        min_occurrences=FOOTER_MIN_OCCURRENCES,
    )
    lines = [line for line in lines if not is_running_footer_line(line, footer_titles)]
    lines = [
        line
        for line in lines
        if clean_paragraph(line).lower() not in repeated_noise_lines
    ]
    chapters: list[Chapter] = []
    current_title = None
    current_content: list[str] = []
    used_toc_indices: set[int] = set()

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        i += 1

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

            # Lookahead: если следующая непустая строка — короткий подзаголовок,
            # объединяем её с заголовком главы (напр. "Глава 3" + "Жертва")
            combined = stripped
            j = i
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and _is_subtitle_candidate(lines[j]):
                subtitle = lines[j].strip()
                combined = f"{stripped}. {subtitle}"
                i = j + 1

            current_title = resolve_title_with_toc(
                combined, toc_entries, used_toc_indices
            )
            continue

        if current_title:
            current_content.append(line)

    if current_title and current_content:
        final_content = "\n".join(current_content).strip()
        if len(final_content) > 300:
            chapters.append(Chapter(title=current_title, content=final_content))

    if len(chapters) < 2:
        numbered_profile_chapters = identify_numbered_profile_chapters(
            lines,
            repeated_noise_lines,
        )
        if len(numbered_profile_chapters) >= 2:
            return numbered_profile_chapters

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
