import json
import os
import struct
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from smar import intro_ar as I  # noqa: E402
from smar import sm_lz  # noqa: E402
from smar.rom import Rom, RomError, pc, diff_ranges  # noqa: E402

from rompath import ROM as ROM_PATH  # noqa: E402
with open(os.path.join(ROOT, "data", "translations_ar.json"), encoding="utf-8") as f:
    _INTRO = json.load(f)["_intro"]
PAGES, LAST = _INTRO["pages"], _INTRO["last"]


def token_table(pages):
    return {k: I.GLYPH_TOKEN + i for i, k in enumerate(I.used_glyphs(pages))}


class TestLayout(unittest.TestCase):
    def test_every_page_fits_its_record_slots_and_the_column_range(self):
        table = token_table(PAGES)
        for (first, n, _), lines in zip(I.PAGES, PAGES):
            placed = I.layout_page(lines, n, table)
            self.assertEqual(len(placed), n)
            for col, row, _ in placed:
                self.assertTrue(1 <= col <= 30)
                self.assertTrue(I.FIRST_ROW <= row <= 24)

    def test_lines_are_three_tile_rows_apart(self):
        table = token_table([["اب", "اب"]])
        placed = I.layout_page(["اب", "اب"], 4, table)
        self.assertEqual(sorted({p[1] for p in placed}), [I.FIRST_ROW, I.FIRST_ROW + I.ROW_STRIDE])

    def test_text_is_typed_right_to_left_and_lines_are_right_aligned(self):
        table = token_table([["اب"]])
        placed = I.layout_page(["اب"], 4, table)
        self.assertEqual([p[0] for p in placed[:2]], [29, 28])        # first typed character is in column 29
        self.assertEqual(placed[2][:2], (30, I.FIRST_ROW))            # surplus slots: blank cell right of the text area
        self.assertEqual(placed[2][2], I.INTRO.space)

    def test_too_long_or_too_many_is_rejected(self):
        table = token_table([["ا"]])
        with self.assertRaises(RomError):
            I.layout_page(["ا" * 30], 100, table)
        with self.assertRaises(RomError):
            I.layout_page(["ا" * 20, "ا" * 20], 30, table)

    def test_glyph_halves_have_ink_and_an_outline(self):
        top, bottom = I.glyph_halves("ب", "I")
        self.assertEqual((len(top), len(bottom)), (16, 16))
        vals = set()
        for half in (top, bottom):
            for y in range(8):
                for x in range(8):
                    vals.add(((half[2 * y] >> (7 - x)) & 1) | (((half[2 * y + 1] >> (7 - x)) & 1) << 1))
        self.assertEqual(vals, {0, 1, 3})

    def test_glyph_art_matches_the_big_menu_font(self):
        from smar import font_big as FB
        px = I.glyph_pixels16("م", "M")
        art = FB.glyph16("م", "M")
        for y in range(16):
            for x in range(8):
                self.assertEqual(px[y][x] == I.INK, art[y][x] == "#")

    def test_the_translation_fits_the_free_tiles(self):
        halves = set()
        for k in I.used_glyphs(PAGES):
            halves |= {h for h in I.glyph_halves(*k) if h != bytes(16)}
        self.assertLessEqual(len(halves), len(I.NEW_TILE_SLOTS))


