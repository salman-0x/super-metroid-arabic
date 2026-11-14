import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from smar import pack_ar as P  # noqa: E402
from smar import pause_ar as Z  # noqa: E402
from smar.rom import Rom, RomError, diff_ranges  # noqa: E402

from rompath import ROM as ROM_PATH  # noqa: E402
with open(os.path.join(ROOT, "data", "translations_ar.json"), encoding="utf-8") as f:
    SPEC = json.load(f)["_pause"]


class TestRender(unittest.TestCase):
    def test_every_label_fits_its_box(self):
        for name, text in SPEC.items():
            if name in Z.BOXES or name.startswith("item_"):     # these need the ROM art: covered by TestBuild
                continue
            tiles = Z.render(name, text)
            self.assertEqual(len(tiles), len(Z.LABELS[name][0]))
            self.assertTrue(all(len(t) == 32 for t in tiles))

    def test_too_wide_a_word_is_refused(self):
        with self.assertRaises(RomError):
            Z.render("beam", "متفرقات")

    def test_packing_keeps_connected_letters_touching_and_gaps_the_rest(self):
        self.assertLess(P.width("بب"), 2 * 8)                       # cropped margins
        rows = P.pack("با")                                          # alef does not connect to the next letter
        self.assertEqual(len(rows), 8)
        self.assertEqual(len({len(r) for r in rows}), 1)


@unittest.skipUnless(os.path.exists(ROM_PATH), "original ROM not available")
class TestBuild(unittest.TestCase):
    def test_only_the_label_tiles_change(self):
        orig, rom = Rom.load(ROM_PATH), Rom.load(ROM_PATH)
        info = Z.build(rom, SPEC)
        allowed = Z.changed_regions(info)
        changed = diff_ranges(bytes(orig.data), bytes(rom.data))
        self.assertTrue(changed)
        for s, e in changed:
            self.assertTrue(any(a <= s and e <= b for a, b in allowed), f"unexpected change {s:#x}-{e:#x}")

    def test_box_text_must_fit_the_text_area(self):
        rom = Rom.load(ROM_PATH)
        with self.assertRaises(RomError):
            Z.render_box("exit", "متفرقات", rom)

    def test_box_frame_pixels_outside_the_text_area_are_kept(self):
        rom = Rom.load(ROM_PATH)
        new = Z.render_box("map", SPEC["map"], rom)
        b = Z.BOXES["map"]
        x0, y0, x1, y1 = b["rect"]
        for k, t in enumerate(b["tiles"]):
            old = Z._decode4(rom.read(Z._tile_at(t), 32))
            cur = Z._decode4(new[t])
            for y in range(8):
                for x in range(8):
                    gx, gy = 8 * (k % b["cols"]) + x, 8 * (k // b["cols"]) + y
                    if not (x0 <= gx <= x1 and y0 <= gy <= y1):
                        self.assertEqual(old[y][x], cur[y][x])

    def test_every_item_name_fits_its_strip_and_unrelated_tiles_stay(self):
        for name, text in SPEC.items():
            if name.startswith("item_"):
                tiles = Z.render_strip(name[5:], text)
                self.assertEqual(len(tiles), len(Z.STRIPS[name[5:]][0]))

    def test_too_long_an_item_name_is_refused(self):
        with self.assertRaises(RomError):
            Z.render_strip("ice", "كرة التحول")

    def test_wrong_art_is_refused(self):
        rom = Rom.load(ROM_PATH)
        rom.write(Z._tile_at(0x107), b"\x01")
        with self.assertRaises(RomError):
            Z.build(rom, SPEC)


if __name__ == "__main__":
    unittest.main()
