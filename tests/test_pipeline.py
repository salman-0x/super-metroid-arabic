import copy
import os
import struct
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from smar.rom import Rom, RomError, ORIGINAL_SHA1, CHK_COMPLEMENT, diff_ranges, pc, snes_checksum  # noqa: E402
from smar import messages as M  # noqa: E402

from rompath import ROM as BASE  # noqa: E402


def fresh():
    return Rom.load(BASE)


class TestBase(unittest.TestCase):
    def test_original_identity(self):
        rom = fresh()
        self.assertEqual(rom.sha1(), ORIGINAL_SHA1)
        self.assertEqual(len(rom.data), 0x300000)
        self.assertTrue(rom.title().startswith("Super Metroid"))

    def test_checksum_algorithm_matches_stored(self):
        rom = fresh()
        chk, comp = rom.stored_checksum()
        self.assertEqual(chk, 0xF8DF)
        self.assertEqual(comp, 0x0720)
        self.assertEqual(rom.compute_checksum(), chk)
        self.assertTrue(rom.checksum_ok())

    def test_free_space_is_unused(self):
        rom = fresh()
        free = rom.read(pc(0x85, M.FREE_START), M.FREE_END - M.FREE_START)
        self.assertEqual(set(free), {0xFF})
        self.assertNotEqual(rom.read(pc(0x85, M.FREE_START - 1), 1), b"\xFF")


class TestChecksumFix(unittest.TestCase):
    def test_fix_after_mutation(self):
        rom = fresh()
        rom.write(pc(0x85, 0xA000), b"\x12\x34\x56")
        self.assertFalse(rom.checksum_ok())
        chk = rom.fix_checksum()
        self.assertTrue(rom.checksum_ok())
        c, comp = rom.stored_checksum()
        self.assertEqual(c, chk)
        self.assertEqual(c ^ comp, 0xFFFF)
        # independent recomputation over the raw bytes
        self.assertEqual(snes_checksum(bytes(rom.data)), chk)

    def test_fix_is_noop_on_original(self):
        rom = fresh()
        rom.fix_checksum()
        self.assertEqual(rom.sha1(), ORIGINAL_SHA1)


