import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from smar import arabic as AR  # noqa: E402
from smar import font_ar as F  # noqa: E402

TABLE = F.tile_table()


def forms(text):
    return [u[1] for u in AR.shape(text) if u[0] == "R"]


class TestShaping(unittest.TestCase):
    def test_isolated_single_letter(self):
        self.assertEqual(forms("ب"), [("ب", "I")])

    def test_dual_joining_word(self):
        # بيت: beh initial, yeh medial, teh final
        self.assertEqual(forms("بيت"), [("ب", "N"), ("ي", "M"), ("ت", "F")])

    def test_right_joining_letters_break_the_chain(self):
        # دار: dal isolated(first), alef final?? dal does not join forward -> alef isolated; reh final? alef doesn't join forward
        self.assertEqual(forms("دار"), [("د", "I"), ("ا", "I"), ("ر", "I")])
        # كتاب: kaf N, teh M, alef F, beh I
        self.assertEqual(forms("كتاب"), [("ك", "N"), ("ت", "M"), ("ا", "F"), ("ب", "I")])

    def test_final_of_right_only_after_dual(self):
        self.assertEqual(forms("بر"), [("ب", "N"), ("ر", "F")])

    def test_space_breaks_joining(self):
        self.assertEqual(forms("ب ب"), [("ب", "I"), ("ب", "I")])

    def test_lam_alef_ligature(self):
        self.assertEqual(forms("لا"), [("ﻻ", "I")])
        self.assertEqual(forms("بلا"), [("ب", "N"), ("ﻻ", "F")])
        # lam + hamza-alef is NOT ligated in this font
        self.assertEqual(forms("لأ"), [("ل", "N"), ("أ", "F")])

    def test_diacritics_and_tatweel_ignored(self):
        self.assertEqual(forms("بَيْت"), forms("بيت"))
        self.assertEqual(forms("بـيـت"), forms("بيت"))

    def test_unsupported_character_raises(self):
        with self.assertRaises(AR.ArabicError):
            AR.shape("بب٣")          # Arabic-Indic digit is not in the font
        with self.assertRaises(AR.ArabicError):
            AR.shape("بé")


class TestVisualOrder(unittest.TestCase):
    def test_rtl_reversal(self):
        t = AR.to_tiles("بيت", TABLE)
        # visual LTR: final form on the LEFT, initial on the RIGHT
        self.assertEqual(t, [TABLE[("ت", "F")], TABLE[("ي", "M")], TABLE[("ب", "N")]])

    def test_words_swap_sides(self):
        # logical: [beh N][alef F] space [teh N][alef F]  ->  visual LTR is the exact reverse
        t = AR.to_tiles("با تا", TABLE)
        self.assertEqual(t, [TABLE[("ا", "F")], TABLE[("ت", "N")], AR.SPACE_TILE,
                             TABLE[("ا", "F")], TABLE[("ب", "N")]])

    def test_latin_run_stays_ltr_inside_arabic(self):
        t = AR.to_tiles("اب X-RAY", TABLE)
        latin = [AR.LATIN["X"], AR.PUNCT["-"], AR.LATIN["R"], AR.LATIN["A"], AR.LATIN["Y"]]
        self.assertEqual(t[:5], latin)                 # Latin run is last logically -> leftmost visually, order kept
        self.assertEqual(t[5], AR.SPACE_TILE)

    def test_trailing_period_goes_left(self):
        t = AR.to_tiles("با.", TABLE)
        self.assertEqual(t[0], AR.PUNCT["."])


class TestFont(unittest.TestCase):
    def test_tile_ids_in_upper_half_and_unique(self):
        ids = list(TABLE.values())
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(0x100 <= i < 0x200 for i in ids))

    def test_every_glyph_is_8x8_ink_or_background(self):
        for ch, f in F.all_glyph_keys():
            rows = F.glyph_pixels(ch, f)
            self.assertEqual(len(rows), 8)
            for r in rows:
                self.assertEqual(len(r), 8)
                self.assertTrue(set(r) <= {"#", "."})

    def test_encode_decode_roundtrip(self):
        for ch, f in F.all_glyph_keys():
            rows = F.glyph_pixels(ch, f)
            self.assertEqual(F.decode_tile(F.encode_tile(rows)), rows)

    def test_encoding_uses_only_index_1_and_3(self):
        data, _ = F.build_font_bytes()
        for t in range(len(TABLE)):
            tile = data[t * 16:(t + 1) * 16]
            for y in range(8):
                for x in range(8):
                    v = ((tile[2 * y] >> (7 - x)) & 1) | (((tile[2 * y + 1] >> (7 - x)) & 1) << 1)
                    self.assertIn(v, (F.INK, F.BG))     # never 0 (transparent) or 2

    def test_injected_tiles_are_the_art_with_a_thickened_baseline(self):
        data, table = F.build_font_bytes()
        for (ch, f), tid in table.items():
            tile = data[(tid - F.FIRST_TILE) * 16:(tid - F.FIRST_TILE + 1) * 16]
            self.assertEqual(F.decode_tile(tile), F.thicken_baseline(F.glyph_pixels(ch, f)))

    def test_thickening_only_adds_ink_directly_below_the_baseline(self):
        for ch, f in F.all_glyph_keys():
            art = F.glyph_pixels(ch, f)
            thick = F.thicken_baseline(art)
            for y in range(8):
                for x in range(8):
                    if thick[y][x] != art[y][x]:
                        self.assertEqual((y, art[4][x], art[6][x]), (5, "#", "."), f"{ch} {f} ({x},{y})")

    def test_thickening_keeps_teeth_holes_and_dot_gaps_open(self):
        thick = F.thicken_baseline(F.glyph_pixels("س", "M"))
        for y in (2, 3):
            self.assertEqual([x for x in range(8) if thick[y][x] == "#"], [1, 3, 5])     # three separate teeth
        thick = F.thicken_baseline(F.glyph_pixels("ص", "N"))
        self.assertEqual((thick[3][4], thick[3][5]), (".", "."))                         # hole of the loop
        thick = F.thicken_baseline(F.glyph_pixels("ب", "I"))
        self.assertNotIn("#", thick[6])                                                  # gap above the lower dot
        self.assertIn("#", thick[7])

    def test_unused_tiles_stay_zero(self):
        data, table = F.build_font_bytes()
        used = {tid - F.FIRST_TILE for tid in table.values()}
        for t in range(256):
            if t not in used:
                self.assertEqual(data[t * 16:(t + 1) * 16], bytes(16))

    def test_joining_strokes_touch_the_cell_edges(self):
        # a form that joins the next (left) letter must touch x=0 on the baseline row; one that joins the
        # previous (right) letter must touch x=7. Otherwise words would show gaps between letters.
        for ch, f in F.all_glyph_keys():
            rows = F.glyph_pixels(ch, f)
            if ch == "ﻻ":
                continue
            if f in "NM":
                self.assertEqual(rows[4][0], "#", f"{ch} {f} does not reach the left edge")
            if f in "MF":
                self.assertEqual(rows[4][7], "#", f"{ch} {f} does not reach the right edge")
            if f in "IF" and ch in F.RIGHT_ONLY | F.NON_JOINING and f == "I":
                self.assertNotEqual(rows[4][7], "#")


if __name__ == "__main__":
    unittest.main()
