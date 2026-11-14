"""Packed 8-row Arabic words for fixed-width graphics labels (pause screen buttons and boxes).
The 8x8 glyph art is cropped to its ink columns; consecutive glyphs that connect keep their touching edge columns, the others get
a 1 px gap.  Result: list of 8 strings of '#'/'.' of exactly the packed width."""
from . import arabic as A
from . import font_ar as F
from . import font_micro as FM

CS = A.Charset(space=0x00F, latin={}, punct={})


def _crop(key, micro=False, target=None):
    if micro:
        return FM.glyph(*key, target=target)
    rows = F.glyph_pixels(*key)
    cols = [x for x in range(8) if any(r[x] == "#" for r in rows)]
    return [r[min(cols):max(cols) + 1] for r in rows]


def pack(text, gap=1, micro=False, target=None):
    """-> 8 rows of the packed word, visual left to right (right-to-left script, no Latin)."""
    units = A.shape(text, CS)                                  # logical order
    glyphs = []                                                # (key, joined_to_previous_logical)
    for i, (kind, val) in enumerate(units):
        if kind == "R":
            joined = i > 0 and units[i - 1][0] == "R" and val[1] in "MF"
            glyphs.append((val, joined))
        elif kind == "N" and val == CS.space:
            glyphs.append((None, False))
        else:
            raise ValueError(f"unsupported unit {kind} {val} in {text!r}")
    n = 6 if micro else 8
    cols = [[] for _ in range(n)]
    for idx, (key, joined) in enumerate(glyphs):               # logical order = right to left; build from the right
        piece = ["..."] * n if key is None else _crop(key, micro, target)
        if idx and not joined and gap:                          # `gap` px before an unconnected glyph
            for y in range(n):
                cols[y].insert(0, "." * gap)
        for y in range(n):
            cols[y].insert(0, piece[y])
    return ["".join(c) for c in cols]


def width(text):
    return len(pack(text)[0])


if __name__ == "__main__":
    import sys
    for t in sys.argv[1:]:
        print(width(t), t)
        print("\n".join(r.replace(".", " ").replace("#", "█") for r in pack(t)))
