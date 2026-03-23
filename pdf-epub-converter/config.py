from pathlib import Path
import shutil


BASE_DIR = Path(__file__).resolve().parent.parent
PDF_DIR = BASE_DIR / "pdf-epub"
PDF_FILE = PDF_DIR / "WarOnTheSaints.pdf"
BUILD_DIR = PDF_DIR / "epub_from_pdf"
TEMP_TXT = Path("/tmp/war_saints_extracted.txt")
EPUB_OUTPUT = PDF_DIR / "WarOnTheSaints_Professional.epub"

BOOK_TITLE = "Война со святыми"
BOOK_CREATOR = "Эван Робертс, Дж. Пенн-Луис"
BOOK_PUBLISHER = "ХБИФ"
BOOK_YEAR = "1997"
BOOK_DESCRIPTION = "Война со святыми. Издание 1997 года."


_COVER_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"]

COVER_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def resolve_cover_image() -> Path | None:
    """Ищет обложку рядом с PDF: <имя_pdf>_cover.ext или cover.ext"""
    for ext in _COVER_EXTENSIONS:
        candidate = PDF_DIR / f"{PDF_FILE.stem}_cover{ext}"
        if candidate.exists():
            return candidate
    for ext in _COVER_EXTENSIONS:
        candidate = PDF_DIR / f"cover{ext}"
        if candidate.exists():
            return candidate
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
