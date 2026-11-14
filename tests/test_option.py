import copy
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from smar import arabic as AR  # noqa: E402
from smar import menu_ar as M  # noqa: E402
from smar import option_ar as O  # noqa: E402
from smar import sm_lz  # noqa: E402
from smar import translate as T  # noqa: E402
from smar.rom import Rom, RomError, diff_ranges, pc, CHK_COMPLEMENT  # noqa: E402

from rompath import ROM as BASE  # noqa: E402
TR = json.load(open(os.path.join(ROOT, "data", "translations_ar.json"), encoding="utf-8"))
DOC = json.load(open(os.path.join(ROOT, "data", "messages.json"), encoding="utf-8"))
SLOTS = TR["_menus"]["options"]["slots"]


def fresh():
    return Rom.load(BASE)


def full_build():
    rom = fresh()
    res = T.build_arabic(rom, DOC, TR)
    return rom, res


class TestOriginalMaps(unittest.TestCase):
    def test_five_maps_decompress_to_2048_bytes_and_blank_is_000f(self):
        rom = fresh()
        for i in range(5):
            words, clen = O.load_map(rom, i)
            self.assertEqual(len(words), 1024)
            self.assertGreater(clen, 100)
            self.assertIn(O.BLANK, words)

    def test_call_sites_load_the_expected_sources(self):
        rom = fresh()
        for i in range(5):
            O.check_call_site(rom, i)

    def test_call_site_guard_trips_on_a_different_source(self):
        rom = fresh()
        rom.write(pc(0x82, O.CALL_SITES[2] + 6), bytes([0x00]))
        with self.assertRaises(RomError):
            O.check_call_site(rom, 2)

    def test_destination_of_each_call_is_the_wram_buffer_we_traced(self):
        rom = fresh()
        for i, dest in enumerate((0x7FC000, 0x7FC800, 0x7FD000, 0x7FD800, 0x7FE000)):
            b = rom.read(pc(0x82, O.CALL_SITES[i]) + 14, 3)           # inline destination after the JSL
            self.assertEqual(b[0] | (b[1] << 8) | (b[2] << 16), dest)


