import json
import os
import struct
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from smar import arabic as AR  # noqa: E402
from smar import font_ar as F  # noqa: E402
from smar import menu_ar as M  # noqa: E402
from smar.rom import Rom, RomError, diff_ranges, pc, CHK_COMPLEMENT  # noqa: E402

from rompath import ROM as BASE  # noqa: E402
TR = json.load(open(os.path.join(ROOT, "data", "translations_ar.json"), encoding="utf-8"))
SPEC = TR["_menus"]


def fresh():
    return Rom.load(BASE)


# the strings-only part of the menu spec: fits in the 80 safe tiles and never touches the second DMA. The option-screen
# maps (which need the extra room, bank $83 and the call-site patches) are covered in tests/test_option.py.
NO_OPTIONS = {k: v for k, v in SPEC.items() if k not in ("options", "game_over", "slot_dialogs")}


def built(spec=None):
    rom = fresh()
    info = M.build(rom, spec or NO_OPTIONS)
    rom.fix_checksum()
    return rom, info


class TestGuards(unittest.TestCase):
    def test_original_strings_are_where_we_expect(self):
        rom = fresh()
        for addr, text in M.ENGLISH.items():
            self.assertEqual(M.decode_english(M.read_string(rom, addr)), text, f"${addr:04X}")

    def test_loader_is_original_and_bank_b8_is_free(self):
        rom = fresh()
        self.assertEqual(rom.read(pc(*M.LOADER), 8), M.LOADER_ORIG)
        self.assertEqual(set(rom.read(pc(M.NEW_BANK, M.NEW_ADDR), 0x8000)), {0xFF})

    def test_menu_tileset_is_what_the_loader_dmas(self):
        # the loader's inline params point at $8E:8000 x 0x5600 (verified against the running game in emu_menu_test)
        p = fresh().read(pc(*M.LOADER), 8)
        self.assertEqual((p[3] | (p[4] << 8), p[5], p[6] | (p[7] << 8)), (0x8000, 0x8E, 0x5600))

    def test_second_build_on_same_rom_is_refused(self):
        rom, _ = built()
        with self.assertRaises(RomError):
            M.build(rom, SPEC)

    def test_unknown_string_address_is_refused(self):
        with self.assertRaises(RomError):
            M.build(fresh(), {"strings": {"B4AD": "ب"}})

    def test_text_longer_than_the_original_string_is_refused(self):
        with self.assertRaises(RomError):
            M.build(fresh(), {"strings": {"B4EE": "ب" * 5}})          # EXIT has 4 words

    def test_unsupported_character_is_refused(self):
        with self.assertRaises(Exception):
            M.build(fresh(), {"strings": {"B4EE": "ب٣"}})

    def test_wrong_english_at_address_is_refused(self):
        rom = fresh()
        rom.write(pc(0x81, 0xB4EE), struct.pack("<H", 0x206A))       # corrupt EXIT
        with self.assertRaises(RomError):
            M.build(rom, SPEC)


class TestGlyphs4bpp(unittest.TestCase):
    def test_roundtrip_and_colour_indices(self):
        for style in ("shadow", "base", "base_h", "bold_h", "bold_hv"):
            for key in F.all_glyph_keys():
                rows = F.glyph_pixels(*key)
                expect = M.glyph_pixels4(rows, style)
                self.assertEqual(M.tile4_to_pixels(M.glyph_to_tile4(rows, style)), expect)
                self.assertTrue({v for r in expect for v in r} <= {0, M.SHADOW, M.INK})

    def test_bold_style_keeps_baseline_joins_to_the_cell_edges(self):
        for ch, f in F.all_glyph_keys():
            px = M.glyph_pixels4(F.glyph_pixels(ch, f))
            if ch == "ﻻ":
                continue
            if f in "NM":
                self.assertEqual(px[4][0], M.INK)
            if f in "MF":
                self.assertEqual(px[4][7], M.INK)

    def test_default_style_matches_english_weight(self):
        # English menu letters use 2-px strokes: stems must be >= 2 px wide, the baseline 2 px thick
        px = M.glyph_pixels4(F.glyph_pixels("ا", "I"))      # alef isolated: 2-px stem in the art
        self.assertGreaterEqual(sum(1 for v in px[1] if v == M.INK), 2)
        px = M.glyph_pixels4(F.glyph_pixels("ب", "M"))      # beh medial: baseline is a full-width 2-px band
        for x in range(8):
            self.assertEqual((px[4][x], px[5][x]), (M.INK, M.INK))

    def test_default_style_keeps_counters_and_dot_gaps_open(self):
        """The first build (bold_hv) merged teeth, dots and holes into solid bars; the default must not."""
        # seen medial: three separate 1-px teeth on rows 2-3 (gaps at x=0,2,4,6 are never ink)
        px = M.glyph_pixels4(F.glyph_pixels("س", "M"))
        for y in (2, 3):
            self.assertEqual([x for x in range(8) if px[y][x] == M.INK], [1, 3, 5])
        # sad initial: the hole of the loop (row 3, x=4..5) stays empty or shadow, never ink
        px = M.glyph_pixels4(F.glyph_pixels("ص", "N"))
        self.assertNotIn(M.INK, (px[3][4], px[3][5]))
        # beh isolated: the lower dot (row 7) is separated from the bowl by an ink-free row 6
        px = M.glyph_pixels4(F.glyph_pixels("ب", "I"))
        self.assertNotIn(M.INK, px[6])
        self.assertIn(M.INK, px[7])

    def test_bold_hv_is_known_to_be_worse(self):
        # documents why it was dropped: it closes the sad loop
        px = M.glyph_pixels4(F.glyph_pixels("ص", "N"), "bold_hv")
        self.assertEqual((px[3][4], px[3][5]), (M.INK, M.INK))


