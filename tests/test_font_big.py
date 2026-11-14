import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from smar import font_ar as F  # noqa: E402
from smar import font_big as FB  # noqa: E402
from smar import menu_ar as M  # noqa: E402

KEYS = F.all_glyph_keys()
# number of dots each letter carries (hamza letters carry a hamza shape, not dots)
DOTS = {"ب": 1, "ت": 2, "ث": 3, "ج": 1, "خ": 1, "ذ": 1, "ز": 1, "ش": 3, "ض": 1, "ظ": 1, "غ": 1, "ف": 1, "ق": 2, "ن": 1,
        "ي": 2, "ة": 2}


def components(rows):
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


def dot_marks(rows):
    return sum(1 for pts in components(rows) if len(pts) <= 4 and
               max(p[0] for p in pts) - min(p[0] for p in pts) <= 1 and max(p[1] for p in pts) - min(p[1] for p in pts) <= 1)


class TestRaster(unittest.TestCase):
    def test_every_form_has_a_16_row_glyph(self):
        for key in KEYS:
            g = FB.glyph16(*key)
            self.assertIsNotNone(g, key)
            self.assertEqual(len(g), 16)
            for r in g:
                self.assertEqual(len(r), 8)
                self.assertTrue(set(r) <= {"#", "."})

    def test_deterministic(self):
        for key in KEYS[::7]:
            self.assertEqual(FB.glyph16(*key), FB.glyph16(*key))

    def test_parameters_are_pinned(self):
        self.assertEqual((FB.WEIGHT, FB.THRESHOLD, FB.PX_PER_EM, FB.BASE_ROWS), ("regular", 0.30, 14.0, (10, 11)))

    def test_joins_reach_the_cell_edges_on_both_baseline_rows(self):
        for ch, f in KEYS:
            if ch == "ﻻ":
                continue
            g = FB.glyph16(ch, f)
            for y in FB.BASE_ROWS:
                if f in "NM":
                    self.assertEqual(g[y][0], "#", f"{ch} {f} row {y}: no ink at the left edge")
                if f in "MF":
                    self.assertEqual(g[y][7], "#", f"{ch} {f} row {y}: no ink at the right edge")

    def test_non_joining_sides_keep_a_margin_on_the_baseline(self):
        for ch, f in KEYS:
            if ch == "ﻻ":
                continue
            g = FB.glyph16(ch, f)
            if f in "IN":                                   # no join on the right: the right edge is empty on the baseline rows
                self.assertEqual([g[y][7] for y in FB.BASE_ROWS], [".", "."], f"{ch} {f} touches the right edge")
            if f in "IF":                                   # no join on the left: the left edge is empty on the baseline rows
                self.assertEqual([g[y][0] for y in FB.BASE_ROWS], [".", "."], f"{ch} {f} touches the left edge")

    def test_no_glyph_is_clipped_by_the_cell(self):
        for key in KEYS:
            FB.glyph16(*key)
            top, bottom = FB.EXTENTS[key]
            self.assertGreaterEqual(top, 0.0, f"{key} clipped at the top")
            self.assertLessEqual(bottom, 16.0, f"{key} clipped at the bottom")

    def test_hamza_and_madda_on_alef_are_visible(self):
        for ch in "أآ":
            for f in "IF":
                g = FB.glyph16(ch, f)
                self.assertIn("#", g[0] + g[1] + g[2], f"{ch} {f}: no mark in the top rows")
                self.assertTrue(any("#" in g[y] for y in FB.BASE_ROWS))        # the stem still reaches the baseline

    def test_hamza_below_alef_is_visible(self):
        for f in "IF":
            g = FB.glyph16("إ", f)
            self.assertIn("#", "".join(g[13:16]), f"إ {f}: no mark below the stem")

    def test_dotted_letters_have_their_dots_as_separate_marks(self):
        wrong = []
        for ch, f in KEYS:
            if ch not in DOTS:
                continue
            got = dot_marks(FB.glyph16(ch, f))
            if got != DOTS[ch]:
                wrong.append((ch, f, got, DOTS[ch]))
        self.assertEqual(wrong, [])

    def test_a_dot_is_separated_from_the_body_by_a_blank_row(self):
        g = FB.glyph16("ب", "I")                              # one dot below the bowl
        comps = sorted(components(g), key=len)
        self.assertEqual(len(comps), 2)
        dot, body = comps
        self.assertLessEqual(len(dot), 4)
        gap = min(p[1] for p in dot) - max(p[1] for p in body) - 1
        self.assertGreaterEqual(gap, 1, "the dot touches or crowds the bowl")

    def test_three_dots_form_a_triangle_with_gaps(self):
        g = FB.glyph16("ث", "I")
        small = [c for c in components(g) if len(c) <= 4]
        self.assertEqual(len(small), 3)
        ys = sorted({p[1] for c in small for p in c})
        xs = [(min(p[0] for p in c), max(p[0] for p in c)) for c in small]
        self.assertEqual(len(ys), 4)                          # apex rows + pair rows, separated by one blank row
        self.assertGreaterEqual(ys[2] - ys[1], 2)

    def test_stems_are_at_least_two_pixels_wide(self):
        for ch in "الط":
            g = FB.glyph16(ch, "I")
            stem_rows = [r for r in g[2:9] if "#" in r]
            self.assertTrue(stem_rows)
            self.assertTrue(all(r.count("#") >= 2 or ch == "ط" for r in stem_rows), ch)


