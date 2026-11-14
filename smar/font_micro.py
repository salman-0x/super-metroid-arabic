"""Condensed Arabic glyphs (6 rows, 1 px strokes) derived from the 8x8 art of font_ar, for labels that only have 5-6 px of height.

Derivation (so every letter keeps its shape family and joins): rows 3 and 6 of the 8x8 art are dropped (rows 0,1,2,4,5,7 are kept),
every horizontal run of exactly two ink pixels becomes one (2 px stems and dots -> 1 px), then empty margin columns are cropped.
Joins are preserved because the baseline row is a long run and is never shortened.  Per-glyph overrides can replace any result.
"""
import re

from . import font_ar as F

KEEP_ROWS = (0, 1, 2, 4, 5, 7)
OVERRIDES = {}          # (letter, form) -> 6 rows of '#'/'.', for glyphs the derivation spoils


def _squeeze(row):
    return re.sub(r"(?<!#)##(?!#)", "#", row)


def glyph(letter, form, target=None):
    """-> 6 rows of '#'/'.' (variable width, margins cropped but join columns kept)."""
    if (letter, form) in OVERRIDES:
        return OVERRIDES[(letter, form)]
    rows = F.glyph_pixels(letter, form)
    rows = [_squeeze(rows[y]) for y in KEEP_ROWS]
    # squeezing shortens rows unevenly: left-align the shortened rows on the original column of their first ink pixel
    cols = [x for x in range(max(len(r) for r in rows)) if any(x < len(r) and r[x] == "#" for r in rows)]
    w = max(len(r) for r in rows)
    rows = [r.ljust(w, ".") for r in rows]
    rows = [r[min(cols):max(cols) + 1] for r in rows]
    return _shorten(rows, target or TARGET_WIDTH)


TARGET_WIDTH = 5


def _shorten(rows, target=TARGET_WIDTH):
    """Remove interior columns that repeat their left neighbour (flat baseline / bowl runs) until the glyph is TARGET_WIDTH wide."""
    while len(rows[0]) > target:
        w = len(rows[0])
        col = lambda x: "".join(r[x] for r in rows)          # noqa: E731
        dup = [x for x in range(1, w - 1) if col(x) == col(x - 1)]
        if not dup:
            break
        x = dup[len(dup) // 2]
        rows = [r[:x] + r[x + 1:] for r in rows]
    return rows
