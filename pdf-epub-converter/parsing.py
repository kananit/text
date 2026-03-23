import re
from collections import Counter

from config import (
    FOOTER_MIN_OCCURRENCES,
    MINOR_SUBHEADING_ENABLED,
    MINOR_SUBHEADING_MAX_LEN,
    MINOR_SUBHEADING_UPPERCASE_RATIO,
)
from models import Chapter, TocEntry


def detect_language(text: str) -> str:
    cyr = len(re.findall(r"[А-Яа-яЁё]", text))
    lat = len(re.findall(r"[A-Za-z]", text))
    return "ru" if cyr > lat else "en"


def clean_line(text: str) -> str:
    # Strip ASCII control chars (except \t, \n)
    text = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]", "", text)
    # Strip Unicode invisible/directional/format marks (e.g. \u200f from textutil docx output)
    # Note: \u2028/\u2029 are converted to real \n at extraction time, not here
    text = re.sub(r"[\u200b-\u200f\u202a-\u202e\ufeff]", "", text)
    return text.rstrip()


def clean_paragraph(text: str) -> str:
    text = clean_line(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def remove_urls_and_domains(text: str) -> str:
    """Удаляет URL и типичные домены мусорных сайтов (работает построчно)."""
    lines = []
    for line in text.split("\n"):
        # Удаляем полные URL (http://, https://)
        line = re.sub(r"https?://\S+", "", line, flags=re.IGNORECASE)
        # Удаляем конкретные известные домены мусора
        line = re.sub(r"filosoff\.org", "", line, flags=re.IGNORECASE)
        line = re.sub(r"libking\.ru", "", line, flags=re.IGNORECASE)
        line = re.sub(r"flibusta\.site", "", line, flags=re.IGNORECASE)
        # Очищаем избыточные пробелы в этой строке
        line = re.sub(r"\s+", " ", line).strip()
        if line:  # добавляем только непустые строки
            lines.append(line)
    return "\n".join(lines)


def remove_boilerplate_text(text: str) -> str:
    """Удаляет типичные фразы благодарности, рекламу и мусор (по строкам)."""
    lines = text.split("\n")
    result = []

    # Очень специфичные паттерны для полных строк (рекламы, благодарности)
    skip_patterns = [
        r"^спасибо.{0,50}скачал.{0,50}книгу",
        r"^thank you for downloading",
        r"^спасибо за скачивание",
        r"^если вам понравилась",
        r"^поделитесь с друзьями",
        r"^присоединяйтесь к",
        r"^подпишитесь на",
        r"^найти нас в",
        r"^все права защищены",
        r"^copyright",
    ]

    for line in lines:
        # Удаляем маркеры страниц (например: "Страница 2")
        line = re.sub(r"\b(?:страница|page)\s+\d{1,4}\b", "", line, flags=re.IGNORECASE)
        line = re.sub(r"\s+", " ", line).strip()

        should_skip = False
        # Проверяем только начало строки и ограничиваем матч 50 символами
        for pattern in skip_patterns:
            if re.search(pattern, line[:100], flags=re.IGNORECASE):
                should_skip = True
                break

        if not should_skip and line.strip():  # Не пустая строка
            result.append(line)

    return "\n".join(result)


def normalize_title(title: str) -> str:
    title = clean_paragraph(title)
    title = re.sub(r"\s{2,}", " ", title)
    return title[:120]


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

    # Берем последовательность с 1 и дальше по порядку: 1,2,3...
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
    if re.search(r"\d{4,}", stripped):  # длинные числа — скорее не заголовок
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
                i = j + 1  # пропускаем строку подзаголовка

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
                and not re.search(r"[\.\.!?…:]$", one)
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
