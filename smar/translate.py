"""Place shaped Arabic text into message tilemaps and inject the Arabic font into the ROM.

Row specs in the translations file are either
  * a string                      -> plain centred text line (palette bits copied from the original letters), or
  * {"text": "...{ICON}...{BTN}...", "icon": {"rows": [r0, r1], "cols": [c0, c1]}, "attr_from_row": 0}
        -> a phrase row that mixes Arabic text with graphic groups taken from the ORIGINAL tilemap:
           {ICON} = a rectangle of item-icon tiles (may span rows above the text row)
           {BTN}  = the button-name tile (A, B, R, Y, X, SEL...) found between the English fragments $D1/$D3
           The groups are moved as units, so the English phrase tiles ("select ... press the ... button") are
           replaced while the icons and the bracketed button names survive untouched.
Special key "_yes_no": {"yes": "...", "no": "..."} translates the save prompt, including the three hardcoded rows
at $85:9581/$95C1/$9601 that the game copies into the box when the cursor moves.
"""
import copy
import re
from collections import Counter

from . import arabic as AR
from . import font_ar as F
from .rom import Rom, RomError, pc
from . import messages as M

OUTSIDE_TILE = 0x00E            # transparent filler outside the message box
LETTER_RANGE = range(0xE0, 0x100)
FONT_BANK, FONT_UPPER = 0x9A, 0xC200      # $9A:C200-$D1FF = tiles 0x100-0x1FF (zero-filled in the original)
FONT_UPPER_LEN = 0x1000

BTN_OPEN, BTN_CLOSE = 0x0D1, 0x0D3        # bracket tiles around a button name
ARROW_L, ARROW_R = 0x0CC, 0x0CD           # two-tile cursor arrow
HFLIP = 0x4000
YESNO_ROWS = {"A": 0x9581, "B": 0x95C1, "C": 0x9601}   # bank $85; B = YES selected, C = NO selected (A = initial)
YES_COL, NO_COL = 8, 19                   # first tile column of the YES / NO entries (same as the English layout)
SEL_ATTR, UNSEL_ATTR, ARROW_ATTR = 0x3C00, 0x2C00, 0x3800


def inject_font(rom: Rom):
    """Write the Arabic tiles into the zero-filled upper half of the font block."""
    data, table = F.build_font_bytes()
    rom.write(pc(FONT_BANK, FONT_UPPER), data)      # the whole 4 KB region is ours by construction
    return table


def check_font_region_pristine(rom: Rom):
    return not any(rom.read(pc(FONT_BANK, FONT_UPPER), FONT_UPPER_LEN))


def row_interior(words):
    """(first, last) column of the box interior: words whose tile is not the transparent filler."""
    cols = [i for i, w in enumerate(words) if (w & 0x3FF) != OUTSIDE_TILE]
    if not cols:
        raise RomError("row has no box interior")
    return cols[0], cols[-1]


def _space_word(inner, attr):
    spaces = [w for w in inner if (w & 0x3FF) == AR.SPACE_TILE]
    return Counter(spaces).most_common(1)[0][0] if spaces else (attr | AR.SPACE_TILE)


def render_row(words, text, table, attr=None):
    lo, hi = row_interior(words)
    width = hi - lo + 1
    inner = words[lo:hi + 1]
    if attr is None:
        letters = [w for w in inner if (w & 0x3FF) in LETTER_RANGE]
        if not letters:
            raise RomError("cannot infer palette/priority bits: row has no English letters to copy them from")
        attr = letters[0] & 0xFC00
    space_word = _space_word(inner, attr)
    tiles = AR.to_tiles(text, table)
    if len(tiles) > width:
        raise RomError(f"text {text!r} needs {len(tiles)} columns but the box interior is {width}")
    start = (width - len(tiles)) // 2
    out = list(words)
    out[lo:hi + 1] = [space_word] * width
    for i, t in enumerate(tiles):
        out[lo + start + i] = space_word if t == AR.SPACE_TILE else (attr | t)
    return out


# ------------------------------------------------------------------ phrase rows (text + graphic groups)
_PLACEHOLDER = re.compile(r"(\{ICON\}|\{BTN\})")


def _title_attr(rows, row_idx):
    letters = [w for w in rows[row_idx] if (w & 0x3FF) in LETTER_RANGE]
    if not letters:
        raise RomError(f"row {row_idx} has no letters to take the palette bits from")
    return letters[0] & 0xFC00