class TestBuild(unittest.TestCase):
    def setUp(self):
        self.rom, self.info = built()
        self.base = fresh()

    def test_original_tiles_are_copied_unchanged_and_arabic_appended(self):
        new = self.rom.read(pc(M.NEW_BANK, M.NEW_ADDR), self.info["blob_size"])
        self.assertEqual(new[:M.SRC_SIZE], self.base.read(pc(M.SRC_BANK, M.SRC_ADDR), M.SRC_SIZE))
        self.assertEqual(self.info["blob_size"], M.SRC_SIZE + 32 * self.info["tiles"])
        self.assertEqual(self.info["tiles"], len(self.info["table"]) + 2 * len(self.info["big_table"]))
        for key, tid in self.info["table"].items():
            self.assertEqual(new[tid * 32:(tid + 1) * 32], M.glyph_to_tile4(F.glyph_pixels(*key)))
        for key, (top, bottom) in self.info["big_table"].items():
            t, b = M.big_glyph_tiles(M.big_rows(key))
            self.assertEqual((new[top * 32:top * 32 + 32], new[bottom * 32:bottom * 32 + 32]), (t, b))

    def test_tile_ids_are_in_the_free_vram_range_and_never_collide(self):
        ids = list(self.info["table"].values())
        for top, bottom in self.info["big_table"].values():
            self.assertEqual(bottom, top + 1)
            ids += [top, bottom]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(0x2B0 <= t < 0x300 for t in ids))

    def test_big_strings_keep_their_word_count_and_line_break(self):
        for addr in M.BIG_ORIGINAL_WORDS:
            a, b = M.read_string(self.base, addr), M.read_string(self.rom, addr)
            self.assertEqual(len(a), len(b))
            self.assertEqual(a.index(0xFFFE), b.index(0xFFFE))
            self.assertEqual(self.rom.word(0x81, addr + 2 * len(b)), 0xFFFF)

    def test_big_strings_show_arabic_pairs_top_over_bottom(self):
        bottom_of = {top: bottom for top, bottom in self.info["big_table"].values()}
        for addr in M.BIG_ORIGINAL_WORDS:
            w = M.read_string(self.rom, addr)
            cut = w.index(0xFFFE)
            top, bottom = w[:cut], w[cut + 1:]
            for tw, bw in zip(top, bottom):
                if (tw & 0x3FF) >= 0x2B0:
                    self.assertEqual(bw & 0x3FF, bottom_of[tw & 0x3FF])
                    self.assertEqual(tw & 0xFC00, bw & 0xFC00)
                else:
                    self.assertEqual((tw & 0x3FF, bw & 0x3FF), (0x0F, 0x0F))     # padding spaces in both rows

    def test_loader_repointed_with_new_size(self):
        p = self.rom.read(pc(*M.LOADER), 8)
        self.assertEqual(p[:3], bytes([1, 1, 0x18]))
        self.assertEqual(p[3:6], bytes([0x00, 0x80, M.NEW_BANK]))
        self.assertEqual(p[6] | (p[7] << 8), self.info["blob_size"])
        if not self.info["dma2_removed"]:
            self.assertLessEqual(self.info["blob_size"], 0x5600 + 80 * 32)  # never reaches VRAM word $3000 (second DMA)
        self.assertLessEqual(self.info["blob_size"], 0x8000)                # fits bank $B8

    def test_original_tileset_still_intact_for_the_other_loaders(self):
        self.assertEqual(self.rom.read(pc(0x8E, 0x8000), 0x5600), self.base.read(pc(0x8E, 0x8000), 0x5600))

    def test_strings_keep_their_word_count_and_terminator(self):
        for addr in M.ENGLISH:
            a, b = M.read_string(self.base, addr), M.read_string(self.rom, addr)
            self.assertEqual(len(a), len(b), f"${addr:04X}")
            self.assertEqual(self.rom.word(0x81, addr + 2 * len(b)), 0xFFFF)

    def test_arabic_words_use_the_original_palette_bits(self):
        for addr in M.ENGLISH:
            orig = M.read_string(self.base, addr)
            attr = [w for w in orig if (w & 0x3FF) != AR.MENU.space][0] & 0xFC00
            for w in M.read_string(self.rom, addr):
                if (w & 0x3FF) >= 0x2B0:
                    self.assertEqual(w & 0xFC00, attr)     # bits 10-15 = palette/priority/flip, unchanged

    def test_untouched_strings_are_identical(self):
        # the SAMUS-slot dialogs (letter written by code at fixed buffer offsets) and the game-over strings must not change
        for addr, n in ((0xB596, 24), (0xB5C8, 28), (0xB69A, 31), (0x9304, 23), (0x9334, 11)):
            self.assertEqual(self.rom.read(pc(0x81, addr), 2 * n), self.base.read(pc(0x81, addr), 2 * n))

    def test_only_expected_regions_changed(self):
        blob = self.info["blob_size"]
        allowed = [(pc(M.NEW_BANK, M.NEW_ADDR), pc(M.NEW_BANK, M.NEW_ADDR) + blob),
                   (pc(*M.LOADER), pc(*M.LOADER) + 8),
                   (CHK_COMPLEMENT, CHK_COMPLEMENT + 4)]
        for addr in [int(k, 16) for k in SPEC["strings"]] + [int(k, 16) for k in SPEC["big_strings"]]:
            n = len(M.read_string(self.base, addr))
            allowed.append((pc(0x81, addr), pc(0x81, addr) + 2 * n))
        for s, e in diff_ranges(self.base.data, self.rom.data):
            self.assertTrue(any(a <= s and e <= b for a, b in allowed), f"unexpected change {s:#x}-{e:#x}")
        self.assertTrue(self.rom.checksum_ok())

    def test_no_english_letters_left_in_translated_strings(self):
        for addr in (int(k, 16) for k in SPEC["strings"]):
            for w in M.read_string(self.rom, addr):
                self.assertFalse(0x6A <= (w & 0x3FF) < 0x6A + 26, f"${addr:04X} still has an English letter")

    def test_question_mark_and_period_use_menu_font_tiles(self):
        words = [w & 0x3FF for w in M.read_string(self.rom, 0xB574)]
        self.assertIn(0x085, words)                       # '?' tile of the menu font (not the message font's 0xFE)
        words = [w & 0x3FF for w in M.read_string(self.rom, 0xB63A)]
        self.assertIn(0x088, words)                       # '.'


