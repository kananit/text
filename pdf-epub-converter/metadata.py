import json
import re
import subprocess
from pathlib import Path

from config import (
    EXAMPLE_META_CREATOR,
    EXAMPLE_META_TITLE,
    EXAMPLE_META_YEAR,
    REQUIRED_META_FIELDS,
)
from models import BookMetadata


METADATA_BOOTSTRAP_TEXT_FILE = Path("/tmp/document_meta_bootstrap.txt")

TITLE_PATTERNS = [
    r"^\s*Название\s*[:\-]\s*(.+)$",
    r"^\s*Title\s*[:\-]\s*(.+)$",
]

CREATOR_PATTERNS = [
    r"^\s*Автор(?:ы)?\s*[:\-]\s*(.+)$",
    r"^\s*Author(?:s)?\s*[:\-]\s*(.+)$",
]

PUBLISHER_PATTERNS = [
    r"^\s*Издательство\s*[:\-]\s*(.+)$",
    r"^\s*Publisher\s*[:\-]\s*(.+)$",
]

YEAR_PATTERNS = [
    r"^\s*Год\s*[:\-]\s*((?:19|20)\d{2})\s*$",
    r"\b((?:19|20)\d{2})\b",
]

AUTHOR_PREFIX_PATTERNS = [
    r"^(?:by|author|автор|авторы)\s*[:\-]?\s*(.+)$",
]


def default_book_metadata() -> BookMetadata:
    title = EXAMPLE_META_TITLE
    year = EXAMPLE_META_YEAR
    return BookMetadata(
        title=title,
        creator=EXAMPLE_META_CREATOR,
        publisher="Unknown Publisher",
        year=year,
        description=f"{title}. Издание {year} года.",
    )


def _clean_str(value: object, fallback: str) -> str:
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            return cleaned
    return fallback