def render_phrase(rows, r, spec, table, orig_rows=None):
    """rows: list of rows (each a list of 32 words, modified in place). r: index of the text row.
    orig_rows: the untouched rows of the block (palette bits are read from the ORIGINAL English letters,
    because an earlier row of the same block may already have been replaced by Arabic tiles)."""
    text = spec["text"]
    attr = _title_attr(orig_rows or rows, spec.get("attr_from_row", 0))
    lo, hi = row_interior(rows[r])
    width = hi - lo + 1
    space_word = _space_word(rows[r][lo:hi + 1], attr)

    icon = spec.get("icon")
    r_lo = icon["rows"][0] if icon else r
    if r_lo > r:
        raise RomError("icon rows must not start below the text row")
    span = list(range(r_lo, r + 1))

    groups = {}
    if "{ICON}" in text:
        if not icon:
            raise RomError("text uses {ICON} but no icon rectangle is given")
        c0, c1 = icon["cols"]
        cols = []
        for c in range(c0, c1 + 1):
            col = []
            for rr in span:
                inside = icon["rows"][0] <= rr <= icon["rows"][1]
                col.append(rows[rr][c] if inside else space_word)
            cols.append(col)
        groups["{ICON}"] = cols
    if "{BTN}" in text:
        found = [i for i in range(lo, hi - 1)
                 if (rows[r][i] & 0x3FF) == BTN_OPEN and (rows[r][i + 2] & 0x3FF) == BTN_CLOSE]
        if len(found) != 1:
            raise RomError(f"expected exactly one button badge in row {r}, found {len(found)}")
        i = found[0]
        # $D1/$D3 are NOT brackets: they hold the tail of the English word "the" and the head of "button",
        # glued to the badge. Only the middle tile (the button name: A, B, R, Y, X, SEL...) is a graphic to keep.
        groups["{BTN}"] = [[space_word] * (len(span) - 1) + [rows[r][i + 1]]]

    def glyph_col(tile):
        w = space_word if tile == AR.SPACE_TILE else (attr | tile)
        return [space_word] * (len(span) - 1) + [w]

    segments = [s for s in _PLACEHOLDER.split(text) if s != ""]
    visual = []
    for seg in reversed(segments):                      # RTL paragraph: segment order is mirrored
        if seg in groups:
            visual.extend(groups[seg])
        else:
            visual.extend(glyph_col(t) for t in AR.to_tiles(seg, table))
    if len(visual) > width:
        raise RomError(f"phrase {text!r} needs {len(visual)} columns but the box interior is {width}")

    for rr in span:                                      # clear everything the old phrase/icon occupied
        for c in range(lo, hi + 1):
            rows[rr][c] = space_word
    start = lo + (width - len(visual)) // 2
    for k, col in enumerate(visual):
        for j, rr in enumerate(span):
            rows[rr][start + k] = col[j]


# ------------------------------------------------------------------ YES / NO prompt
def build_yes_no_rows(template_row, yes_text, no_text, table):
    """Three 32-word rows (A/B: YES selected, C: NO selected) in the same layout as the English prompt,
    with the cursor arrow mirrored (flipped tiles, placed to the right of the entry)."""
    lo, hi = row_interior(template_row)
    space = _space_word(template_row[lo:hi + 1], SEL_ATTR)
    yes_t, no_t = AR.to_tiles(yes_text, table), AR.to_tiles(no_text, table)

    def row(selected):
        out = list(template_row)
        out[lo:hi + 1] = [space] * (hi - lo + 1)
        for col0, tiles, key in ((YES_COL, yes_t, "yes"), (NO_COL, no_t, "no")):
            attr = SEL_ATTR if key == selected else UNSEL_ATTR
            for i, t in enumerate(tiles):
                out[col0 + i] = attr | t
            if key == selected:
                a = col0 + len(tiles)                    # mirrored arrow: [CD|flip][CC|flip] right of the word
                out[a], out[a + 1] = ARROW_ATTR | ARROW_R | HFLIP, ARROW_ATTR | ARROW_L | HFLIP
        if any(not lo <= c <= hi for c in range(YES_COL, NO_COL + len(no_t) + 2)):
            raise RomError("YES/NO layout does not fit the box")
        return out
    return {"A": row("yes"), "B": row("yes"), "C": row("no")}