class TestSeenSheen(unittest.TestCase):
    """The outline raster merges seen's three ~1 px teeth into a block; س/ش use a hand-drawn comb instead."""
    TEETH = {"N": [1, 3, 5], "M": [1, 3, 5, 7], "F": [2, 4, 6], "I": [2, 4, 6]}

    def test_three_separate_teeth_above_the_baseline(self):
        for ch in "سش":
            for f in "NMFI":
                g = FB.glyph16(ch, f)
                for y in (7, 8, 9):
                    self.assertEqual([x for x in range(8) if g[y][x] == "#"], self.TEETH[f], f"{ch} {f} row {y}")

    def test_baseline_is_two_rows_and_joins_follow_the_form(self):
        for ch in "سش":
            for f in "NMFI":
                g = FB.glyph16(ch, f)
                self.assertEqual(g[10], g[11])
                self.assertEqual(g[10][0] == "#", f in "NM")
                self.assertEqual(g[10][7] == "#", f in "MF")

    def test_final_and_isolated_seen_close_into_a_bowl_below_the_baseline(self):
        for f in "FI":
            g = FB.glyph16("س", f)
            self.assertIn("#", g[12] + g[13])
            self.assertEqual(g[14].count("#") >= 5, True)

    def test_sheen_keeps_its_three_dots_above_the_teeth(self):
        for f in "NMFI":
            g = FB.glyph16("ش", f)
            self.assertEqual(dot_marks(g), 3)
            top_ink = [y for y in range(16) if "#" in g[y]]
            self.assertLess(min(top_ink), 6)                    # the dots sit above the teeth (which start at row 7)


class TestIntegration(unittest.TestCase):
    def test_menu_build_uses_the_new_art(self):
        key = ("ب", "N")
        rows = M.big_rows(key)
        self.assertEqual(rows, FB.glyph16(*key))
        self.assertEqual(len(rows), 16)

    def test_big_pixels4_accepts_16_rows_and_keeps_old_8_row_behaviour(self):
        g16 = FB.glyph16("ل", "M")
        px = M.big_pixels4(g16)
        self.assertEqual((len(px), len(px[0])), (16, 8))
        for y in range(16):
            self.assertEqual([x for x in range(8) if px[y][x] == M.INK], [x for x in range(8) if g16[y][x] == "#"])
        art = F.glyph_pixels("ل", "M")
        self.assertEqual(M.big_pixels4(art), M.big_pixels4([art[y // 2] for y in range(16)]))

    def test_small_font_is_untouched_by_the_big_font_work(self):
        self.assertEqual(F.glyph_pixels("ب", "M")[4], "########")
        self.assertEqual(len(F.glyph_pixels("ب", "M")), 8)


if __name__ == "__main__":
    unittest.main()