def _find_first(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            value = (
                match.group(1).strip() if match.lastindex else match.group(0).strip()
            )
            if value:
                return value
    return None


def _page_lines(text: str, max_lines: int = 20) -> list[str]:
    first_page = text.split("\f", 1)[0]
    lines = []
    for raw_line in first_page.splitlines():
        # Strip invisible Unicode direction/format marks
        raw_line = re.sub(r"[\u200b-\u200f\u202a-\u202e\ufeff]", "", raw_line)
        line = " ".join(raw_line.split()).strip()
        if line:
            lines.append(line)
        if len(lines) >= max_lines:
            break
    return lines


def _has_letters(line: str) -> bool:
    return bool(re.search(r"[A-Za-zА-Яа-яЁё]", line))


def _is_bad_meta_line(line: str) -> bool:
    lowered = line.lower()
    blocked = (
        "издательство",
        "publisher",
        "оглавление",
        "contents",
        "chapter",
        "глава",
        "год",
        "isbn",
        "http",
        "www.",
    )
    return any(token in lowered for token in blocked)


def _looks_like_title_line(line: str) -> bool:
    if len(line) < 4 or len(line) > 120:
        return False
    if _is_bad_meta_line(line):
        return False
    if re.search(r"\d{4}", line):
        return False
    if not _has_letters(line):
        return False
    words = [word for word in re.split(r"\s+", line) if word]
    return 1 <= len(words) <= 12


def _looks_like_author_line(line: str) -> bool:
    if len(line) < 5 or len(line) > 80:
        return False
    if _is_bad_meta_line(line):
        return False
    if re.search(r"\d", line):
        return False
    if not _has_letters(line):
        return False

    for pattern in AUTHOR_PREFIX_PATTERNS:
        if re.match(pattern, line, flags=re.IGNORECASE):
            return True

    words = [w for w in re.split(r"\s+", line) if w]
    if not (2 <= len(words) <= 5):
        return False
    stopwords = {
        "и",
        "в",
        "на",
        "с",
        "со",
        "по",
        "о",
        "the",
        "of",
        "and",
        "with",
        "for",
    }
    lowered_words = [w.lower().strip(".,:;!?()[]{}\"'") for w in words]
    if any(word in stopwords for word in lowered_words):
        return False

    capitalized_count = sum(
        1 for w in words if re.match(r"^[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё'\-]+$", w)
    )
    return capitalized_count >= 2


def _extract_first_page_title_author(text: str) -> tuple[str | None, str | None]:
    lines = _page_lines(text, max_lines=20)
    if not lines:
        return None, None

    title_candidate = None
    author_candidate = None
    title_index = -1

    for index, line in enumerate(lines[:8]):
        # Check author before title: a line matching both (e.g. "Иван Иванов") is
        # more likely an author name than a book title.
        if author_candidate is None and _looks_like_author_line(line):
            prefix_match = None
            for pattern in AUTHOR_PREFIX_PATTERNS:
                prefix_match = re.match(pattern, line, flags=re.IGNORECASE)
                if prefix_match:
                    break
            author_candidate = (
                prefix_match.group(1).strip()
                if prefix_match and prefix_match.lastindex
                else line
            )

        if (
            title_candidate is None
            and _looks_like_title_line(line)
            and not _looks_like_author_line(line)
        ):
            title_candidate = line
            title_index = index
            if index + 1 < len(lines):
                subtitle_line = lines[index + 1]
                subtitle_words = [
                    w for w in re.split(r"\s+", subtitle_line.strip()) if w
                ]
                if (
                    _looks_like_title_line(subtitle_line)
                    and not _looks_like_author_line(subtitle_line)
                    and subtitle_line.lower() not in title_candidate.lower()
                    and len(subtitle_words) >= 2  # skip single-word city names etc.
                ):
                    title_candidate = f"{title_candidate}: {subtitle_line}"

        if title_candidate and author_candidate:
            break

    return title_candidate, author_candidate


def _try_extract_source_text(source_file: Path) -> str | None:
    suffix = source_file.suffix.lower()

    if suffix == ".pdf":
        command = [
            "pdftotext",
            "-layout",
            "-f",
            "1",
            "-l",
            "8",
            str(source_file),
            str(METADATA_BOOTSTRAP_TEXT_FILE),
        ]
        result = subprocess.run(command, capture_output=True)
        if result.returncode != 0:
            return None
        try:
            return METADATA_BOOTSTRAP_TEXT_FILE.read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            return None
        finally:
            if METADATA_BOOTSTRAP_TEXT_FILE.exists():
                METADATA_BOOTSTRAP_TEXT_FILE.unlink()

    if suffix in {".doc", ".docx"}:
        command = ["textutil", "-convert", "txt", "-stdout", str(source_file)]
        result = subprocess.run(command, capture_output=True)
        if result.returncode != 0:
            return None
        text = result.stdout.decode("utf-8", errors="replace")
        # Same cleanup as extraction.py: convert line separators, strip invisible marks
        text = text.replace("\u2028", "\n").replace("\u2029", "\n")
        text = re.sub(r"[\u200b-\u200f\u202a-\u202e\ufeff]", "", text)
        return text

    return None


def load_example_metadata(metadata_example_file: Path) -> BookMetadata:
    defaults = default_book_metadata()
    if not metadata_example_file.exists():
        save_book_metadata(metadata_example_file, defaults)
        return defaults

    metadata, _, _ = load_book_metadata(metadata_example_file, defaults)
    return metadata


def guess_metadata_from_text(
    text: str,
    fallback: BookMetadata,
) -> tuple[BookMetadata, list[str]]:
    title = _find_first(TITLE_PATTERNS, text)
    creator = _find_first(CREATOR_PATTERNS, text)
    publisher = _find_first(PUBLISHER_PATTERNS, text)
    year = _find_first(YEAR_PATTERNS, text)

    if not title or not creator:
        first_page_title, first_page_author = _extract_first_page_title_author(text)
        if not title and first_page_title:
            title = first_page_title
        if not creator and first_page_author:
            creator = first_page_author

    missing_required = []
    if not title:
        missing_required.append("title")
    if not creator:
        missing_required.append("creator")
    if not year:
        missing_required.append("year")

    final_title = title or fallback.title
    final_creator = creator or fallback.creator
    final_publisher = publisher or fallback.publisher
    final_year = year or fallback.year

    return (
        BookMetadata(
            title=final_title,
            creator=final_creator,
            publisher=final_publisher,
            year=final_year,
            description=f"{final_title}. Издание {final_year} года.",
        ),
        missing_required,
    )


def load_book_metadata(
    metadata_file: Path,
    fallback_metadata: BookMetadata | None = None,
) -> tuple[BookMetadata, bool, list[str]]:
    """Загружает метаданные из JSON. Возвращает мету, флаг чтения из файла и поля из example."""
    defaults = fallback_metadata or default_book_metadata()
    example_fields_used = list(REQUIRED_META_FIELDS)
    if not metadata_file.exists():
        return defaults, False, example_fields_used

    try:
        payload = json.loads(metadata_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults, False, example_fields_used

    if not isinstance(payload, dict):
        return defaults, False, example_fields_used

    title_raw = payload.get("title")
    creator_raw = payload.get("creator")
    year_raw = payload.get("year")

    title = _clean_str(title_raw, defaults.title)
    creator = _clean_str(creator_raw, defaults.creator)
    year = _clean_str(year_raw, defaults.year)

    example_fields_used = []
    if not isinstance(title_raw, str) or not title_raw.strip():
        example_fields_used.append("title")
    if not isinstance(creator_raw, str) or not creator_raw.strip():
        example_fields_used.append("creator")
    if not isinstance(year_raw, str) or not year_raw.strip():
        example_fields_used.append("year")

    publisher = _clean_str(payload.get("publisher"), "Unknown Publisher")
    description = _clean_str(
        payload.get("description"),
        f"{title}. Издание {year} года.",
    )

    return (
        BookMetadata(
            title=title,
            creator=creator,
            publisher=publisher,
            year=year,
            description=description,
        ),
        True,
        example_fields_used,
    )


def save_book_metadata(metadata_file: Path, metadata: BookMetadata) -> None:
    payload = {
        "title": metadata.title,
        "creator": metadata.creator,
        "publisher": metadata.publisher,
        "year": metadata.year,
        "description": metadata.description,
    }
    metadata_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def ensure_metadata_files(
    metadata_file: Path,
    metadata_example_file: Path,
    source_file: Path,
) -> tuple[bool, bool, list[str]]:
    """Создаёт шаблон и при отсутствии meta.json пытается заполнить его из исходного файла с fallback к meta.example."""
    example_created = False
    metadata_created = False
    example_fields_used_on_bootstrap: list[str] = []

    if not metadata_example_file.exists():
        save_book_metadata(metadata_example_file, default_book_metadata())
        example_created = True

    if not metadata_file.exists():
        example_metadata = load_example_metadata(metadata_example_file)
        source_text = _try_extract_source_text(source_file)
        if source_text:
            metadata, missing_required = guess_metadata_from_text(
                source_text,
                example_metadata,
            )
            example_fields_used_on_bootstrap = missing_required
        else:
            metadata = example_metadata
            example_fields_used_on_bootstrap = list(REQUIRED_META_FIELDS)

        save_book_metadata(metadata_file, metadata)
        metadata_created = True

    return example_created, metadata_created, example_fields_used_on_bootstrap