class TestMessages(unittest.TestCase):
    def setUp(self):
        self.doc = M.extract(fresh())

    def test_extract_shape(self):
        self.assertEqual(len(self.doc["entries"]), 0x1D)
        self.assertEqual(len(self.doc["blocks"]), 26)
        texts = {b["id"]: b["text"][0].strip("|").strip() for b in self.doc["blocks"]}
        self.assertEqual(texts["msg01"], "ENERGY TANK")
        self.assertEqual(texts["msg1A"], "GRAVITY SUIT")
        e = self.doc["entries"]
        self.assertEqual(e[0x1A]["block"], M.END_ID)       # msg $1B = end marker
        self.assertEqual(e[0x1B]["block"], "msg17")        # msg $1C aliases $17
        self.assertEqual(e[0x1C]["block"], "msg18")        # msg $1D aliases $18

    def test_roundtrip_in_place_is_byte_identical(self):
        rom = fresh()
        M.build(rom, self.doc)
        rom.fix_checksum()
        self.assertEqual(rom.sha1(), ORIGINAL_SHA1)

    def test_relocation(self):
        base = fresh()
        rom = fresh()
        info = M.build(rom, self.doc, start=M.FREE_START, limit=M.FREE_END)
        rom.fix_checksum()
        self.assertTrue(rom.checksum_ok())
        self.assertEqual(len(rom.data), len(base.data))

        old = M.read_table(base)
        new = M.read_table(rom)
        delta = M.FREE_START - int(self.doc["data_start"], 16)
        for (s0, m0, t0), (s1, m1, t1) in zip(old, new):
            self.assertEqual((s0, m0), (s1, m1))            # routines untouched
            self.assertEqual(t1, t0 + delta)                # every pointer shifted by the same amount
        # content at the new location equals the original tilemaps
        size = int(self.doc["data_end"], 16) - int(self.doc["data_start"], 16)
        self.assertEqual(rom.read(pc(0x85, M.FREE_START), size),
                         base.read(pc(0x85, int(self.doc["data_start"], 16)), size))
        self.assertEqual(info["end"], M.FREE_START + size)
        # game's size rule still yields the same sizes
        for i in range(len(new) - 1):
            self.assertEqual(new[i + 1][2] - new[i][2], old[i + 1][2] - old[i][2])

        # only expected regions changed: table pointers, new data, checksum
        allowed = [(pc(0x85, M.TABLE), pc(0x85, M.TABLE + M.ENTRY_COUNT * 6)),
                   (pc(0x85, M.FREE_START), pc(0x85, M.FREE_START + size)),
                   (CHK_COMPLEMENT, CHK_COMPLEMENT + 4)]
        for s, e in diff_ranges(base.data, rom.data):
            self.assertTrue(any(a <= s and e <= b for a, b in allowed), f"unexpected change at {s:#x}-{e:#x}")

    def test_yes_no_rows_are_preserved(self):
        # $85:8523 does LDA $9581,Y: hardcoded reference into the 196 bytes between the end marker ($957F)
        # and the free area ($9643). Relocation must never touch them (or the save prompt breaks).
        base = fresh()
        rom = fresh()
        M.build(rom, self.doc, start=M.FREE_START, limit=M.FREE_END)
        self.assertEqual(rom.read(pc(0x85, 0x957F), 0x9643 - 0x957F), base.read(pc(0x85, 0x957F), 0x9643 - 0x957F))
        self.assertEqual(base.read(pc(0x85, 0x8523), 3), bytes([0xB9, 0x81, 0x95]))  # LDA $9581,Y exists

    def test_in_place_build_cannot_overwrite_yes_no_rows(self):
        doc = copy.deepcopy(self.doc)
        doc["blocks"][0]["rows"].append(" ".join(["3C4E"] * M.ROW_WORDS))   # grows past $957F
        with self.assertRaises(RomError):
            M.build(fresh(), doc)

    def test_variable_length_pointer_chain(self):
        doc = copy.deepcopy(self.doc)
        blank = " ".join(["3C4E"] * M.ROW_WORDS)
        doc["blocks"][0]["rows"].append(blank)             # msg01 grows from 1 to 2 rows
        rom = fresh()
        M.build(rom, doc, start=M.FREE_START, limit=M.FREE_END)
        t = M.read_table(rom)
        self.assertEqual(t[1][2] - t[0][2], 2 * M.ROW_BYTES)
        start0 = int(self.doc["data_start"], 16)
        for i in range(1, 0x1A):                            # entries 1..0x19 each have a block; all moved by one row
            self.assertEqual(t[i][2], M.FREE_START + M.ROW_BYTES + (int(self.doc["blocks"][i]["orig_addr"], 16)
                                                                    - start0))
        end0 = int(self.doc["data_end"], 16)                # end marker (entry 0x1A) moved by one row as well
        self.assertEqual(t[0x1A][2], M.FREE_START + M.ROW_BYTES + (end0 - start0))
        self.assertEqual(t[0x1C][2] - t[0x1B][2], 4 * M.ROW_BYTES)  # alias $1C still sized like $17

    def test_rejects_overflow(self):
        doc = copy.deepcopy(self.doc)
        doc["blocks"][0]["rows"] *= 500
        with self.assertRaises(RomError):
            M.build(fresh(), doc, start=M.FREE_START, limit=M.FREE_END)

    def test_rejects_bad_row_width(self):
        doc = copy.deepcopy(self.doc)
        doc["blocks"][3]["rows"][0] += " 3C4E"
        with self.assertRaises(RomError):
            M.build(fresh(), doc, start=M.FREE_START, limit=M.FREE_END)

    def test_rejects_broken_alias_chain(self):
        doc = copy.deepcopy(self.doc)
        b = doc["blocks"]
        i17 = next(i for i, x in enumerate(b) if x["id"] == "msg17")
        b[i17], b[i17 + 1] = b[i17 + 1], b[i17]             # msg18 no longer follows msg17
        with self.assertRaises(RomError):
            M.build(fresh(), doc, start=M.FREE_START, limit=M.FREE_END)

    def test_bank_boundary_guard(self):
        with self.assertRaises(RomError):
            fresh().write_in_bank(0x85, 0xFFF0, b"\x00" * 0x20)


if __name__ == "__main__":
    unittest.main()
