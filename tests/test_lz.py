import os
import random
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from smar import sm_lz as LZ  # noqa: E402
from smar.rom import Rom, pc  # noqa: E402

from rompath import ROM as BASE  # noqa: E402


class TestCommands(unittest.TestCase):
    """Hand-assembled streams, one per command, checked against the documented behaviour."""

    def test_direct_copy(self):
        self.assertEqual(LZ.decompress(bytes([0x02, 1, 2, 3, 0xFF]), 0)[0], bytes([1, 2, 3]))

    def test_byte_fill(self):
        self.assertEqual(LZ.decompress(bytes([0x24, 0xAA, 0xFF]), 0)[0], bytes([0xAA] * 5))

    def test_word_fill(self):
        self.assertEqual(LZ.decompress(bytes([0x45, 0x12, 0x34, 0xFF]), 0)[0], bytes([0x12, 0x34] * 3))

    def test_incrementing_fill(self):
        self.assertEqual(LZ.decompress(bytes([0x63, 0x10, 0xFF]), 0)[0], bytes([0x10, 0x11, 0x12, 0x13]))

    def test_absolute_copy_and_inverted_copy(self):
        # direct [1,2,3,4]; cmd4 len2 from output[1] -> 2,3 ; cmd5 len2 from output[0], XOR FF -> FE,FD
        s = bytes([0x03, 1, 2, 3, 4,
                   (4 << 5) | 1, 0x01, 0x00,
                   (5 << 5) | 1, 0x00, 0x00,
                   0xFF])
        self.assertEqual(LZ.decompress(s, 0)[0], bytes([1, 2, 3, 4, 2, 3, 0xFE, 0xFD]))

    def test_relative_copy_and_inverted_copy(self):
        # direct [1,2,3,4]; cmd6 len2 offset3 -> out[len-3:] = 2,3 ; then cmd7 (needs the extended header:
        # 0xE0|(7<<2), length byte) len2 offset4 -> src = 6-4 = 2 -> 3,4 inverted = FC,FB
        s = bytes([0x03, 1, 2, 3, 4,
                   (6 << 5) | 1, 0x03,
                   0xE0 | (7 << 2), 0x01, 0x04,
                   0xFF])
        self.assertEqual(LZ.decompress(s, 0)[0], bytes([1, 2, 3, 4, 2, 3, 0xFC, 0xFB]))

    def test_extended_length(self):
        # extended header: cmd 1 (byte fill), length 300
        ln = 299
        s = bytes([0xE0 | (1 << 2) | (ln >> 8), ln & 0xFF, 0x55, 0xFF])
        self.assertEqual(LZ.decompress(s, 0)[0], bytes([0x55] * 300))

    def test_stops_after_terminator_and_reports_end(self):
        s = bytes([0x00, 9, 0xFF, 0xDE, 0xAD])
        out, end = LZ.decompress(s, 0)
        self.assertEqual((out, end), (bytes([9]), 3))

    def test_truncated_stream_raises(self):
        with self.assertRaises(Exception):
            LZ.decompress(bytes([0x05, 1, 2]), 0)


class TestRoundTrip(unittest.TestCase):
    def test_random_and_structured_data(self):
        rnd = random.Random(1234)
        samples = [b"", b"\x00", bytes(2000), bytes(range(256)) * 9, b"AB" * 700, b"\xFF" * 3000]
        for n in (1, 2, 31, 32, 33, 1023, 1024, 1025, 4096):
            samples.append(bytes(rnd.randrange(256) for _ in range(n)))
        mixed = bytearray()
        for _ in range(60):
            mixed += bytes([rnd.randrange(256)]) * rnd.randrange(1, 70)
            mixed += bytes(rnd.randrange(256) for _ in range(rnd.randrange(1, 40)))
        samples.append(bytes(mixed))
        for s in samples:
            packed = LZ.compress(s)
            self.assertEqual(packed[-1], 0xFF)
            out, end = LZ.decompress(packed, 0)
            self.assertEqual(out, s)
            self.assertEqual(end, len(packed))

    def test_real_game_graphics_roundtrip(self):
        """Every blob the game itself decompresses: decode with our decoder, re-compress, decode again -> identical."""
        rom = Rom.load(BASE)
        d = rom.data
        pat = bytes([0x22, 0xFF, 0xB0, 0x80])
        i, checked = d.find(pat), 0
        seen = set()
        while i != -1:
            w = d[i - 10:i]
            if w[0] == 0xA9 and w[1] == 0 and w[3] == 0x85 and w[4] == 0x48 and w[5] == 0xA9 and w[8] == 0x85 and w[9] == 0x47:
                key = (w[2], w[6] | (w[7] << 8))
                if key not in seen:
                    seen.add(key)
                    raw, end = LZ.decompress(d, pc(*key))
                    self.assertGreater(len(raw), 0)
                    self.assertEqual(LZ.decompress(LZ.compress(raw), 0)[0], raw, f"round trip failed for ${key[0]:02X}:{key[1]:04X}")
                    checked += 1
            i = d.find(pat, i + 1)
        self.assertGreaterEqual(checked, 40)

    def test_real_blob_sizes_are_whole_tile_sets(self):
        rom = Rom.load(BASE)
        raw, _ = LZ.decompress(rom.data, pc(0xB9, 0x8000))
        self.assertEqual(len(raw), 12288)
        raw, _ = LZ.decompress(rom.data, pc(0x94, 0xE000))
        self.assertEqual(len(raw), 16384)


if __name__ == "__main__":
    unittest.main()
