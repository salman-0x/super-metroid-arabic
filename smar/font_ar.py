"""Arabic 8x8 2bpp bitmap font (hand-drawn, original work) for Super Metroid's BG3 message font.  Version 2.

Conventions (match the original English font at $9A:B200):
  * pixel index 1 = ink, index 3 = box background (index 0 is transparent and must NOT appear inside the box)
  * 8x8 cells, baseline (the connecting stroke) on row 4, dots above on rows 0-1, dots/descenders on rows 5-7
  * every glyph is exactly 8 px wide so text stays on the tile grid (monospaced)
  * a glyph that joins its left neighbour touches x=0 on row 4, one that joins its right neighbour touches x=7

Forms: I isolated, N initial (joins the NEXT letter = left), M medial, F final (joins the PREVIOUS letter = right).
Bodies are shared between letters that differ only by dots; dots are an overlay.

v2 design rules (legibility at 1x):
  * vertical stems (alef, lam, tah, kaf) are 2 px wide to match the weight of the game's own bold font
  * dots outside the body are 2 px wide where there is room (single dots) so they read as dots, not specks
  * letters that differ only in the shape of their head have heads of clearly different size/fill:
      meem = solid 3x3 head, feh = hollow 3x3 head + dot above, sad = hollow 4x2 head, seen = 3 two-pixel teeth
"""
import struct

INK, BG = 1, 3
FORMS = "INMF"


def A(*rows):
    rows = list(rows) + ["........"] * (8 - len(rows))
    assert len(rows) == 8 and all(len(r) == 8 for r in rows), rows
    return rows


