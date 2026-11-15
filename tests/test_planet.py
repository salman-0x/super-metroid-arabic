import json
import os
import struct
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from smar import planet_ar as P  # noqa: E402
from smar.rom import Rom, RomError, pc, diff_ranges  # noqa: E402

from rompath import ROM as ROM_PATH  # noqa: E402
with open(os.path.join(ROOT, "data", "translations_ar.json"), encoding="utf-8") as f:
    TITLE = json.load(f)["_planet"]["title"]


class TestLayout(unittest.TestCase):
    def test_title_is_centred_and_in_visual_order(self):
        units = P.layout(TITLE)
        self.assertEqual(len(units), len(TITLE))
        self.assertIsNone(units[len(TITLE.split(" ")[1])])            # the space sits between the two words
        self.assertEqual(units[-1][0], "ك")                             # logical first letter is drawn rightmost

    def test_entries_stay_inside_the_original_footprint(self):
        units = P.layout(TITLE)
        tiles = {k: (P.SLOTS[2 * i], P.SLOTS[2 * i + 1]) for i, k in enumerate(sorted({u for u in units if u}, key=str))}
        ents = P.entries(units, tiles)
        self.assertEqual(len(ents), 2 * sum(1 for u in units if u))
        self.assertLessEqual(len(ents), P.MAP_ENTRIES)
        for e in ents:
            x = e[0] - (256 if e[1] else 0)
            self.assertTrue(-48 <= x <= 40, x)                          # the English title spans -48..+48
            self.assertEqual(e[4], P.ATTR)

    def test_glyph_tiles_have_ink_and_shadow(self):
        top, bottom = P.glyph_tiles("ب", "I")
        vals = set()
        for half in (top, bottom):
            for y in range(8):
                for x in range(8):
                    v = sum(((half[(p // 2) * 16 + 2 * y + (p & 1)] >> (7 - x)) & 1) << p for p in range(4))
                    vals.add(v)
        self.assertEqual(vals, {0, P.INK, P.SHADOW})


@unittest.skipUnless(os.path.exists(ROM_PATH), "original ROM not available")
class TestBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orig = Rom.load(ROM_PATH)
        cls.rom = Rom.load(ROM_PATH)
        cls.info = P.build(cls.rom, {"title": TITLE})

    def test_spritemap_points_at_the_new_tiles(self):
        at = pc(*P.MAP_AT)
        n = struct.unpack_from("<H", self.rom.data, at)[0]
        self.assertEqual(n, self.info["sprites"])
        for k in range(n):
            e = self.rom.read(at + 2 + 5 * k, 5)
            self.assertIn(e[3], self.info["tiles"])
            self.assertEqual(e[4], P.ATTR)

    def test_only_the_title_tiles_change_in_the_set(self):
        base = pc(*P.TILES_AT)
        for t in self.info["tiles"]:
            self.assertIn(t, P.SLOTS)
            self.assertTrue(any(self.rom.read(base + 32 * t, 32)))
        for t in range(512):
            if t not in self.info["tiles"]:
                self.assertEqual(self.rom.read(base + 32 * t, 32), self.orig.read(base + 32 * t, 32), t)

    def test_nothing_changes_outside_the_expected_places(self):
        allowed = P.changed_regions(self.info)
        for s, e in diff_ranges(bytes(self.orig.data), bytes(self.rom.data)):
            self.assertTrue(any(a <= s and e <= b for a, b in allowed), f"unexpected change {s:#x}-{e:#x}")

    def test_too_long_a_title_is_rejected(self):
        with self.assertRaises(RomError):
            P.build(Rom.load(ROM_PATH), {"title": "كوكب " * 6})

    def test_changed_letter_art_is_refused(self):
        bad = Rom.load(ROM_PATH)
        bad.write(pc(*P.TILES_AT) + 32 * P.SLOTS[0], b"")
        with self.assertRaises(RomError):
            P.build(bad, {"title": TITLE})

    def test_wrong_rom_is_refused(self):
        bad = Rom.load(ROM_PATH)
        bad.write(pc(*P.MAP_AT) + 2, b"\x01")
        with self.assertRaises(RomError):
            P.build(bad, {"title": TITLE})


if __name__ == "__main__":
    unittest.main()
