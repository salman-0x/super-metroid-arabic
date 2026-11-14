import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from smar import hud_ar as H  # noqa: E402
from smar.rom import Rom, RomError, diff_ranges  # noqa: E402

from rompath import ROM as ROM_PATH  # noqa: E402
with open(os.path.join(ROOT, "data", "translations_ar.json"), encoding="utf-8") as f:
    SPEC = json.load(f)["_hud"]


@unittest.skipUnless(os.path.exists(ROM_PATH), "original ROM not available")
class TestHud(unittest.TestCase):
    def test_labels_fit_and_only_their_tiles_change(self):
        orig, rom = Rom.load(ROM_PATH), Rom.load(ROM_PATH)
        info = H.build(rom, SPEC)
        allowed = H.changed_regions(info)
        changed = diff_ranges(bytes(orig.data), bytes(rom.data))
        self.assertTrue(changed)
        for s, e in changed:
            self.assertTrue(any(a <= s and e <= b for a, b in allowed), f"unexpected change {s:#x}-{e:#x}")

    def test_row_zero_and_row_seven_keep_the_background(self):
        rom = Rom.load(ROM_PATH)
        for name, text in SPEC.items():
            b = H.LABELS[name]
            for data in H.render(name, text, rom):
                rows = [(data[2 * y], data[2 * y + 1]) for y in range(8)]
                px = lambda r, x: ((rows[r][0] >> (7 - x)) & 1) | (((rows[r][1] >> (7 - x)) & 1) << 1)   # noqa: E731
                self.assertTrue(all(px(0, x) == b["bg"] and px(7, x) == b["last_row"] for x in range(8)))

    def test_too_wide_is_refused(self):
        with self.assertRaises(RomError):
            H.render("auto", "كرة التحول", Rom.load(ROM_PATH))

    def test_original_art_is_required(self):
        rom = Rom.load(ROM_PATH)
        rom.write(H._tile_at(0x0B), b"\x00")
        with self.assertRaises(RomError):
            H.build(rom, SPEC)


if __name__ == "__main__":
    unittest.main()
