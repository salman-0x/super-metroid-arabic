import os
import random
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from smar import bps  # noqa: E402


def sample():
    rnd = random.Random(7)
    src = bytes(rnd.randrange(256) for _ in range(6000))
    tgt = bytearray(src)
    tgt[100:140] = b"NEW DATA " * 4 + b"x"                     # changed bytes
    tgt[3000:3000] = src[500:700]                              # a block moved/copied from elsewhere in the source
    del tgt[5200:5300]
    tgt += bytes(rnd.randrange(256) for _ in range(50))
    return src, bytes(tgt)


class TestBps(unittest.TestCase):
    def test_roundtrip(self):
        src, tgt = sample()
        self.assertEqual(bps.apply(src, bps.make(src, tgt)), tgt)

    def test_a_copied_block_is_referenced_not_embedded(self):
        src, tgt = sample()
        self.assertLess(len(bps.make(src, tgt)), 400)             # the 200-byte copy and the unchanged bytes cost almost nothing

    def test_wrong_source_and_damage_are_refused(self):
        src, tgt = sample()
        patch = bps.make(src, tgt)
        with self.assertRaises(ValueError):
            bps.apply(src[:-1] + b"\x00", patch)
        bad = bytearray(patch)
        bad[20] ^= 0xFF
        with self.assertRaises(ValueError):
            bps.apply(src, bytes(bad))

    def test_standalone_applier_matches_the_library(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import apply_patch
        src, tgt = sample()
        self.assertEqual(apply_patch.apply_bps(src, bps.make(src, tgt)), tgt)


if __name__ == "__main__":
    unittest.main()
