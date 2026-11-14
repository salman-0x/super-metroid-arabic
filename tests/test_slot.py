import json
import os
import struct
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from smar import arabic as A  # noqa: E402
from smar import slot_ar as S  # noqa: E402
from smar import translate as T  # noqa: E402
from smar.rom import Rom, RomError, diff_ranges, pc  # noqa: E402

from rompath import ROM as ROM_PATH  # noqa: E402
with open(os.path.join(ROOT, "data", "translations_ar.json"), encoding="utf-8") as f:
    TR = json.load(f)
SPEC = TR["_menus"]["slot_dialogs"]


def fake_table():
    return {k: 0x2B0 + i for i, k in enumerate(sorted(S.small_keys(SPEC)))}


class TestCompose(unittest.TestCase):
    def test_one_placeholder_per_file_letter_site(self):
        table = fake_table()
        for name, (_, _, _, _, _, sites) in S.ENTRIES.items():
            words, start, holes = S.compose(name, SPEC[name], table)
            self.assertEqual(len(holes), len(sites), name)
            self.assertEqual(words[-1], 0xFFFF)
            for c in holes:
                self.assertGreaterEqual(c, start)
                self.assertLess(c - start, len(words) - 1)
                self.assertEqual(words[c - start], S.ATTR | S.SPACE, "the placeholder cell must be blank")

    def test_strings_cover_at_least_the_original_cells(self):
        table = fake_table()
        for name, (_, _, _, x, hexwords, _) in S.ENTRIES.items():
            words, start, _ = S.compose(name, SPEC[name], table)
            orig_col, orig_n = (x % 0x40) // 2, len(hexwords.split())
            self.assertLessEqual(start, orig_col)
            self.assertGreaterEqual(start + len(words) - 1, orig_col + orig_n)

    def test_no_placeholder_tile_reaches_the_output(self):
        table = fake_table()
        for name in S.ENTRIES:
            words, _, _ = S.compose(name, SPEC[name], table)
            self.assertTrue(all((w & 0x3FF) != S.PLACEHOLDER for w in words[:-1]))

    def test_holes_are_in_visual_order_source_first_on_the_right(self):
        words, start, holes = S.compose("copy_both", SPEC["copy_both"], fake_table())
        self.assertEqual(len(holes), 2)
        # right-to-left text: the first "(ساموس #)" (the source file) is the rightmost one
        self.assertGreater(holes[1] - holes[0], 0)
        self.assertEqual(S.ENTRIES["copy_both"][5][0][2], 0x375C)       # first site = source, original cell $375C

    def test_text_without_the_right_number_of_placeholders_is_refused(self):
        class R:                                    # minimal stand-in: build() must refuse before touching anything
            pass
        spec = dict(SPEC, copy_both="نسخ (ساموس #)")
        with self.assertRaises(Exception):
            S.build(Rom.load(ROM_PATH) if os.path.exists(ROM_PATH) else R(), spec, fake_table(), 0x300)


@unittest.skipUnless(os.path.exists(ROM_PATH), "original ROM not available")
class TestBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orig = Rom.load(ROM_PATH)
        cls.rom = Rom.load(ROM_PATH)
        with open(os.path.join(ROOT, "data", "messages.json"), encoding="utf-8") as f:
            doc = json.load(f)
        cls.res = T.build_arabic(cls.rom, doc, TR)
        cls.info = cls.res["menus"]["slot_dialogs"]
        cls.base = cls.info["slot_base"]

    def test_slot_letter_tiles_are_three_consecutive_arabic_letters(self):
        p = self.rom.read(pc(0x81, 0x8DF1), 8)
        blob = self.rom.read(pc(p[5], p[3] | (p[4] << 8)), p[6] | (p[7] << 8))
        for i, rows in enumerate(S.letter_tiles()):
            from smar import menu_ar as M
            self.assertEqual(blob[(self.base + i) * 32:(self.base + i) * 32 + 32], M.glyph_to_tile4(rows))

    def test_code_operands_point_at_the_new_strings_cells_and_letter_base(self):
        for name, (ldy, ldx, addr, x, _, sites) in S.ENTRIES.items():
            placed = self.info["placed"][name]
            self.assertEqual(self.rom.read(pc(0x81, ldy + 1), 2), struct.pack("<H", placed["ptr"]))
            self.assertEqual(self.rom.read(pc(0x81, ldx + 1), 2), struct.pack("<H", placed["x"]))
            self.assertEqual(placed["x"] // 0x40, x // 0x40)
            for (adc, sta, off), hole in zip(sites, placed["holes"]):
                self.assertEqual(self.rom.read(pc(0x81, adc), 3), bytes([0x69]) + struct.pack("<H", S.ATTR | self.base))
                self.assertEqual(self.rom.read(pc(0x81, sta), 4), bytes([0x8F]) + struct.pack("<H", hole) + b"\x7E")

    def test_original_strings_and_the_rest_of_the_code_are_untouched(self):
        allowed = S.changed_regions(self.info)
        for name, (_, _, addr, _, hexwords, _) in S.ENTRIES.items():
            self.assertEqual(S._read_words(self.rom, addr), [int(w, 16) for w in hexwords.split()])
        for s, e in diff_ranges(bytes(self.orig.data), bytes(self.rom.data)):
            if pc(0x81, 0x9700) <= s < pc(0x81, 0x9D00) or pc(0x81, S.FREE_AT) <= s < pc(0x81, S.FREE_AT + S.FREE_LEN):
                if not any(a <= s and e <= b for a, b in allowed):
                    # not ours: it must be one of the other modules' known regions
                    from smar import gameover_ar as G
                    self.assertTrue(any(a <= s and e <= b for a, b in G.changed_regions(self.res["menus"]["game_over"])),
                                    f"unexpected change {s:#x}-{e:#x}")

    def test_wrong_rom_is_refused(self):
        bad = Rom.load(ROM_PATH)
        bad.write(pc(0x81, S.ENTRIES["clear"][5][0][0] + 1), b"\x00\x00")
        with self.assertRaises(RomError):
            S.build(bad, SPEC, fake_table(), 0x300)


if __name__ == "__main__":
    unittest.main()