class TestSlots(unittest.TestCase):
    def test_every_generated_slot_matches_the_original_rom(self):
        rom = fresh()
        maps = {i: O.load_map(rom, i)[0] for i in range(5)}
        for s in SLOTS:
            O.validate_slot(maps[s["map"]], s)

    def test_slot_guard_rejects_wrong_expectations(self):
        rom = fresh()
        words = O.load_map(rom, 0)[0]
        s = copy.deepcopy(next(x for x in SLOTS if x["map"] == 0 and x["row"] == 6))
        s["expect_top"][0] = "02C"
        with self.assertRaises(RomError):
            O.validate_slot(words, s)

    def test_slot_guard_rejects_a_region_over_non_blank_cells(self):
        rom = fresh()
        words = O.load_map(rom, 0)[0]
        s = copy.deepcopy(next(x for x in SLOTS if x["map"] == 0 and x["row"] == 13))
        s["region"] = [4, 20]                                          # runs into the kanji group at column 18
        with self.assertRaises(RomError):
            O.validate_slot(words, s)

    def test_text_wider_than_the_region_is_refused(self):
        rom = fresh()
        words = O.load_map(rom, 0)[0]
        s = copy.deepcopy(next(x for x in SLOTS if x["map"] == 0 and x["row"] == 6))
        s["text"] = "ب" * 40
        small, big = M.allocate_all(set(), AR.glyph_keys(s["text"], M.BIG_CS))
        with self.assertRaises(RomError):
            O.apply_slot(words, s, small, M.BIG_CS, big)

    def test_alignment_modes(self):
        rom = fresh()
        base_words = O.load_map(rom, 0)[0]
        s0 = next(x for x in SLOTS if x["map"] == 0 and x["row"] == 6)
        for align in ("left", "right", "center"):
            s = copy.deepcopy(s0)
            s["text"], s["align"] = "ب", align
            small, big = M.allocate_all(set(), AR.glyph_keys("ب", M.BIG_CS))
            words = list(base_words)
            O.apply_slot(words, s, small, M.BIG_CS, big)
            c0, c1 = s["region"]
            cols = [c for c in range(c0, c1 + 1) if (words[6 * 32 + c] & 0x3FF) != O.BLANK]
            want = {"left": c0, "right": c1, "center": c0 + (c1 - c0 + 1 - 1) // 2}[align]
            self.assertEqual(cols, [want], align)
            self.assertEqual(words[7 * 32 + want] & 0x3FF, big[("ب", "I")][1])    # bottom tile directly below the top one

    def test_only_the_slot_region_changes(self):
        rom = fresh()
        words = O.load_map(rom, 0)[0]
        orig = list(words)
        s = next(x for x in SLOTS if x["map"] == 0 and x["row"] == 13)
        small, big = M.allocate_all(set(), AR.glyph_keys(s["text"], M.BIG_CS))
        O.apply_slot(words, s, small, M.BIG_CS, big)
        c0, c1 = s["region"]
        for i, (a, b) in enumerate(zip(orig, words)):
            r, c = divmod(i, 32)
            if a != b:
                self.assertIn(r, (13, 14))
                self.assertTrue(c0 <= c <= c1, f"changed outside the region: row {r} col {c}")
        # the kanji group beside "JAPANESE TEXT" is untouched
        for r in (13, 14):
            self.assertEqual(words[r * 32 + 18:r * 32 + 29], orig[r * 32 + 18:r * 32 + 29])

    def test_attribute_bits_are_kept(self):
        rom = fresh()
        words = O.load_map(rom, 0)[0]
        s = next(x for x in SLOTS if x["map"] == 0 and x["row"] == 13)         # the dimmed JAPANESE TEXT line (attr $0400)
        small, big = M.allocate_all(set(), AR.glyph_keys(s["text"], M.BIG_CS))
        O.apply_slot(words, s, small, M.BIG_CS, big)
        used = [w for w in words[13 * 32 + 4:13 * 32 + 18] if (w & 0x3FF) != O.BLANK]
        self.assertTrue(used and all(w & 0xFC00 == 0x0400 for w in used))


class TestBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom, cls.res = full_build()
        cls.base = fresh()
        cls.info = cls.res["menus"]

    def test_all_five_maps_were_rebuilt_and_roundtrip(self):
        self.assertEqual(sorted(self.info["options"]), [0, 1, 2, 3, 4])
        for m, i in self.info["options"].items():
            site = pc(0x82, O.CALL_SITES[m])
            bank, addr = self.rom.read(site + 2, 1)[0], self.rom.word(0x82, O.CALL_SITES[m] + 6)
            self.assertEqual((bank, addr), (O.FREE_BANK, i["at"]))
            blob, end = sm_lz.decompress(self.rom.data, pc(bank, addr))
            self.assertEqual(len(blob), 2048)
            self.assertEqual(end - pc(bank, addr), i["new_compressed"])

    def test_rebuilt_maps_equal_the_original_with_exactly_the_slot_regions_changed(self):
        small, big = self.info["table"], self.info["big_table"]
        for m in range(5):
            orig = O.load_map(self.base, m)[0]
            bank, addr = self.rom.read(pc(0x82, O.CALL_SITES[m]) + 2, 1)[0], self.rom.word(0x82, O.CALL_SITES[m] + 6)
            blob, _ = sm_lz.decompress(self.rom.data, pc(bank, addr))
            new = [blob[2 * k] | (blob[2 * k + 1] << 8) for k in range(1024)]
            expected = list(orig)
            for s in (x for x in SLOTS if x["map"] == m):
                O.apply_slot(expected, s, small, M.BIG_CS, big)
            self.assertEqual(new, expected, f"map {m}")
            self.assertNotEqual(new, orig)

    def test_no_english_big_letters_remain_in_translated_rows(self):
        # every slot's rows hold only Arabic tiles (>= $2B0) or blanks in the region
        for m in range(5):
            bank, addr = self.rom.read(pc(0x82, O.CALL_SITES[m]) + 2, 1)[0], self.rom.word(0x82, O.CALL_SITES[m] + 6)
            blob, _ = sm_lz.decompress(self.rom.data, pc(bank, addr))
            words = [blob[2 * k] | (blob[2 * k + 1] << 8) for k in range(1024)]
            for s in (x for x in SLOTS if x["map"] == m):
                c0, c1 = s["region"]
                rows = (s["row"], s["row"] + 1) if s["kind"] == "big" else (s["row"],)
                for r in rows:
                    for c in range(c0, c1 + 1):
                        t = words[r * 32 + c] & 0x3FF
                        self.assertTrue(t == O.BLANK or t >= 0x2B0, f"map {m} row {r} col {c}: tile {t:#x}")

    def test_arabic_tiles_for_the_options_are_inside_the_loaded_blob(self):
        ids = list(self.info["table"].values()) + [t for p in self.info["big_table"].values() for t in p]
        self.assertTrue(all(0x2B0 <= t < 0x400 for t in ids))
        self.assertEqual(self.info["blob_size"], M.SRC_SIZE + 32 * self.info["tiles"])
        self.assertGreater(self.info["tiles"], M.SAFE_TILES)             # this build needs the second-DMA room

    def test_second_dma_removed_exactly_when_needed(self):
        self.assertTrue(self.info["dma2_removed"])
        self.assertEqual(self.rom.read(pc(0x81, M.DMA2_ADDR), 32), bytes([0xEA]) * 32)
        # the byte after the NOPs is still the third DMA's setup
        self.assertEqual(self.rom.read(pc(0x81, M.DMA2_ADDR + 32), 5), bytes([0xA9, 0x00, 0x8D, 0x16, 0x21]))

    def test_original_compressed_maps_are_still_in_place(self):
        for i, (bank, addr) in enumerate(O.MAP_SOURCES):
            n = O.load_map(self.rom, i)[1]
            self.assertEqual(self.rom.read(pc(bank, addr), n), self.base.read(pc(bank, addr), n))

    def test_changes_are_confined_to_the_expected_regions(self):
        blob = self.info["blob_size"]
        allowed = [(pc(M.NEW_BANK, M.NEW_ADDR), pc(M.NEW_BANK, M.NEW_ADDR) + blob),
                   (pc(*M.LOADER), pc(*M.LOADER) + 8),
                   (pc(0x81, M.DMA2_ADDR), pc(0x81, M.DMA2_ADDR) + 32),
                   (pc(0x9A, T.FONT_UPPER), pc(0x9A, T.FONT_UPPER) + T.FONT_UPPER_LEN),
                   (pc(0x85, 0x877F), pc(0x85, 0x957F)),
                   (pc(0x85, T.YESNO_ROWS["A"]), pc(0x85, T.YESNO_ROWS["C"] + 64)),
                   (CHK_COMPLEMENT, CHK_COMPLEMENT + 4)]
        last = max(i["at"] + i["new_compressed"] for i in self.info["options"].values())
        allowed.append((pc(O.FREE_BANK, O.FREE_ADDR), pc(O.FREE_BANK, last)))
        for m in range(5):
            allowed.append((pc(0x82, O.CALL_SITES[m]) + 2, pc(0x82, O.CALL_SITES[m]) + 3))
            allowed.append((pc(0x82, O.CALL_SITES[m]) + 6, pc(0x82, O.CALL_SITES[m]) + 8))
        for k in list(TR["_menus"]["strings"]) + list(TR["_menus"]["big_strings"]):
            a = int(k, 16)
            allowed.append((pc(0x81, a), pc(0x81, a) + 2 * len(M.read_string(self.base, a))))
        if self.info.get("game_over"):
            from smar import gameover_ar
            allowed += gameover_ar.changed_regions(self.info["game_over"])
        if self.info.get("slot_dialogs"):
            from smar import slot_ar
            allowed += slot_ar.changed_regions(self.info["slot_dialogs"])
        if self.res.get("pause"):
            from smar import pause_ar
            allowed += pause_ar.changed_regions(self.res["pause"])
        if self.res.get("hud"):
            from smar import hud_ar
            allowed += hud_ar.changed_regions(self.res["hud"])
        if self.res.get("areas"):
            from smar import area_ar
            allowed += area_ar.changed_regions(self.res["areas"])
        if self.res.get("credit"):
            from smar import credit_ar
            allowed += credit_ar.changed_regions(self.res["credit"])
        if self.res.get("intro"):
            from smar import intro_ar
            allowed += intro_ar.changed_regions(self.res["intro"])
        for s, e in diff_ranges(self.base.data, self.rom.data):
            self.assertTrue(any(a <= s and e <= b for a, b in allowed), f"unexpected change {s:#x}-{e:#x}")
        self.assertTrue(self.rom.checksum_ok())

    def test_second_build_on_the_result_is_refused(self):
        with self.assertRaises(RomError):
            O.build_maps(self.rom, SLOTS, self.info["table"], M.BIG_CS, self.info["big_table"])      # bank $83 area is used now


class TestFreeAreaGuard(unittest.TestCase):
    def test_non_free_target_area_is_refused(self):
        rom = fresh()
        rom.write(pc(O.FREE_BANK, O.FREE_ADDR + 100), bytes([0x12]))
        keys = AR.glyph_keys(SLOTS[0]["text"], M.BIG_CS)
        small, big = M.allocate_all(set(), keys)
        with self.assertRaises(RomError):
            O.build_maps(rom, SLOTS[:1], small, M.BIG_CS, big)

    def test_the_free_area_check_runs_before_anything_is_written(self):
        rom = fresh()
        rom.write(pc(O.FREE_BANK, O.FREE_ADDR + 100), bytes([0x12]))
        before = bytes(rom.data)
        keys = AR.glyph_keys(SLOTS[0]["text"], M.BIG_CS)
        small, big = M.allocate_all(set(), keys)
        with self.assertRaises(RomError):
            O.build_maps(rom, SLOTS[:1], small, M.BIG_CS, big)
        self.assertEqual(bytes(rom.data), before)


if __name__ == "__main__":
    unittest.main()