BASES = {
    # ---- right-joining only (forms I, F) ----
    "alef_I": A("...##...", "...##...", "...##...", "...##...", "...##..."),
    "alef_F": A("....##..", "....##..", "....##..", "....##..", "....####"),
    "alefh_I": A("........", "........", "...##...", "...##...", "...##..."),      # stem for أ / آ (room above)
    "alefh_F": A("........", "........", "....##..", "....##..", "....####"),
    "dal_I": A("........", "........", "..###...", ".....#..", ".....#..", "..###..."),
    "dal_F": A("........", "........", "..###...", ".....#..", ".....###", "..###..."),
    "reh_I": A("........", "........", "......##", "......#.", ".....#..", "....#...", "..##....", ".#......"),
    "reh_F": A("........", "........", "........", "........", ".....###", "....#...", "...#....", ".##....."),
    "waw_I": A("........", "........", "...###..", "...#.#..", "...###..", "....#...", "...#....", ".##....."),
    "waw_F": A("........", "........", "...###..", "...#.#..", "...#####", "....#...", "...#....", ".##....."),
    "teh_marbuta_I": A("........", "........", "...##...", "..#..#..", "..#..#..", "...##..."),
    "teh_marbuta_F": A("........", "........", "...##...", "..#..#..", "..#..###", "...##..."),
    "hamza_I": A("........", "........", "........", "...##...", "..#.....", "...##...", "........"),
    # lam (left stem, with the lam's lower hook) + alef (right stem) meeting in a V: not confusable with digits
    "lamalef_I": A("..##.#..", "..##.#..", "..##.#..", "...###..", "...##...", "..#.....", ".#......"),
    "lamalef_F": A("..##.#..", "..##.#..", "..##.#..", "...###..", "...#####", "..#.....", ".#......"),
    # ---- dual-joining ----
    "beh_N": A("........", "........", "........", "......#.", "#######."),
    "beh_M": A("........", "........", "........", "....#...", "########"),
    "beh_F": A("........", "........", "........", "........", "#......#", ".######."),
    "beh_I": A("........", "........", "........", "........", "#.....#.", ".#####.."),
    "nun_F": A("........", "........", "........", "........", "#......#", "#......#", ".######."),
    "nun_I": A("........", "........", "........", "........", "#.....#.", "#.....#.", ".#####.."),
    "yeh_F": A("........", "........", "........", "........", "......##", ".#####..", "#......."),
    "yeh_I": A("........", "........", "........", "........", ".....#..", ".#####..", "#......."),
    "jeem_N": A("........", "........", "........", "..#####.", "##......"),
    "jeem_M": A("........", "........", "........", "..####..", "##....##"),
    "jeem_F": A("........", "........", "........", "..####..", ".#....##", ".#......", "..####.."),
    "jeem_I": A("........", "........", "........", "..####..", ".#....#.", ".#......", "..####.."),
    # seen: three 2-px-tall teeth
    "seen_N": A("........", "........", ".#.#.#..", ".#.#.#..", "#######."),
    "seen_M": A("........", "........", ".#.#.#..", ".#.#.#..", "########"),
    "seen_F": A("........", "........", "..#.#.#.", "..#.#.#.", "########", "#......#", ".######."),
    "seen_I": A("........", "........", "..#.#.#.", "..#.#.#.", "#######.", "#.....#.", ".#####.."),
    # sad: hollow wide head (4 wide)
    "sad_N": A("........", "........", "...####.", "...#..#.", "#######."),
    "sad_M": A("........", "........", "..####..", "..#..#..", "########"),
    "sad_F": A("........", "........", "..####..", "..#..#..", "########", "#......#", ".######."),
    "sad_I": A("........", "........", "..####..", "..#..#..", "#######.", "#.....#.", ".#####.."),
    # tah: 2-px ascender + hollow 3x3 head
    "tah_N": A("...##...", "...##...", "...###..", "...#.#..", "#######."),
    "tah_M": A("...##...", "...##...", "...###..", "...#.#..", "########"),
    "tah_F": A("..##....", "..##....", "..###...", "..#.#...", "..######"),
    "tah_I": A("..##....", "..##....", "..###...", "..#.#...", "..###..."),
    "ain_N": A("........", "........", "...###..", "..#...#.", "####.##."),
    "ain_M": A("........", "........", "...###..", "..#...#.", "####.###"),
    "ain_F": A("........", "........", "...###..", "..#...#.", "...#####", ".#......", "..####.."),
    "ain_I": A("........", "........", "...###..", "..#...#.", "...#.##.", ".#......", "..####.."),
    # feh/qaf: hollow 3x3 head (smaller than sad's), dots above
    "feh_N": A("........", "........", "....###.", "....#.#.", "#######."),
    "feh_M": A("........", "........", "...###..", "...#.#..", "########"),
    "feh_F": A("........", "........", "...###..", "...#.#..", "...#####", "..#.....", ".#####.."),
    "feh_I": A("........", "........", "...###..", "...#.#..", "...###..", "..#.....", ".#####.."),
    # kaf: 2-px stem with the characteristic inner bar
    "kaf_N": A(".....##.", ".....##.", "...####.", ".....##.", "#######."),
    "kaf_M": A("...##...", "...##...", ".####...", "...##...", "########"),
    "kaf_F": A("...##...", "...##...", ".####...", "...##...", "...#####", "..#.....", ".#......"),
    "kaf_I": A("....##..", "....##..", "..####..", "....##..", ".######.", "........"),
    "lam_N": A(".....##.", ".....##.", ".....##.", ".....##.", "#######."),
    "lam_M": A("...##...", "...##...", "...##...", "...##...", "########"),
    "lam_F": A("...##...", "...##...", "...##...", "...##...", "...#####", "..#.....", ".#......"),
    "lam_I": A("....##..", "....##..", "....##..", "....##..", "....##..", "...#....", "..#....."),
    # meem: solid 3x3 head
    "meem_N": A("........", "........", "....###.", "....###.", "#######."),
    "meem_M": A("........", "........", "...###..", "...###..", "########"),
    "meem_F": A("........", "........", "...###..", "...###..", "...#####", "...#....", "...#...."),
    "meem_I": A("........", "........", "..###...", "..###...", "..###...", "...#....", "...#...."),
    "heh_N": A("........", "........", "....##..", "...#..#.", "####.##."),
    "heh_M": A("........", "........", "...##...", "..#..#..", "###..###"),
    "heh_F": A("........", "........", "...##...", "..#..#..", "..#..###", "...##..."),
    "heh_I": A("........", "........", "...##...", "..#..#..", "..#..#..", "...##..."),
}