@unittest.skipUnless(os.path.exists(ROM_PATH), "original ROM not available")
class TestBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orig = Rom.load(ROM_PATH)
        cls.rom = Rom.load(ROM_PATH)
        cls.info = I.build(cls.rom, PAGES, LAST)

    def test_english_pages_are_recognised_in_the_original(self):
        pages = I.read_pages(self.orig)
        self.assertEqual([len(p) for p in pages], [n for _, n, _ in I.PAGES])

    def test_font_block_is_original_plus_the_arabic_tiles(self):
        data, _ = sm_lz.decompress(bytes(self.rom.data), pc(*I.NEW_FONT_AT), 0x2000)
        orig, _ = sm_lz.decompress(bytes(self.orig.data), pc(*I.FONT_SRC), 0x2000)
        self.assertEqual(len(data), I.FONT_LEN_NEW)
        changed = {t for t in range(0x100) if data[t * 16:t * 16 + 16] != (orig + bytes(0x700))[t * 16:t * 16 + 16]}
        self.assertTrue(changed <= set(I.NEW_TILE_SLOTS) | set(I.LAST_TILE_SLOTS))   # no other tile moved
        self.assertEqual(len(changed & set(I.NEW_TILE_SLOTS)), self.info["tiles"])
        self.assertLessEqual(len(changed & set(I.LAST_TILE_SLOTS)), self.info["last_tiles"])
        for (letter, form), (top, bottom) in self.info["table"].items():
            t, b = I.glyph_halves(letter, form)
            for tid, want in ((top, t), (bottom, b)):
                if want == bytes(16):
                    self.assertEqual(tid, I.BLANK_TILE)
                else:
                    self.assertEqual(data[tid * 16:tid * 16 + 16], want)

    def test_loader_points_at_the_new_block_and_dma_size_grows(self):
        self.assertEqual(self.rom.read(pc(0x8B, I.SRC_BANK_AT), 1), bytes([I.NEW_FONT_AT[0]]))
        self.assertEqual(self.rom.read(pc(0x8B, I.SRC_ADDR_AT), 2), struct.pack("<H", I.NEW_FONT_AT[1]))
        self.assertEqual(self.rom.read(pc(0x8B, I.DMA_SIZE_AT), 2), struct.pack("<H", I.FONT_LEN_NEW))

    def _records(self):
        out = []
        for first, n, _ in I.PAGES:
            recs = []
            for k in range(n):
                b = self.rom.read(pc(0x8C, first + 6 * k), 6)
                recs.append([b[0], b[1], b[2], b[3] | (b[4] << 8), b[5]])
            out.append(recs)
        return out

    def test_every_record_points_at_a_real_glyph_object(self):
        for recs in self._records():
            for rec in recs:
                ptr = rec[3]
                if ptr == I.SPACE_OBJ:
                    continue
                obj = self.rom.read(pc(0x8C, ptr), 6)
                self.assertEqual(obj[:3], bytes([0x4D, 0x88, 0x01]))
                if ptr >= I.OBJ_AT[1]:                              # Arabic: two tiles, both with the intro palette bits
                    obj = self.rom.read(pc(0x8C, ptr), I.OBJ_SIZE)
                    self.assertEqual((obj[3], obj[5], obj[7]), (2, 0x20, 0x20))
                    self.assertIn(obj[4], list(I.NEW_TILE_SLOTS) + [I.BLANK_TILE])
                    self.assertIn(obj[6], list(I.NEW_TILE_SLOTS) + [I.BLANK_TILE])

    def test_record_bytes_other_than_col_row_ptr_are_unchanged(self):
        for first, n, _ in I.PAGES:
            for k in range(n):
                a = pc(0x8C, first + 6 * k)
                o, r = self.orig.read(a, 6), self.rom.read(a, 6)
                self.assertEqual((o[0], o[5]), (r[0], r[5]))

    def test_nothing_changes_outside_the_expected_places(self):
        allowed = I.changed_regions(self.info)
        for s, e in diff_ranges(bytes(self.orig.data), bytes(self.rom.data)):
            self.assertTrue(any(a <= s and e <= b for a, b in allowed), f"unexpected change {s:#x}-{e:#x}")

    def test_first_page_tilemap_is_arabic_and_keeps_everything_else(self):
        import struct as st
        orig_tm, _ = sm_lz.decompress(bytes(self.orig.data), pc(*I.LAST_SRC), 0x1000)
        new_tm, _ = sm_lz.decompress(bytes(self.rom.data), pc(*self.info["last_at"]), 0x1000)
        ow, nw = st.unpack("<1024H", orig_tm), st.unpack("<1024H", new_tm)
        text_rows = {r + d for r in I.LAST_ROWS for d in (0, 1)}
        for r in range(32):
            for c in range(32):
                if r not in text_rows:
                    self.assertEqual(ow[r * 32 + c], nw[r * 32 + c], f"row {r} col {c} changed")
        used = {w & 0x3FF for r in text_rows for w in nw[r * 32:(r + 1) * 32] if (w & 0x3FF) != 0x2F}
        self.assertTrue(used)
        self.assertTrue(all(0x30 <= t < 0x90 or t == 0x26 for t in used), sorted(used))
        for r in text_rows:
            for w in nw[r * 32:(r + 1) * 32]:
                self.assertIn(w >> 8, (0x00, 0x10))                # blank or palette-4 text word
        self.assertEqual(I._sha("\n".join(I._decode_last(list(ow)))), I.LAST_ENGLISH["sha1"])

    def test_first_page_glyph_tiles_are_in_the_font_block(self):
        data, _ = sm_lz.decompress(bytes(self.rom.data), pc(*I.NEW_FONT_AT), 0x2000)
        import struct as st
        new_tm, _ = sm_lz.decompress(bytes(self.rom.data), pc(*self.info["last_at"]), 0x1000)
        nw = st.unpack("<1024H", new_tm)
        from smar import arabic as A
        keys = sorted({k for text in LAST for k in A.glyph_keys(text, I.LASTCS)},
                      key=lambda k: (k[0], A.F.FORMS.index(k[1])))
        halves = {h for k in keys for h in I.glyph_halves(*k) if h != bytes(16)}
        in_block = {data[t * 16:t * 16 + 16] for t in I.LAST_TILE_SLOTS}
        self.assertTrue(halves <= in_block)
        self.assertEqual(self.rom.read(pc(0x8B, I.LAST_ADDR_AT), 2), st.pack("<H", self.info["last_at"][1]))
        self.assertEqual(self.rom.read(pc(0x8B, I.LAST_BANK_AT), 1), bytes([self.info["last_at"][0]]))

    def test_first_page_too_many_lines_or_columns_are_rejected(self):
        with self.assertRaises(RomError):
            I.layout_last(["ا", "ا", "ا", "ا"], {})
        table = {("ا", "I"): I.GLYPH_TOKEN}
        with self.assertRaises(RomError):
            I.layout_last(["ا" * 23], table)

    def test_wrong_rom_is_refused(self):
        bad = Rom.load(ROM_PATH)
        bad.write(pc(0x8B, I.DMA_SIZE_AT), b"\x00\x08")
        with self.assertRaises(RomError):
            I.build(bad, PAGES)


if __name__ == "__main__":
    unittest.main()
