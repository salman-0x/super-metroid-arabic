import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from smar import credit_ar as C  # noqa: E402
from smar.rom import Rom, RomError, pc  # noqa: E402
from rompath import ROM as ROM_PATH  # noqa: E402


@unittest.skipUnless(os.path.exists(ROM_PATH), "original ROM not available")
class TestCredit(unittest.TestCase):
    def test_the_mark_is_written_in_free_space_and_nothing_else_changes(self):
        orig, rom = Rom.load(ROM_PATH), Rom.load(ROM_PATH)
        info = C.build(rom)
        self.assertEqual(rom.read(pc(*C.AT), len(C.TEXT)), C.TEXT)
        self.assertIn(b"Mr S", C.TEXT)
        start = pc(*C.AT)
        for i, (a, b) in enumerate(zip(orig.data, rom.data)):
            if a != b:
                self.assertTrue(start <= i < start + info["length"])

    def test_occupied_space_is_refused(self):
        rom = Rom.load(ROM_PATH)
        rom.write(pc(*C.AT), b"\x00")
        with self.assertRaises(RomError):
            C.build(rom)


if __name__ == "__main__":
    unittest.main()