def D2(*xs, y):
    """Horizontal 2-px dots: each x becomes (x, y),(x+1, y)."""
    return [p for x in xs for p in ((x, y), (x + 1, y))]


# dot overlays ----------------------------------------------------------------------------------
DOT1B = D2(3, y=7)                      # ب
DOT2A = D2(2, 5, y=1)                   # ت
DOT3A = [(4, 0), (2, 1), (6, 1)]        # ث (single pixels: three 2-px dots would not fit)
DOT1A = D2(3, y=1)                      # ن
DOT2B = D2(2, 5, y=7)                   # ي
HAMZA = [(4, 0), (5, 0), (3, 1), (4, 1)]


def _fam(prefix, forms, dots):
    """dots: list (same for all forms) or dict form->list."""
    out = {}
    for f in forms:
        d = dots[f] if isinstance(dots, dict) else dots
        out[f] = (f"{prefix}_{f}", list(d))
    return out


LETTERS = {
    "ا": _fam("alef", "IF", []),
    "أ": {"I": ("alefh_I", D2(3, y=0)), "F": ("alefh_F", D2(4, y=0))},
    "إ": {"I": ("alef_I", D2(3, y=6)), "F": ("alef_F", D2(4, y=6))},
    "آ": {"I": ("alefh_I", [(3, 0), (4, 0), (2, 1), (5, 1)]), "F": ("alefh_F", [(4, 0), (5, 0), (3, 1), (6, 1)])},
    "ب": _fam("beh", "INMF", DOT1B),
    "ت": _fam("beh", "INMF", DOT2A),
    "ث": _fam("beh", "INMF", DOT3A),
    "ج": _fam("jeem", "INMF", D2(3, y=5)),
    "ح": _fam("jeem", "INMF", []),
    "خ": _fam("jeem", "INMF", D2(3, y=1)),
    "د": _fam("dal", "IF", []),
    "ذ": _fam("dal", "IF", D2(3, y=0)),
    "ر": _fam("reh", "IF", []),
    "ز": _fam("reh", "IF", {"I": D2(4, y=1), "F": D2(4, y=2)}),
    "س": _fam("seen", "INMF", []),
    "ش": _fam("seen", "INMF", {"N": [(1, 0), (3, 0), (5, 0)], "M": [(1, 0), (3, 0), (5, 0)],
                               "F": [(2, 0), (4, 0), (6, 0)], "I": [(2, 0), (4, 0), (6, 0)]}),
    "ص": _fam("sad", "INMF", []),
    "ض": _fam("sad", "INMF", D2(3, y=0)),
    "ط": _fam("tah", "INMF", []),
    "ظ": _fam("tah", "INMF", D2(5, y=0)),
    "ع": _fam("ain", "INMF", []),
    "غ": _fam("ain", "INMF", D2(3, y=0)),
    "ف": _fam("feh", "INMF", {"N": D2(4, y=0), "M": D2(3, y=0), "F": D2(3, y=0), "I": D2(3, y=0)}),
    "ق": _fam("feh", "INMF", {"N": [(4, 0), (6, 0)], "M": [(3, 0), (5, 0)], "F": [(3, 0), (5, 0)], "I": [(3, 0), (5, 0)]}),
    "ك": _fam("kaf", "INMF", []),
    "ل": _fam("lam", "INMF", []),
    "م": _fam("meem", "INMF", []),
    "ن": {"N": ("beh_N", DOT1A), "M": ("beh_M", DOT1A), "F": ("nun_F", DOT1A), "I": ("nun_I", DOT1A)},
    "ه": _fam("heh", "INMF", []),
    "و": _fam("waw", "IF", []),
    "ؤ": {"I": ("waw_I", [(1, 3), (2, 3)]), "F": ("waw_F", [(1, 3), (2, 3)])},
    "ي": {"N": ("beh_N", DOT2B), "M": ("beh_M", DOT2B), "F": ("yeh_F", DOT2B), "I": ("yeh_I", DOT2B)},
    "ى": {"F": ("yeh_F", []), "I": ("yeh_I", [])},
    "ئ": {"N": ("beh_N", HAMZA), "M": ("beh_M", HAMZA), "F": ("yeh_F", HAMZA), "I": ("yeh_I", HAMZA)},
    "ة": {"I": ("teh_marbuta_I", D2(2, 4, y=0)), "F": ("teh_marbuta_F", D2(2, 4, y=0))},
    "ء": {"I": ("hamza_I", [])},
    "ﻻ": {"I": ("lamalef_I", []), "F": ("lamalef_F", [])},   # لا ligature
}

