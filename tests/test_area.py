import json
import os
import struct
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from smar import area_ar as AR  # noqa: E402
from smar.rom import Rom, RomError, diff_ranges, pc  # noqa: E402

from rompath import ROM as ROM_PATH  # noqa: E402
with open(os.path.join(ROOT, "data", "translations_ar.json"), encoding="utf-8") as f:
    SPEC = json.load(f)["_areas"]


class TestRender(unittest.TestCase):
    def test_all_names_fit_the_tile_pool(self):
        need = sum(len(AR.render(SPEC[k], k)) for k in AR.ENGLISH)
        self.assertLessEqual(need, len(AR.POOL))

    def test_pool_tiles_are_distinct_and_one_byte_ids(self):
        self.assertEqual(len(set(AR.POOL)), len(AR.POOL))
        self.assertTrue(all(0 <= t < 0x100 for t in AR.POOL))


@unittest.skipUnless(os.path.exists(ROM_PATH), "original ROM not available")
class TestBuild(unittest.TestCase):
    def test_original_names_are_found_in_order(self):
        self.assertEqual([t for _, _, t in AR.spans(Rom.load(ROM_PATH))], AR.ENGLISH)

    def test_only_the_table_and_the_pool_tiles_change_and_names_stay_in_their_span(self):
        orig, rom = Rom.load(ROM_PATH), Rom.load(ROM_PATH)
        before = AR.spans(orig)
        info = AR.build(rom, SPEC)
        allowed = AR.changed_regions(info)
        for s, e in diff_ranges(bytes(orig.data), bytes(rom.data)):
            self.assertTrue(any(a <= s and e <= b for a, b in allowed), f"unexpected change {s:#x}-{e:#x}")
        words = [struct.unpack_from("<H", rom.data, pc(AR.BANK, a))[0] for a in range(AR.TABLE, AR.TABLE_END, 2)]
        for a, b, _ in before:
            inside = [w >> 8 for w in words[a:b + 1] if (w >> 8) != 1]
            self.assertTrue(inside and all(t in info["tiles"] for t in inside))
        self.assertEqual(len(words), (AR.TABLE_END - AR.TABLE) // 2)

    def test_changed_table_is_not_longer_than_before(self):
        rom = Rom.load(ROM_PATH)
        AR.build(rom, SPEC)
        self.assertEqual(rom.read(pc(AR.BANK, AR.TABLE_END), 8), Rom.load(ROM_PATH).read(pc(AR.BANK, AR.TABLE_END), 8))

    def test_wrong_table_is_refused(self):
        rom = Rom.load(ROM_PATH)
        rom.write(pc(AR.BANK, AR.TABLE + 2), b"\x28\x31")
        with self.assertRaises(RomError):
            AR.build(rom, SPEC)

    def test_a_name_too_long_for_the_pool_is_refused(self):
        rom = Rom.load(ROM_PATH)
        with self.assertRaises(RomError):
            AR.build(rom, dict(SPEC, COLONY="المستعمرة الكبيرة جدا جدا جدا"))


if __name__ == "__main__":
    unittest.main()