# ------------------------------------------------------------------ whole documents
def apply_translations(doc: dict, translations: dict, table=None):
    """Return a deep-copied doc with the listed rows replaced. translations: {block_id: {row_index: spec}}."""
    table = table or F.tile_table()
    new = copy.deepcopy(doc)
    seen = set()
    for b in new["blocks"]:
        spec = translations.get(b["id"])
        if not spec:
            continue
        seen.add(b["id"])
        rows = [[int(x, 16) for x in row.split()] for row in b["rows"]]
        orig_rows = copy.deepcopy(rows)
        for r_str, rspec in spec.items():
            if r_str.startswith("_"):
                continue            # comment keys
            r = int(r_str)
            if not 0 <= r < len(rows):
                raise RomError(f"{b['id']}: row {r} out of range (block has {len(rows)} rows)")
            if isinstance(rspec, str):
                rows[r] = render_row(rows[r], rspec, table)
                b["text"][r] = rspec
            else:
                render_phrase(rows, r, rspec, table, orig_rows)
                b["text"][r] = rspec["text"]
        b["rows"] = [" ".join(f"{w:04X}" for w in row) for row in rows]
    yn = translations.get("_yes_no")
    if yn:
        blk = next((b for b in new["blocks"] if b["id"] == "msg17"), None)
        if blk is None or len(blk["rows"]) < 4:
            raise RomError("_yes_no needs msg17 with 4 rows")
        template = [int(x, 16) for x in blk["rows"][3].split()]
        yrows = build_yes_no_rows(template, yn["yes"], yn["no"], table)
        blk["rows"][3] = " ".join(f"{w:04X}" for w in yrows["A"])
        blk["text"][3] = f"{yn['yes']} | {yn['no']}"
        new["yes_no_rows"] = {k: v for k, v in yrows.items()}
        seen.add("msg17")
    unknown = set(k for k in translations if not k.startswith("_")) - seen
    if unknown:
        raise RomError(f"translations for unknown blocks: {sorted(unknown)}")
    return new


def write_yes_no_rows(rom: Rom, rows: dict):
    """Write rows A/B/C into bank $85 after checking they currently hold the original English prompt."""
    import struct
    for key, addr in YESNO_ROWS.items():
        cur = struct.unpack("<32H", rom.read(pc(0x85, addr), 64))
        tiles = {w & 0x3FF for w in cur}
        if not {0x0F8, 0x0E4, 0x0F2} <= tiles:
            raise RomError(f"unexpected content at $85:{addr:04X}: not the English YES/NO row")
        rom.write(pc(0x85, addr), struct.pack("<32H", *rows[key]))


def build_arabic(rom: Rom, doc: dict, translations: dict, relocate: bool = False):
    """Inject font, rewrite message tilemaps (in place unless relocate), translate the YES/NO rows, fix checksum."""
    table = inject_font(rom)
    tdoc = apply_translations(doc, translations, table)
    if relocate:
        info = M.build(rom, tdoc, start=M.FREE_START, limit=M.FREE_END)
    else:
        info = M.build(rom, tdoc)
    if "yes_no_rows" in tdoc:
        write_yes_no_rows(rom, tdoc["yes_no_rows"])
    menus = None
    if "_menus" in translations:
        from . import menu_ar
        menus = menu_ar.build(rom, translations["_menus"])
    intro = None
    if "_intro" in translations:
        from . import intro_ar
        intro = intro_ar.build(rom, translations["_intro"]["pages"], translations["_intro"].get("last"))
    pause = None
    if "_pause" in translations:
        from . import pause_ar
        pause = pause_ar.build(rom, translations["_pause"])
    areas = None
    if "_areas" in translations:
        from . import area_ar
        areas = area_ar.build(rom, translations["_areas"])
    hud = None
    if "_hud" in translations:
        from . import hud_ar
        hud = hud_ar.build(rom, translations["_hud"])
    planet = None
    if "_planet" in translations:
        from . import planet_ar
        planet = planet_ar.build(rom, translations["_planet"])
    from . import credit_ar
    credit = credit_ar.build(rom)
    chk = rom.fix_checksum()
    return {"font_tiles": len(table), "info": info, "checksum": chk, "doc": tdoc, "menus": menus, "intro": intro, "pause": pause, "hud": hud, "areas": areas, "planet": planet, "credit": credit}
