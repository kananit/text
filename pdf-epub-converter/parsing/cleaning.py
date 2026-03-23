import re


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


def normalize_title(title: str) -> str:
    title = clean_paragraph(title)
    title = re.sub(r"\s{2,}", " ", title)
    return title[:120]


def remove_urls_and_domains(text: str) -> str:
    """Удаляет URL и типичные домены мусорных сайтов (работает построчно)."""
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"https?://\S+", "", line, flags=re.IGNORECASE)
        line = re.sub(r"filosoff\.org", "", line, flags=re.IGNORECASE)
        line = re.sub(r"libking\.ru", "", line, flags=re.IGNORECASE)
        line = re.sub(r"flibusta\.site", "", line, flags=re.IGNORECASE)
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def remove_boilerplate_text(text: str) -> str:
    """Удаляет типичные фразы благодарности, рекламу и мусор (по строкам)."""
    lines = text.split("\n")
    result = []

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
        line = re.sub(r"\b(?:страница|page)\s+\d{1,4}\b", "", line, flags=re.IGNORECASE)
        line = re.sub(r"\s+", " ", line).strip()

        should_skip = False
        for pattern in skip_patterns:
            if re.search(pattern, line[:100], flags=re.IGNORECASE):
                should_skip = True
                break

        if not should_skip and line.strip():
            result.append(line)

    return "\n".join(result)


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
