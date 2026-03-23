"""
parsing package — public API.

All imports from the old flat parsing.py continue to work unchanged.
"""

from .cleaning import (
    chapter_number_key,
    clean_line,
    clean_paragraph,
    detect_language,
    is_chapter_heading,
    normalize_title,
    remove_boilerplate_text,
    remove_urls_and_domains,
)
from .noise import (
    detect_repeated_noise_lines,
    detect_running_footer_titles,
    is_running_footer_line,
)
from .chapters import (
    collect_profile_heading_parts,
    extract_toc_entries,
    fallback_chapters,
    identify_chapters,
    identify_numbered_profile_chapters,
    resolve_title_with_toc,
)
from .formatting import (
    chapter_blocks,
    is_minor_subheading,
    parse_table_rows,
    split_columns,
)

__all__ = [
    # cleaning
    "chapter_number_key",
    "clean_line",
    "clean_paragraph",
    "detect_language",
    "is_chapter_heading",
    "normalize_title",
    "remove_boilerplate_text",
    "remove_urls_and_domains",
    # noise
    "detect_repeated_noise_lines",
    "detect_running_footer_titles",
    "is_running_footer_line",
    # chapters
    "collect_profile_heading_parts",
    "extract_toc_entries",
    "fallback_chapters",
    "identify_chapters",
    "identify_numbered_profile_chapters",
    "resolve_title_with_toc",
    # formatting
    "chapter_blocks",
    "is_minor_subheading",
    "parse_table_rows",
    "split_columns",
]
