from pathlib import Path
import shutil


BASE_DIR = Path(__file__).resolve().parent.parent
PDF_DIR = BASE_DIR / "pdf-epub"
PDF_FILE = PDF_DIR / "WarOnTheSaints.pdf"
BUILD_DIR = PDF_DIR / "epub_from_pdf"
TEMP_TXT = Path("/tmp/war_saints_extracted.txt")
EPUB_OUTPUT = PDF_DIR / "WarOnTheSaints_Professional.epub"

BOOK_TITLE = "War with the Saints"
BOOK_CREATOR = "Jessie Penn-Lewis"
BOOK_CONTRIBUTOR = "Evan Roberts"
BOOK_DESCRIPTION = (
    "A classic work on spiritual warfare, deliverance from demonic oppression, "
    "and Christian victory."
)


def cleanup_temp_files() -> None:
    if TEMP_TXT.exists():
        TEMP_TXT.unlink()
    if BUILD_DIR.is_dir():
        shutil.rmtree(BUILD_DIR, ignore_errors=True)


def ensure_build_dirs() -> None:
    cleanup_temp_files()
    (BUILD_DIR / "OEBPS" / "text").mkdir(parents=True, exist_ok=True)
    (BUILD_DIR / "OEBPS" / "css").mkdir(parents=True, exist_ok=True)
    (BUILD_DIR / "META-INF").mkdir(parents=True, exist_ok=True)
