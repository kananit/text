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
    detect_probable_page_number_line_indices,
    detect_repeated_noise_lines,
    is_running_footer_line,
)


def _strip_toc_leader_artifacts(title: str) -> str:
    cleaned = normalize_title(title)
    cleaned = re.sub(r"\s*[.․‥…⋯·•]{2,}\s*$", "", cleaned)
    return cleaned.rstrip()


def _toc_title_key(title: str) -> str:
    cleaned = _strip_toc_leader_artifacts(title).lower()
    return cleaned.strip(' .,:;!?-—–/\\"')


def extract_toc_entries(text: str) -> list[TocEntry]:
    lines = [clean_line(line) for line in text.split("\n")]
    footer_titles = detect_running_footer_titles(
        lines,
        min_occurrences=FOOTER_MIN_OCCURRENCES,
    )
    page_number_indices = detect_probable_page_number_line_indices(lines)
    lines = [
        line
        for index, line in enumerate(lines)
        if index not in page_number_indices
        and not is_running_footer_line(line, footer_titles)
    ]
    toc_separator = r"(?:\s*[.․‥…⋯·•]{2,}\s*|\s{2,})"
    toc_header = re.compile(
        r"^(содержание|оглавление|contents|table of contents)\s*$",
        re.IGNORECASE,
    )
    toc_entry_patterns = [
        re.compile(rf"^(?P<title>.+?){toc_separator}(?P<page>\d{{1,4}})\s*$"),
        re.compile(
            rf"^(?P<title>(?:глава|часть|раздел)\s+[0-9ivxlcdm].*?){toc_separator}(?P<page>\d{{1,4}})\s*$",
            re.IGNORECASE,
        ),
        re.compile(
            rf"^(?P<title>(?:chapter|part|section)\s+[0-9ivxlcdm].*?){toc_separator}(?P<page>\d{{1,4}})\s*$",
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

        title = _strip_toc_leader_artifacts(matched.group("title"))
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
    lowered = _toc_title_key(normalized)

    for idx, item in enumerate(toc_entries):
        if idx in used_indices:
            continue
        toc_title = _toc_title_key(item.title)
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
    if stripped.endswith((".", ",", ";", ":", "?", "!", "…", ")")):
        return False
    if re.search(r"[,;:()]", stripped):
        return False
    if re.search(r"\d{4,}", stripped):
        return False
    if len(stripped.split()) > 8:
        return False
    return bool(re.search(r"[A-Za-zА-Яа-яЁё]", stripped))


def _is_toc_title_heading_candidate(
    line: str,
    toc_titles_exact: set[str],
    next_non_empty_line: str | None,
) -> bool:
    stripped = line.strip()
    if not stripped:
        return False

    normalized = _toc_title_key(stripped)
    if normalized not in toc_titles_exact:
        return False
    if is_chapter_heading(stripped):
        return False

    if next_non_empty_line:
        next_normalized = _toc_title_key(next_non_empty_line)
        if next_normalized in toc_titles_exact or is_chapter_heading(
            next_non_empty_line
        ):
            return False

    return True


_FRONT_MATTER_HEADINGS = {
    "отзывы",
    "предисловие",
    "введение",
    "послесловие",
    "заключение",
    "благодарности",
    "foreword",
    "preface",
    "introduction",
    "afterword",
    "acknowledgements",
    "acknowledgments",
    "conclusion",
}


def _normalize_heading_label(text: str) -> str:
    return normalize_title(text).lower().strip(" .:-—–")


def _finalize_section_title(text: str) -> str:
    title = normalize_title(text)
    return re.sub(r"\s*[:：;；/\-—–]+\s*$", "", title)


def _is_front_matter_heading_candidate(
    line: str,
    next_non_empty_line: str | None,
) -> bool:
    normalized = _normalize_heading_label(line)
    if normalized not in _FRONT_MATTER_HEADINGS:
        return False

    # Avoid matching TOC listing where headings go one-by-one.
    if next_non_empty_line:
        next_normalized = _normalize_heading_label(next_non_empty_line)
        if next_normalized in _FRONT_MATTER_HEADINGS or is_chapter_heading(
            next_non_empty_line
        ):
            return False

    return True


def _min_section_content_len(title: str | None) -> int:
    if title and _normalize_heading_label(title) in _FRONT_MATTER_HEADINGS:
        return 120
    return 300


def _chapter_split_threshold(title: str | None) -> int:
    if title and _normalize_heading_label(title) in _FRONT_MATTER_HEADINGS:
        return 120
    return 2500


def _is_probable_toc_chapter_line(lines: list[str], chapter_line_index: int) -> bool:
    # Strong signal: nearby TOC header above this line.
    header_window_start = max(0, chapter_line_index - 25)
    for k in range(header_window_start, chapter_line_index):
        if re.match(
            r"^(содержание|оглавление|contents|table of contents)\s*$",
            lines[k].strip(),
            flags=re.IGNORECASE,
        ):
            return True

    # Heuristic: TOC often contains several chapter headings in a short range.
    chapter_like_count = 0
    scan_end = min(len(lines), chapter_line_index + 16)
    for k in range(chapter_line_index, scan_end):
        candidate = lines[k].strip()
        if not candidate:
            continue
        if is_chapter_heading(candidate):
            chapter_like_count += 1
            if chapter_like_count >= 3:
                return True

    return False


def _is_numbered_heading_title_candidate(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if len(stripped) > 120:
        return False
    if is_chapter_heading(stripped):
        return False
    if re.fullmatch(r"\d{1,4}", stripped):
        return False
    if not re.search(r"[A-Za-zА-Яа-яЁё]", stripped):
        return False
    if re.search(r"https?://|www\.", stripped, flags=re.IGNORECASE):
        return False
    return True


def _is_explicit_chapter_start_candidate(lines: list[str], index: int) -> bool:
    stripped = lines[index].strip()
    if not stripped or not is_chapter_heading(stripped):
        return False

    prev_line = lines[index - 1].strip() if index > 0 else ""
    next_line = lines[index + 1].strip() if index + 1 < len(lines) else ""
    has_blank_before = index == 0 or not prev_line
    has_blank_after = index + 1 >= len(lines) or not next_line

    if not (has_blank_before or has_blank_after):
        return False

    if stripped.endswith((",", ";", ":")):
        return False

    if not has_blank_before and re.search(r"[A-Za-zА-Яа-яЁё0-9,;:(]$", prev_line):
        return False

    return True


def _is_bare_explicit_chapter_heading(line: str) -> bool:
    stripped = line.strip()
    patterns = [
        r"^(?:глава|часть|раздел)\s+[0-9ivxlcdm]+(?:\s*[\.:\-)])?\s*$",
        r"^(?:chapter|part|section)\s+[0-9ivxlcdm]+(?:\s*[\.:\-)])?\s*$",
        r"^(?:приложение|appendix)\s+[a-zа-я0-9ivxlcdm]+(?:\s*[\.:\-)])?\s*$",
    ]
    return any(re.match(pattern, stripped, re.IGNORECASE) for pattern in patterns)


def _extract_explicit_chapter_numbers(lines: list[str]) -> list[int]:
    numbers: list[int] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or not is_chapter_heading(stripped):
            continue
        match = re.search(
            r"(?:глава|часть|раздел|chapter|part|section)\s+(\d{1,3})",
            stripped,
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        number = int(match.group(1))
        if 1 <= number <= 300:
            numbers.append(number)
    return numbers


def _next_non_empty_line(
    lines: list[str], start_index: int
) -> tuple[int | None, str | None]:
    index = start_index
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index < len(lines):
        return index, lines[index].strip()
    return None, None


def _append_current_chapter_if_valid(
    chapters: list[Chapter],
    current_title: str | None,
    current_content: list[str],
) -> None:
    if not current_title or not current_content:
        return

    final_content = "\n".join(current_content).strip()
    if len(final_content) > _min_section_content_len(current_title):
        chapters.append(Chapter(title=current_title, content=final_content))


def _handle_toc_or_front_matter_branch(
    *,
    stripped: str,
    next_non_empty_line: str | None,
    chapters: list[Chapter],
    current_title: str | None,
    current_content: list[str],
    toc_titles_exact: set[str],
    toc_entries: list[TocEntry],
    used_toc_indices: set[int],
) -> tuple[bool, str | None, list[str]]:
    if _is_toc_title_heading_candidate(stripped, toc_titles_exact, next_non_empty_line):
        _append_current_chapter_if_valid(chapters, current_title, current_content)
        new_title = _finalize_section_title(
            resolve_title_with_toc(stripped, toc_entries, used_toc_indices)
        )
        return True, new_title, []

    if _is_front_matter_heading_candidate(stripped, next_non_empty_line):
        _append_current_chapter_if_valid(chapters, current_title, current_content)
        new_title = _finalize_section_title(stripped)
        return True, new_title, []

    return False, current_title, current_content


def _handle_number_plus_title_branch(
    *,
    lines: list[str],
    i: int,
    stripped: str,
    enable_number_plus_title_detection: bool,
    chapters: list[Chapter],
    current_title: str | None,
    current_content: list[str],
    toc_entries: list[TocEntry],
    used_toc_indices: set[int],
) -> tuple[bool, int, str | None, list[str]]:
    if not enable_number_plus_title_detection or not re.fullmatch(r"\d{1,3}", stripped):
        return False, i, current_title, current_content

    chapter_number = int(stripped)
    if not (1 <= chapter_number <= 300):
        return False, i, current_title, current_content
    if _is_probable_toc_chapter_line(lines, i - 1):
        return False, i, current_title, current_content

    title_idx, title_candidate = _next_non_empty_line(lines, i)
    if title_idx is None or title_candidate is None:
        return False, i, current_title, current_content
    if not _is_numbered_heading_title_candidate(title_candidate):
        return False, i, current_title, current_content

    body_probe_idx, _ = _next_non_empty_line(lines, title_idx + 1)
    if body_probe_idx is None:
        return False, i, current_title, current_content

    _append_current_chapter_if_valid(chapters, current_title, current_content)
    combined = f"Глава {chapter_number}. {title_candidate}"
    new_title = _finalize_section_title(
        resolve_title_with_toc(combined, toc_entries, used_toc_indices)
    )
    return True, title_idx + 1, new_title, []


def _handle_explicit_chapter_heading_branch(
    *,
    lines: list[str],
    i: int,
    line: str,
    stripped: str,
    current_title: str | None,
    current_content: list[str],
    chapters: list[Chapter],
    toc_entries: list[TocEntry],
    used_toc_indices: set[int],
) -> tuple[bool, int, str | None, list[str]]:
    current_index = i - 1
    if not _is_explicit_chapter_start_candidate(lines, current_index):
        return False, i, current_title, current_content
    if _is_probable_toc_chapter_line(lines, i - 1):
        return True, i, current_title, current_content

    accumulated_len = len("\n".join(current_content).strip())
    if current_title and accumulated_len > _chapter_split_threshold(current_title):
        chapters.append(
            Chapter(title=current_title, content="\n".join(current_content).strip())
        )
        current_content = []
    elif current_title and accumulated_len <= _chapter_split_threshold(current_title):
        current_content.append(line)
        return True, i, current_title, current_content

    combined = stripped
    next_idx, next_line = _next_non_empty_line(lines, i)
    if (
        _is_bare_explicit_chapter_heading(stripped)
        and next_idx is not None
        and next_line
        and _is_subtitle_candidate(next_line)
    ):
        combined = f"{stripped}. {next_line}"
        i = next_idx + 1

    new_title = _finalize_section_title(
        resolve_title_with_toc(combined, toc_entries, used_toc_indices)
    )
    return True, i, new_title, []


def _prepare_chapter_detection_context(text: str, toc_entries: list[TocEntry]) -> dict:
    """Pre-process text and build detection context.

    Returns dict with keys:
    - lines: cleaned, denoised lines
    - footer_titles: detected footer titles
    - repeated_noise_lines: detected repeated noise lines
    - enable_number_plus_title_detection: bool flag
    - toc_titles_exact: set of normalized TOC titles
    """
    lines = [clean_line(line) for line in text.split("\n")]
    footer_titles = detect_running_footer_titles(
        lines,
        min_occurrences=FOOTER_MIN_OCCURRENCES,
    )
    page_number_indices = detect_probable_page_number_line_indices(lines)
    repeated_noise_lines = detect_repeated_noise_lines(
        lines,
        min_occurrences=FOOTER_MIN_OCCURRENCES,
    )
    lines = [
        line
        for index, line in enumerate(lines)
        if index not in page_number_indices
        and not is_running_footer_line(line, footer_titles)
    ]
    lines = [
        line
        for line in lines
        if clean_paragraph(line).lower() not in repeated_noise_lines
    ]

    explicit_numbers = _extract_explicit_chapter_numbers(lines)
    enable_number_plus_title_detection = (
        bool(explicit_numbers) and 1 not in explicit_numbers
    )

    toc_titles_exact = {_toc_title_key(item.title) for item in toc_entries}

    return {
        "lines": lines,
        "footer_titles": footer_titles,
        "page_number_indices": page_number_indices,
        "repeated_noise_lines": repeated_noise_lines,
        "enable_number_plus_title_detection": enable_number_plus_title_detection,
        "toc_titles_exact": toc_titles_exact,
    }


def identify_chapters(text: str, toc_entries: list[TocEntry]) -> list[Chapter]:
    ctx = _prepare_chapter_detection_context(text, toc_entries)
    lines = ctx["lines"]
    repeated_noise_lines = ctx["repeated_noise_lines"]
    enable_number_plus_title_detection = ctx["enable_number_plus_title_detection"]

    chapters: list[Chapter] = []
    current_title = None
    current_content: list[str] = []
    used_toc_indices: set[int] = set()
    toc_titles_exact = ctx["toc_titles_exact"]

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        i += 1

        if not stripped:
            if current_content:
                current_content.append("")
            continue

        # Support non-numbered section starts from TOC/front-matter
        # while ignoring TOC listing itself.
        _, next_non_empty_line = _next_non_empty_line(lines, i)

        handled, current_title, current_content = _handle_toc_or_front_matter_branch(
            stripped=stripped,
            next_non_empty_line=next_non_empty_line,
            chapters=chapters,
            current_title=current_title,
            current_content=current_content,
            toc_titles_exact=toc_titles_exact,
            toc_entries=toc_entries,
            used_toc_indices=used_toc_indices,
        )
        if handled:
            continue

        handled, i, current_title, current_content = _handle_number_plus_title_branch(
            lines=lines,
            i=i,
            stripped=stripped,
            enable_number_plus_title_detection=enable_number_plus_title_detection,
            chapters=chapters,
            current_title=current_title,
            current_content=current_content,
            toc_entries=toc_entries,
            used_toc_indices=used_toc_indices,
        )
        if handled:
            continue

        handled, i, current_title, current_content = (
            _handle_explicit_chapter_heading_branch(
                lines=lines,
                i=i,
                line=line,
                stripped=stripped,
                current_title=current_title,
                current_content=current_content,
                chapters=chapters,
                toc_entries=toc_entries,
                used_toc_indices=used_toc_indices,
            )
        )
        if handled:
            continue

        if current_title:
            current_content.append(line)

    _append_current_chapter_if_valid(chapters, current_title, current_content)

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
