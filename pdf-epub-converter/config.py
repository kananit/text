from pathlib import Path
import shutil


BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIR = BASE_DIR / "pdf-epub"
EPUB_BUILD_DIR = SOURCE_DIR / "epub_build"
EXTRACTED_TEXT_FILE = Path("/tmp/document_epub_extracted.txt")
METADATA_FILE = SOURCE_DIR / "meta.json"
METADATA_EXAMPLE_FILE = BASE_DIR / "pdf-epub-converter" / "meta.example.json"

EXAMPLE_META_TITLE = "Название книги"
EXAMPLE_META_CREATOR = "Имя Автора"
EXAMPLE_META_YEAR = "2000"

REQUIRED_META_FIELDS = ("title", "creator", "year")

FOOTER_MIN_OCCURRENCES = 5

# Minor subheading detection (UPPERCASE lines inside chapter body)
MINOR_SUBHEADING_ENABLED = True  # False — treat as regular h2
MINOR_SUBHEADING_MAX_LEN = 100  # chars; longer lines are never a subheading
MINOR_SUBHEADING_UPPERCASE_RATIO = 0.85  # fraction of uppercase letters required


_COVER_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"]

COVER_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def resolve_source_file() -> Path:
    candidates = [
        *sorted(SOURCE_DIR.glob("*.pdf")),
        *sorted(SOURCE_DIR.glob("*.docx")),
        *sorted(SOURCE_DIR.glob("*.doc")),
    ]
    if not candidates:
        raise FileNotFoundError(
            f"В папке {SOURCE_DIR} не найден исходный файл (*.pdf, *.docx, *.doc)."
        )
    return candidates[0]


def resolve_epub_output(source_file: Path) -> Path:
    return SOURCE_DIR / f"{source_file.stem}.epub"


def resolve_cover_image(source_file: Path) -> Path | None:
    """Ищет обложку рядом с исходным файлом: <имя>_cover.ext, <имя>.ext, cover.ext, любой *.jpeg/*.jpg."""
    for ext in _COVER_EXTENSIONS:
        candidate = SOURCE_DIR / f"{source_file.stem}_cover{ext}"
        if candidate.exists():
            return candidate
    for ext in _COVER_EXTENSIONS:
        candidate = SOURCE_DIR / f"{source_file.stem}{ext}"
        if candidate.exists():
            return candidate
    for ext in _COVER_EXTENSIONS:
        candidate = SOURCE_DIR / f"cover{ext}"
        if candidate.exists():
            return candidate
    jpeg_files = sorted([*SOURCE_DIR.glob("*.jpeg"), *SOURCE_DIR.glob("*.jpg")])
    if jpeg_files:
        return jpeg_files[0]
    return None


def cleanup_temp_files() -> None:
    if EXTRACTED_TEXT_FILE.exists():
        EXTRACTED_TEXT_FILE.unlink()
    if EPUB_BUILD_DIR.is_dir():
        shutil.rmtree(EPUB_BUILD_DIR, ignore_errors=True)


def ensure_build_dirs() -> None:
    cleanup_temp_files()
    (EPUB_BUILD_DIR / "OEBPS" / "text").mkdir(parents=True, exist_ok=True)
    (EPUB_BUILD_DIR / "OEBPS" / "css").mkdir(parents=True, exist_ok=True)
    (EPUB_BUILD_DIR / "OEBPS" / "images").mkdir(parents=True, exist_ok=True)
    (EPUB_BUILD_DIR / "META-INF").mkdir(parents=True, exist_ok=True)
