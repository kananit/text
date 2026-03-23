import re
import sys

sys.path.insert(0, ".")
from extraction import extract_text
from config import resolve_source_file
from pathlib import Path

src = resolve_source_file()
text = extract_text(src, Path("/tmp/tmp_debug.txt"))
lines = text.split("\n")

print(f"Total lines: {len(lines)}\n")

# Show all lines matching chapter heading pattern
found = 0
for i, line in enumerate(lines):
    stripped = line.strip()
    if re.match(
        r"^(глава|часть|раздел|chapter|part)\s+[0-9ivxlcdm]+", stripped, re.IGNORECASE
    ):
        print(f"[{i}] {repr(stripped)}")
        for j in range(1, 5):
            if i + j < len(lines):
                print(f"  [{i+j}] {repr(lines[i+j])}")
        print()
        found += 1

print(f"\nTotal chapter-heading lines found: {found}")
