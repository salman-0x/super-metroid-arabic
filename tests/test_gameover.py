import json
import os
import struct
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from smar import arabic as A  # noqa: E402
from smar import gameover_ar as G  # noqa: E402
from smar import translate as T  # noqa: E402
from smar.rom import Rom, RomError, diff_ranges, pc  # noqa: E402

from rompath import ROM as ROM_PATH  # noqa: E402
with open(os.path.join(ROOT, "data", "translations_ar.json"), encoding="utf-8") as f:
    TR = json.load(f)
SPEC = TR["_menus"]["game_over"]


def fake_tables():
    small = {k: 0x2B0 + i for i, k in enumerate(sorted(G.small_keys(SPEC)))}
    base = 0x2B0 + len(small)
    big = {k: (base + 2 * i, base + 2 * i + 1) for i, k in enumerate(sorted(G.big_keys(SPEC)))}
    return small, big


class TestCompose(unittest.TestCase):
    def test_every_string_fits_the_screen(self):
        small, big = fake_tables()
        for name in G.ENTRIES:
            words, width = G.compose(name, SPEC, small, big)
            col = G.column(name, width)
            self.assertTrue(0 <= col and col + width - 1 <= G.RIGHT_LIMIT, name)
            self.assertEqual(words[-1], 0xFFFF)

    def test_two_row_strings_have_equal_rows(self):
        small, big = fake_tables()
        for name in ("title", "yes", "no"):
            words, width = G.compose(name, SPEC, small, big)
            cut = words.index(0xFFFE)
            self.assertEqual(cut, len(words) - 2 - cut)
            self.assertEqual(cut, width)

    def test_yes_no_keep_the_original_column_next_to_the_cursor(self):
        small, big = fake_tables()
        for name in ("yes", "no"):
            _, width = G.compose(name, SPEC, small, big)
            self.assertEqual(G.column(name, width), (G.ENTRIES[name][3] % 0x40) // 2)

    def test_brackets_are_mirrored_for_right_to_left_text(self):
        small, big = fake_tables()
        words, _ = G.compose("yes", SPEC, small, big)
        bottom = words[words.index(0xFFFE) + 1:-1]
        # logical "(" comes first = rightmost: it must be drawn with the ")" tile, and the leftmost with the "(" tile
        self.assertEqual(bottom[-1], A.MENU.punct[")"])
        self.assertEqual(bottom[bottom.index(A.MENU.punct["("])], A.MENU.punct["("])

    def test_too_wide_is_rejected(self):
        with self.assertRaises(RomError):
            G.column("title", 40)

    def test_original_words_table_matches_the_documented_layout(self):
        for name, (_, _, addr, x, kind, hexwords) in G.ENTRIES.items():
            words = [int(w, 16) for w in hexwords.split()]
            if kind != "small":
                cut = words.index(0xFFFE)
                self.assertEqual(cut, len(words) - 1 - cut, name)


@unittest.skipUnless(os.path.exists(ROM_PATH), "original ROM not available")
class TestBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orig = Rom.load(ROM_PATH)
        cls.rom = Rom.load(ROM_PATH)
        with open(os.path.join(ROOT, "data", "messages.json"), encoding="utf-8") as f:
            doc = json.load(f)
        cls.res = T.build_arabic(cls.rom, doc, TR)
        cls.info = cls.res["menus"]["game_over"]

    def test_five_operand_pairs_point_at_the_new_strings(self):
        for name, (ldy, ldx, addr, x, kind, _) in G.ENTRIES.items():
            ptr, new_x, width = self.info["placed"][name]
            self.assertEqual(self.rom.read(pc(G.BANK, ldy), 1), b"\xA0")
            self.assertEqual(self.rom.read(pc(G.BANK, ldy + 1), 2), struct.pack("<H", ptr))
            self.assertEqual(self.rom.read(pc(G.BANK, ldx), 1), b"\xA2")
            self.assertEqual(self.rom.read(pc(G.BANK, ldx + 1), 2), struct.pack("<H", new_x))
            self.assertEqual(new_x // 0x40, x // 0x40, "the string moved to another tile row")

    def test_new_strings_are_terminated_and_use_only_known_tiles(self):
        limit = 0x2B0 + self.res["menus"]["tiles"]
        for name in G.ENTRIES:
            ptr = self.info["placed"][name][0]
            words = G._read_words(self.rom, ptr)
            for w in words:
                if w != 0xFFFE:
                    self.assertTrue((w & 0x3FF) < limit, f"{name}: tile {w & 0x3FF:#x} is beyond the loaded tile set")

    def test_original_strings_are_left_where_they_were(self):
        for name, (_, _, addr, _, _, hexwords) in G.ENTRIES.items():
            self.assertEqual(G._read_words(self.rom, addr), [int(w, 16) for w in hexwords.split()])

    def test_changes_stay_inside_the_free_run_and_operands(self):
        allowed = G.changed_regions(self.info)
        self.assertLessEqual(self.info["bytes"], G.FREE_LEN)
        outside = []
        for s, e in diff_ranges(bytes(self.orig.data), bytes(self.rom.data)):
            if pc(0x81, 0x9200) <= s < pc(0x81, 0x9240) or pc(0x81, G.FREE_AT) <= s < pc(0x81, G.FREE_AT + G.FREE_LEN):
                if not any(a <= s and e <= b for a, b in allowed):
                    outside.append((s, e))
        self.assertEqual(outside, [])

    def test_wrong_rom_is_refused(self):
        bad = Rom.load(ROM_PATH)
        bad.write(pc(G.BANK, 0x9304), b"\x00\x00")
        small, big = fake_tables()
        with self.assertRaises(RomError):
            G.build(bad, SPEC, small, big)


if __name__ == "__main__":
    unittest.main()
