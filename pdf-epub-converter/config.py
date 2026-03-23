from pathlib import Path
import shutil


BASE_DIR = Path(__file__).resolve().parent.parent
PDF_DIR = BASE_DIR / "pdf-epub"
BUILD_DIR = PDF_DIR / "epub_from_pdf"
TEMP_TXT = Path("/tmp/pdf_epub_extracted.txt")
METADATA_FILE = PDF_DIR / "meta.json"
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
        *sorted(PDF_DIR.glob("*.pdf")),
        *sorted(PDF_DIR.glob("*.docx")),
        *sorted(PDF_DIR.glob("*.doc")),
    ]
    if not candidates:
        raise FileNotFoundError(
            f"В папке {PDF_DIR} не найден исходный файл (*.pdf, *.docx, *.doc)."
        )
    return candidates[0]


def resolve_pdf_file() -> Path:
    """Совместимость со старыми скриптами, которые ждут именно PDF."""
    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"В папке {PDF_DIR} не найден PDF-источник (*.pdf).")
    return pdf_files[0]


def resolve_epub_output(source_file: Path) -> Path:
    return PDF_DIR / f"{source_file.stem}.epub"


def resolve_cover_image(source_file: Path) -> Path | None:
    """Ищет обложку рядом с исходным файлом: <имя>_cover.ext, <имя>.ext, cover.ext, любой *.jpeg/*.jpg."""
    for ext in _COVER_EXTENSIONS:
        candidate = PDF_DIR / f"{source_file.stem}_cover{ext}"
        if candidate.exists():
            return candidate
    for ext in _COVER_EXTENSIONS:
        candidate = PDF_DIR / f"{source_file.stem}{ext}"
        if candidate.exists():
            return candidate
    for ext in _COVER_EXTENSIONS:
        candidate = PDF_DIR / f"cover{ext}"
        if candidate.exists():
            return candidate
    jpeg_files = sorted([*PDF_DIR.glob("*.jpeg"), *PDF_DIR.glob("*.jpg")])
    if jpeg_files:
        return jpeg_files[0]
    return None


def cleanup_temp_files() -> None:
    if TEMP_TXT.exists():
        TEMP_TXT.unlink()
    if BUILD_DIR.is_dir():
        shutil.rmtree(BUILD_DIR, ignore_errors=True)


def ensure_build_dirs() -> None:
    cleanup_temp_files()
    (BUILD_DIR / "OEBPS" / "text").mkdir(parents=True, exist_ok=True)
    (BUILD_DIR / "OEBPS" / "css").mkdir(parents=True, exist_ok=True)
    (BUILD_DIR / "OEBPS" / "images").mkdir(parents=True, exist_ok=True)
    (BUILD_DIR / "META-INF").mkdir(parents=True, exist_ok=True)
