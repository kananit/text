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


_COVER_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"]

COVER_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def resolve_pdf_file() -> Path:
    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"В папке {PDF_DIR} не найден PDF-файл (*.pdf).")
    return pdf_files[0]


def resolve_epub_output(pdf_file: Path) -> Path:
    return PDF_DIR / f"{pdf_file.stem}.epub"


def resolve_cover_image(pdf_file: Path) -> Path | None:
    """Ищет обложку рядом с PDF: <имя_pdf>_cover.ext, <имя_pdf>.ext, cover.ext, любой *.jpeg/*.jpg."""
    for ext in _COVER_EXTENSIONS:
        candidate = PDF_DIR / f"{pdf_file.stem}_cover{ext}"
        if candidate.exists():
            return candidate
    for ext in _COVER_EXTENSIONS:
        candidate = PDF_DIR / f"{pdf_file.stem}{ext}"
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
