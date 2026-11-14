"""For every glyph form: count isolated 2x2 dots in the 8x16 raster and compare with the number of dots the letter has.
Prints the forms that disagree. Usage: python tools/check_big_dots.py"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar import font_ar as F, font_big as FB

EXPECT = {"ب": 1, "ت": 2, "ث": 3, "ج": 1, "خ": 1, "ذ": 1, "ز": 1, "ش": 3, "ض": 1, "ظ": 1, "غ": 1, "ف": 1, "ق": 2, "ن": 1,
          "ي": 2, "ة": 2}          # hamza letters (ؤ ئ) carry a hamza shape, not dots: not measured here


def comps(rows):
    seen, out = set(), []
    for y in range(16):
        for x in range(8):
            if rows[y][x] == "#" and (x, y) not in seen:
                st, pts = [(x, y)], []
                seen.add((x, y))
                while st:
                    cx, cy = st.pop()
                    pts.append((cx, cy))
                    for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                        if 0 <= nx < 8 and 0 <= ny < 16 and rows[ny][nx] == "#" and (nx, ny) not in seen:
                            seen.add((nx, ny))
                            st.append((nx, ny))
                out.append(pts)
    return out


def dots(rows):
    """Number of separate dot marks: isolated components of at most 4 px that are 2 wide (2x2, or 2x1 where the cell had no room)."""
    n = 0
    for pts in comps(rows):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        if len(pts) <= 4 and max(xs) - min(xs) <= 1 and max(ys) - min(ys) <= 1:      # 2x2, 2x1 or the 1x1 last resort
            n += 1
    return n


bad = []
for ch, f in F.all_glyph_keys():
    if ch not in EXPECT:
        continue
    g = FB.glyph16(ch, f)
    got = dots(g)
    if got != EXPECT[ch]:
        bad.append((ch, f, got, EXPECT[ch]))
print("forms checked:", sum(1 for k in F.all_glyph_keys() if k[0] in EXPECT))
print("forms with the wrong number of separate 2x2 dots:", len(bad))
for b in bad:
    print("  ", b)
