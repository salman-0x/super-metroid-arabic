import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from smar import font_ar as F  # noqa: E402
from smar import messages as M  # noqa: E402
from smar import translate as T  # noqa: E402
from smar.rom import Rom, RomError, CHK_COMPLEMENT, diff_ranges, pc  # noqa: E402

from rompath import ROM as BASE  # noqa: E402
DOC = json.load(open(os.path.join(ROOT, "data", "messages.json"), encoding="utf-8"))
TR = json.load(open(os.path.join(ROOT, "data", "translations_ar.json"), encoding="utf-8"))
TABLE = F.tile_table()


def words(row):
    return [int(x, 16) for x in row.split()]


def build(relocate=False):
    rom = Rom.load(BASE)
    res = T.build_arabic(rom, DOC, TR, relocate=relocate)
    return rom, res


class TestRenderRow(unittest.TestCase):
    def setUp(self):
        self.block = next(b for b in DOC["blocks"] if b["id"] == "msg01")
        self.orig = words(self.block["rows"][0])

    def test_text_is_centered_inside_interior_and_outside_untouched(self):
        out = T.render_row(self.orig, "ب", TABLE)
        lo, hi = T.row_interior(self.orig)
        self.assertEqual(out[:lo], self.orig[:lo])
        self.assertEqual(out[hi + 1:], self.orig[hi + 1:])
        glyph_cols = [i for i, w in enumerate(out) if 0x100 <= (w & 0x3FF) < 0x200]
        self.assertEqual(glyph_cols, [lo + (hi - lo + 1 - 1) // 2])

    def test_attribute_bits_copied_from_original_letters(self):
        attr = next(w for w in self.orig if (w & 0x3FF) in T.LETTER_RANGE) & 0xFC00
        out = T.render_row(self.orig, "بيت", TABLE)
        glyphs = [w for w in out if 0x100 <= (w & 0x3FF) < 0x200]
        self.assertEqual(len(glyphs), 3)
        for w in glyphs:
            self.assertEqual(w & 0xFC00, attr)

    def test_too_long_text_is_rejected(self):
        lo, hi = T.row_interior(self.orig)
        with self.assertRaises(RomError):
            T.render_row(self.orig, "ب" * (hi - lo + 2), TABLE)

    def test_exact_fit_is_accepted(self):
        lo, hi = T.row_interior(self.orig)
        out = T.render_row(self.orig, "ب" * (hi - lo + 1), TABLE)
        self.assertEqual(len(out), 32)

    def test_unsupported_char_is_rejected_not_dropped(self):
        with self.assertRaises(Exception):
            T.render_row(self.orig, "ب٣", TABLE)

    def test_row_without_letters_is_rejected(self):
        blank = [0x000E] * 3 + [0x3C4E] * 26 + [0x000E] * 3
        with self.assertRaises(RomError):
            T.render_row(blank, "ب", TABLE)


class TestApply(unittest.TestCase):
    def test_unknown_block_in_translations_is_an_error(self):
        with self.assertRaises(RomError):
            T.apply_translations(DOC, {"msgZZ": {"0": "ب"}})

    def test_bad_row_index_is_an_error(self):
        with self.assertRaises(RomError):
            T.apply_translations(DOC, {"msg01": {"5": "ب"}})

    def test_untranslated_rows_are_byte_identical(self):
        new = T.apply_translations(DOC, TR)
        old_b = {b["id"]: b for b in DOC["blocks"]}
        for b in new["blocks"]:
            touched = set()
            for k, v in TR.get(b["id"], {}).items():
                if k.startswith("_"):
                    continue
                r = int(k)
                lo = v["icon"]["rows"][0] if isinstance(v, dict) and v.get("icon") else r
                touched |= set(range(lo, r + 1))
            if b["id"] == "msg17" and "_yes_no" in TR:
                touched.add(3)
            for r, row in enumerate(b["rows"]):
                if r not in touched:
                    self.assertEqual(row, old_b[b["id"]]["rows"][r], f"{b['id']} row {r} changed")

    def test_all_translations_fit(self):
        T.apply_translations(DOC, TR)        # raises if any text overflows its box


def blk_rows(doc, mid):
    b = next(b for b in doc["blocks"] if b["id"] == mid)
    return [[int(x, 16) for x in r.split()] for r in b["rows"]]


def tiles(row):
    return {w & 0x3FF for w in row}


class TestPhrases(unittest.TestCase):
    PHRASE_MSGS = ["msg02", "msg03", "msg04", "msg05", "msg06", "msg0D", "msg13"]

    def setUp(self):
        self.new = T.apply_translations(DOC, TR)

    def _spec(self, mid):
        return TR[mid]["3"]

    def test_icons_survive_intact_as_contiguous_blocks(self):
        for mid in self.PHRASE_MSGS:
            icon = self._spec(mid).get("icon")
            if not icon:
                continue
            (r0, r1), (c0, c1) = icon["rows"], icon["cols"]
            orig, new = blk_rows(DOC, mid), blk_rows(self.new, mid)
            rect = [[orig[r][c] for c in range(c0, c1 + 1)] for r in range(r0, r1 + 1)]
            w = c1 - c0 + 1
            hits = [s for s in range(32 - w + 1)
                    if all(new[r0 + dr][s:s + w] == rect[dr] for dr in range(r1 - r0 + 1))]
            self.assertEqual(len(hits), 1, f"{mid}: icon block not found exactly once in the new rows")

    def test_icon_moves_to_the_right_of_the_text(self):
        # RTL: "select <icon> ..." -> the icon sits to the right of the remaining text
        for mid in ("msg02", "msg03", "msg04", "msg05", "msg06"):
            icon = self._spec(mid)["icon"]
            c0 = icon["cols"][0]
            new = blk_rows(self.new, mid)
            glyph_cols = [c for c, w in enumerate(new[3]) if 0x100 <= (w & 0x3FF) < 0x200]
            icon_cols = [c for c in range(32) if (new[2][c] & 0x3FF) not in (0x04E, 0x00E)]
            self.assertTrue(icon_cols and glyph_cols)
            self.assertGreater(min(icon_cols), min(glyph_cols), mid)      # some text is left of the icon
            self.assertLess(max(icon_cols), max(glyph_cols) + 1, mid)     # and the first word ("اختر") is right of it

    def test_button_name_kept_and_english_fragments_removed(self):
        for mid in self.PHRASE_MSGS:
            orig3, new3 = blk_rows(DOC, mid)[3], blk_rows(self.new, mid)[3]
            i = next(i for i in range(31) if orig3[i] & 0x3FF == T.BTN_OPEN)
            button_word = orig3[i + 1]
            self.assertIn(button_word, new3, f"{mid}: button name tile lost")
            self.assertNotIn(T.BTN_OPEN, tiles(new3))
            self.assertNotIn(T.BTN_CLOSE, tiles(new3))
            english_words = {t for t in tiles(orig3) if 0xB0 <= t <= 0xC8 or t in (0x0CA, 0x0CB)}
            icon = self._spec(mid).get("icon")
            if icon:
                c0, c1 = icon["cols"]
                english_words -= {orig3[c] & 0x3FF for c in range(c0, c1 + 1)}
            self.assertFalse(english_words & tiles(new3), f"{mid}: English phrase tiles remain: "
                             f"{sorted(hex(t) for t in english_words & tiles(new3))}")

    def test_phrase_glyphs_use_the_title_palette_bits(self):
        for mid in self.PHRASE_MSGS:
            title_attr = next(w for w in blk_rows(DOC, mid)[0] if w & 0x3FF in T.LETTER_RANGE) & 0xFC00
            for w in blk_rows(self.new, mid)[3]:
                if 0x100 <= (w & 0x3FF) < 0x200:
                    self.assertEqual(w & 0xFC00, title_attr)

    def test_overflowing_phrase_is_rejected(self):
        rows = blk_rows(DOC, "msg02")
        with self.assertRaises(RomError):
            T.render_phrase(rows, 3, {"text": "ب" * 30}, TABLE, copy_rows(rows))

    def test_button_placeholder_without_badge_is_rejected(self):
        rows = blk_rows(DOC, "msg02")
        with self.assertRaises(RomError):
            T.render_phrase(rows, 0, {"text": "ب {BTN}"}, TABLE, copy_rows(rows))   # title row has no badge

    def test_icon_placeholder_without_rectangle_is_rejected(self):
        rows = blk_rows(DOC, "msg02")
        with self.assertRaises(RomError):
            T.render_phrase(rows, 3, {"text": "ب {ICON}"}, TABLE, copy_rows(rows))


def copy_rows(rows):
    return [list(r) for r in rows]


class TestYesNo(unittest.TestCase):
    def setUp(self):
        self.new = T.apply_translations(DOC, TR)
        self.yn = self.new["yes_no_rows"]

    def test_three_rows_of_32_words(self):
        for k in "ABC":
            self.assertEqual(len(self.yn[k]), 32)

    def test_msg17_row3_is_row_A_and_A_equals_B(self):
        self.assertEqual(blk_rows(self.new, "msg17")[3], self.yn["A"])
        self.assertEqual(self.yn["A"], self.yn["B"])
        self.assertNotEqual(self.yn["B"], self.yn["C"])

    def test_cursor_arrow_is_mirrored_and_follows_the_selection(self):
        def arrows(row):
            return [c for c, w in enumerate(row) if w & 0x3FF in (T.ARROW_L, T.ARROW_R)]
        a, c = arrows(self.yn["B"]), arrows(self.yn["C"])
        self.assertEqual(len(a), 2)
        self.assertEqual(len(c), 2)
        self.assertLess(a[0], c[0])                                  # arrow moves from YES to NO
        for row, cols in ((self.yn["B"], a), (self.yn["C"], c)):
            self.assertTrue(row[cols[0]] & T.HFLIP and row[cols[1]] & T.HFLIP)
            self.assertEqual(row[cols[0]] & 0x3FF, T.ARROW_R)       # flipped pair: right half first
            self.assertEqual(row[cols[1]] & 0x3FF, T.ARROW_L)

    def test_no_english_letters_remain(self):
        for k in "ABC":
            self.assertFalse(tiles(self.yn[k]) & {0x0F8, 0x0E4, 0x0F2, 0x0ED, 0x0EE})

    def test_selected_entry_is_highlighted(self):
        def attrs_of_arabic(row):
            return [w & 0xFC00 for w in row if 0x100 <= (w & 0x3FF) < 0x200]
        self.assertEqual(set(attrs_of_arabic(self.yn["B"])), {T.SEL_ATTR, T.UNSEL_ATTR})
        yes_cols = range(T.YES_COL, T.YES_COL + 3)
        self.assertTrue(all(self.yn["B"][c] & 0xFC00 == T.SEL_ATTR for c in yes_cols))
        self.assertTrue(all(self.yn["C"][c] & 0xFC00 == T.UNSEL_ATTR for c in yes_cols))

    def test_rom_rows_written_and_neighbouring_bytes_untouched(self):
        import struct
        base = Rom.load(BASE)
        for relocate in (False, True):
            rom, _ = build(relocate)
            for k, addr in T.YESNO_ROWS.items():
                self.assertEqual(list(struct.unpack("<32H", rom.read(pc(0x85, addr), 64))), self.yn[k])
            for a, n in ((0x957F, 2), (0x9641, 2)):
                self.assertEqual(rom.read(pc(0x85, a), n), base.read(pc(0x85, a), n))

    def test_refuses_to_overwrite_non_english_rows(self):
        rom, _ = build()
        with self.assertRaises(RomError):
            T.write_yes_no_rows(rom, self.yn)     # already Arabic: the guard must trip


class TestBuildArabic(unittest.TestCase):
    def test_in_place_changes_only_expected_regions(self):
        base = Rom.load(BASE)
        rom, res = build()
        data_start, data_end = int(DOC["data_start"], 16), int(DOC["data_end"], 16)
        allowed = [(pc(T.FONT_BANK, T.FONT_UPPER), pc(T.FONT_BANK, T.FONT_UPPER) + T.FONT_UPPER_LEN),
                   (pc(0x85, data_start), pc(0x85, data_end)),
                   (pc(0x85, T.YESNO_ROWS["A"]), pc(0x85, T.YESNO_ROWS["C"] + 64)),
                   (CHK_COMPLEMENT, CHK_COMPLEMENT + 4)]
        if res["menus"]:                                   # file-select menu build (tests/test_menu.py covers it in detail)
            from smar import menu_ar
            allowed += [(pc(menu_ar.NEW_BANK, menu_ar.NEW_ADDR), pc(menu_ar.NEW_BANK, menu_ar.NEW_ADDR) + res["menus"]["blob_size"]),
                        (pc(*menu_ar.LOADER), pc(*menu_ar.LOADER) + 8)]
            if res["menus"]["dma2_removed"]:                  # the option-screen build needs the room of the second DMA
                allowed.append((pc(0x81, menu_ar.DMA2_ADDR), pc(0x81, menu_ar.DMA2_ADDR) + len(menu_ar.DMA2_ORIG)))
            if res["menus"]["options"]:
                from smar import option_ar
                last = max(i["at"] + i["new_compressed"] for i in res["menus"]["options"].values())
                allowed.append((pc(option_ar.FREE_BANK, option_ar.FREE_ADDR), pc(option_ar.FREE_BANK, last)))
                for m in res["menus"]["options"]:
                    allowed.append((pc(0x82, option_ar.CALL_SITES[m]) + 2, pc(0x82, option_ar.CALL_SITES[m]) + 3))
                    allowed.append((pc(0x82, option_ar.CALL_SITES[m]) + 6, pc(0x82, option_ar.CALL_SITES[m]) + 8))
            for k in list(TR["_menus"]["strings"]) + list(TR["_menus"].get("big_strings", {})):
                a = int(k, 16)
                allowed.append((pc(0x81, a), pc(0x81, a) + 2 * len(menu_ar.read_string(base, a))))
        if res["menus"] and res["menus"].get("game_over"):
            from smar import gameover_ar
            allowed += gameover_ar.changed_regions(res["menus"]["game_over"])
        if res["menus"] and res["menus"].get("slot_dialogs"):
            from smar import slot_ar
            allowed += slot_ar.changed_regions(res["menus"]["slot_dialogs"])
        if res.get("pause"):
            from smar import pause_ar
            allowed += pause_ar.changed_regions(res["pause"])
        if res.get("hud"):
            from smar import hud_ar
            allowed += hud_ar.changed_regions(res["hud"])
        if res.get("areas"):
            from smar import area_ar
            allowed += area_ar.changed_regions(res["areas"])
        if res.get("planet"):
            from smar import planet_ar
            allowed += planet_ar.changed_regions(res["planet"])
        if res.get("credit"):
            from smar import credit_ar
            allowed += credit_ar.changed_regions(res["credit"])
        if res.get("intro"):
            from smar import intro_ar
            allowed += intro_ar.changed_regions(res["intro"])
        for s, e in diff_ranges(base.data, rom.data):
            self.assertTrue(any(a <= s and e <= b for a, b in allowed), f"unexpected change {s:#x}-{e:#x}")
        # pointer table and routines untouched in place mode
        self.assertEqual(rom.read(pc(0x85, M.TABLE), M.ENTRY_COUNT * 6), base.read(pc(0x85, M.TABLE), M.ENTRY_COUNT * 6))
        self.assertTrue(rom.checksum_ok())

    def test_original_font_half_and_english_tiles_unchanged(self):
        base = Rom.load(BASE)
        rom, res = build()
        from smar import hud_ar
        a, b = rom.read(pc(0x9A, 0xB200), 0x1000), base.read(pc(0x9A, 0xB200), 0x1000)
        hud = {t for n in (res["hud"] or {"labels": {}})["labels"] for t in hud_ar.LABELS[n]["tiles"]}      # the HUD labels are edited on purpose
        self.assertEqual([i for i in range(0x100) if a[16 * i:16 * i + 16] != b[16 * i:16 * i + 16]], sorted(
            t for t in hud if a[16 * t:16 * t + 16] != b[16 * t:16 * t + 16]))
        self.assertTrue(all(a[16 * i:16 * i + 16] == b[16 * i:16 * i + 16] for i in range(0x100) if i not in hud))

    def test_font_region_was_zero_in_original(self):
        self.assertTrue(T.check_font_region_pristine(Rom.load(BASE)))

    def test_injected_font_matches_module_output(self):
        rom, res = build()
        data, _ = F.build_font_bytes()
        self.assertEqual(rom.read(pc(0x9A, 0xC200), 0x1000), data)

    def test_relocated_build_has_same_tilemap_words(self):
        a, _ = build(False)
        b, _ = build(True)
        ta, tb = M.read_table(a), M.read_table(b)
        n = int(DOC["data_end"], 16) - int(DOC["data_start"], 16)
        self.assertEqual(a.read(pc(0x85, int(DOC["data_start"], 16)), n), b.read(pc(0x85, M.FREE_START), n))
        for (s1, m1, _), (s2, m2, _) in zip(ta, tb):
            self.assertEqual((s1, m1), (s2, m2))
        self.assertTrue(b.checksum_ok())

    def test_relocated_build_still_equals_in_place_for_phrases(self):
        a, _ = build(False)
        b, _ = build(True)
        n = int(DOC["data_end"], 16) - int(DOC["data_start"], 16)
        self.assertEqual(a.read(pc(0x85, int(DOC["data_start"], 16)), n), b.read(pc(0x85, M.FREE_START), n))


if __name__ == "__main__":
    unittest.main()