# Characters that join to the following letter (dual-joining) / only to the preceding one (right-joining)
DUAL = set("بتثجحخسشصضطظعغفقكلمنهيئى")
RIGHT_ONLY = set("اأإآدذرزوؤة")
NON_JOINING = set("ء")


def glyph_pixels(letter, form):
    base, dots = LETTERS[letter][form]
    rows = [list(r) for r in BASES[base]]
    for x, y in dots:
        assert 0 <= x < 8 and 0 <= y < 8, (letter, form, x, y)
        rows[y][x] = "#"
    return ["".join(r) for r in rows]


def thicken_baseline(rows):
    """Second row under the connecting baseline (row 4) wherever that cell and the one below it are free.
    Keeps counters (teeth gaps, holes) and the gap above the lower dots open; used for the on-screen weight."""
    out = [list(r) for r in rows]
    for x in range(8):
        if out[4][x] == "#" and out[5][x] != "#" and out[6][x] != "#":
            out[5][x] = "#"
    return ["".join(r) for r in out]


def all_glyph_keys():
    return [(ch, f) for ch, forms in LETTERS.items() for f in FORMS if f in forms]


def encode_tile(rows):
    """rows: 8 strings of '#'/'.' -> 16 bytes of SNES 2bpp (ink=1, background=3)."""
    out = bytearray()
    for r in rows:
        p0 = p1 = 0
        for x, c in enumerate(r):
            v = INK if c == "#" else BG
            p0 |= (v & 1) << (7 - x)
            p1 |= ((v >> 1) & 1) << (7 - x)
        out += bytes([p0, p1])
    return bytes(out)


def decode_tile(b):
    rows = []
    for y in range(8):
        p0, p1 = b[2 * y], b[2 * y + 1]
        rows.append("".join(
            "#" if (((p0 >> (7 - x)) & 1) | (((p1 >> (7 - x)) & 1) << 1)) == INK else "." for x in range(8)))
    return rows


FIRST_TILE = 0x100          # tiles 0x100-0x1FF live in the zero-filled upper half of the 8 KB font block


def tile_table():
    """Stable tile assignment: sorted by (letter, form) so ids never move when glyph art changes."""
    keys = sorted(all_glyph_keys(), key=lambda k: (k[0], FORMS.index(k[1])))
    if FIRST_TILE + len(keys) > 0x200:
        raise ValueError("too many glyphs")
    return {k: FIRST_TILE + i for i, k in enumerate(keys)}


def build_font_bytes():
    """4096 bytes for tiles 0x100-0x1FF. Unused tiles stay zero, exactly as in the original ROM."""
    table = tile_table()
    buf = bytearray(0x1000)
    for (ch, f), tid in table.items():
        # on-screen weight: the art is drawn with 1-px horizontals; the baseline gets a second row at encode time
        buf[(tid - FIRST_TILE) * 16:(tid - FIRST_TILE + 1) * 16] = encode_tile(thicken_baseline(glyph_pixels(ch, f)))
    return bytes(buf), table