class TestBigGlyphs(unittest.TestCase):
    def test_big_glyph_is_the_art_stretched_vertically_with_open_counters(self):
        rows = F.glyph_pixels("س", "M")
        px = M.big_pixels4(rows)
        self.assertEqual((len(px), len(px[0])), (16, 8))
        for y in range(16):
            ink = [x for x in range(8) if px[y][x] == M.INK]
            art = [x for x in range(8) if rows[y // 2][x] == "#"]
            self.assertEqual(ink, art, f"row {y}")                      # ink is exactly the art, rows doubled
        self.assertEqual([x for x in range(8) if px[4][x] == M.INK], [1, 3, 5])      # teeth stay separate (2 rows tall)

    def test_big_joins_reach_the_cell_edges_on_the_doubled_baseline(self):
        for ch, f in F.all_glyph_keys():
            if ch == "ﻻ":
                continue
            px = M.big_pixels4(F.glyph_pixels(ch, f))
            for y in (8, 9):                                             # art baseline row 4 -> rows 8 and 9
                if f in "NM":
                    self.assertEqual(px[y][0], M.INK, f"{ch} {f}")
                if f in "MF":
                    self.assertEqual(px[y][7], M.INK, f"{ch} {f}")

    def test_shadow_flows_across_the_tile_seam(self):
        # a pixel on row 7 of the top tile must cast its shadow onto row 0 of the bottom tile
        rows = ["........"] * 8
        rows[3] = "...#...."                                              # art row 3 -> big rows 6 and 7
        top, bottom = M.big_glyph_tiles(rows)
        self.assertEqual(M.tile4_to_pixels(top)[7][3], M.INK)
        self.assertEqual(M.tile4_to_pixels(bottom)[0][4], M.SHADOW)

    def test_two_tiles_per_glyph_encode_only_known_indices(self):
        for key in F.all_glyph_keys():
            for t in M.big_glyph_tiles(F.glyph_pixels(*key)):
                self.assertTrue({v for r in M.tile4_to_pixels(t) for v in r} <= {0, M.SHADOW, M.INK})

    def test_tile_budget_for_the_current_translations(self):
        small, big = set(), set()
        for t in SPEC["strings"].values():
            small |= AR.glyph_keys(t, AR.MENU)
        for t in SPEC["big_strings"].values():
            big |= AR.glyph_keys(t, M.BIG_CS)
        self.assertLessEqual(len(small) + 2 * len(big), M.MAX_TILES)

    def test_over_budget_is_refused(self):
        many = {(chr(0x0628 + i), "I") for i in range(170)}                # 170 big glyphs = 340 tiles > 336
        with self.assertRaises(RomError):
            M.allocate_all(set(), many)

    def test_budget_limits(self):
        self.assertEqual((M.FIRST_TILE, M.SAFE_TILES, M.MAX_TILES), (0x2B0, 80, 336))
        small, big = M.allocate_all({(chr(0x0628 + i), "N") for i in range(100)}, {(chr(0x0628 + i), "I") for i in range(100)})
        self.assertEqual(len(small) + 2 * len(big), 300)                   # between 80 and 336: allowed
        ids = list(small.values()) + [t for pair in big.values() for t in pair]
        self.assertTrue(all(0x2B0 <= t < 0x400 for t in ids))

    def test_second_dma_block_is_the_expected_32_bytes(self):
        self.assertEqual(len(M.DMA2_ORIG), 32)
        self.assertEqual(fresh().read(pc(0x81, M.DMA2_ADDR), 32), M.DMA2_ORIG)
        # it must end exactly where the third DMA's VRAM-address setup begins ($6000: LDA #$00 STA $2116 ... LDA #$60)
        self.assertEqual(fresh().read(pc(0x81, M.DMA2_ADDR + 32), 8), bytes([0xA9, 0x00, 0x8D, 0x16, 0x21, 0xA9, 0x60, 0x8D]))

    def test_small_builds_leave_the_second_dma_alone(self):
        rom, info = built()
        self.assertFalse(info["dma2_removed"])
        self.assertEqual(rom.read(pc(0x81, M.DMA2_ADDR), 32), M.DMA2_ORIG)


class TestBigStrings(unittest.TestCase):
    def setUp(self):
        self.rom = fresh()
        self.words = lambda a: M.read_string(self.rom, a)                  # noqa: E731

    def test_guard_rejects_a_changed_original(self):
        self.rom.write(pc(0x81, 0xB40A), struct.pack("<H", 0x202C))
        with self.assertRaises(RomError):
            M.build(self.rom, {"big_strings": {"B40A": "ب"}})

    def test_unknown_big_address_is_refused(self):
        with self.assertRaises(RomError):
            M.build(fresh(), {"big_strings": {"B40B": "ب"}})

    def test_too_wide_big_text_is_refused(self):
        with self.assertRaises(RomError):
            M.build(fresh(), {"big_strings": {"B62A": "ب" * 4}})            # NO has 3 columns

    def test_latin_letters_are_not_available_in_big_strings(self):
        with self.assertRaises(Exception):
            M.build(fresh(), {"big_strings": {"B62A": "A"}})

    def test_centering_in_the_row(self):
        rom = fresh()
        info = M.build(rom, {"big_strings": {"B62A": "لا"}})                # one glyph in a 3-column row
        w = M.read_string(rom, 0xB62A)
        cut = w.index(0xFFFE)
        glyph_cols = [i for i, x in enumerate(w[:cut]) if (x & 0x3FF) >= 0x2B0]
        self.assertEqual(glyph_cols, [1])

    def test_every_big_original_decodes_to_two_equal_rows(self):
        for addr, hexwords in M.BIG_ORIGINAL_WORDS.items():
            words = [int(x, 16) for x in hexwords.split()]
            cut = words.index(0xFFFE)
            self.assertEqual(cut, len(words) - cut - 1, f"${addr:04X}")


class TestCharsets(unittest.TestCase):
    def test_same_text_different_charset_gives_different_punctuation_tiles(self):
        t = F.tile_table()
        self.assertEqual(AR.to_tiles("؟", t, AR.MESSAGES), [0x0FE])
        self.assertEqual(AR.to_tiles("؟", t, AR.MENU), [0x085])
        self.assertEqual(AR.to_tiles(" ", t, AR.MENU), [0x00F])
        self.assertEqual(AR.to_tiles("A", t, AR.MENU), [0x06A])


if __name__ == "__main__":
    unittest.main()
