"""Arabic version of the intro story text (Samus' green typed monologue, game state $1E).

How the game draws it (measured, see analysis/intro_text_findings.md):
  * BG3 (2bpp) tilemap; chr base VRAM word $4000.  The font block is $95:D089 (LZ, 0x900 bytes = 144 tiles), decompressed to
    $7F:8000 by $8B:A405 and DMA'd to VRAM by the code at $8B:A478-$A490.  Tiles $30-$8F are overwritten with a solid fill when
    the Samus pages start, so new glyphs go to tile ids $90-$FF (the next DMA only starts at tile $100) plus the four unused
    tiles $2B-$2E.
  * Text = bank $8C list of 6-byte records `00 COL ROW PTR_LO PTR_HI B5`, one per character in typing order.  PTR points to a
    glyph object `4D 88 01 01 TILE $20` (table at $8C:D685; the space object is $D67D).  The object's width/height bytes make
    the draw routine ($8B:88B6 / $8B:9880) copy WIDTH x HEIGHT tile words, so an object `4D 88 01 02 TOP $20 BOTTOM $20` draws
    an 8x16 glyph from ONE record.
We keep every record slot (so all following instruction lists stay where they are), rewrite COL/ROW/PTR, and give the Arabic
glyphs their own two-tile objects in the free space at $8C:F3E9.  The glyphs are the 8x16 art of the big menu font
(font_big), with a 1 px dark outline like the original intro letters.
"""
import hashlib
import struct

from . import arabic as A
from . import font_big as FB
from . import sm_lz
from .rom import RomError, pc

FONT_SRC = (0x95, 0xD089)
FONT_LEN_ORIG = 0x900                  # 144 tiles
FONT_LEN_NEW = 0x1000                  # 256 tiles
NEW_TILE_SLOTS = [0x2B, 0x2C, 0x2D, 0x2E] + list(range(0x90, 0x100))      # 116 free tile ids
BLANK_TILE = 0x2F                      # the (all-zero) space tile
NEW_FONT_AT = (0x89, 0xAEFD)           # free run (0x5103 bytes)
OBJ_AT = (0x8C, 0xF3E9)                # free run (0xC17 bytes)
OBJ_SIZE = 8                           # 4D 88 01 02 + two tile words
OBJ_TABLE = 0xD685
SPACE_OBJ = 0xD67D
OBJ_BANK = 0x8C
COLS = range(1, 30)                    # columns used by the original text: 1..29
FIRST_ROW = 4
ROW_STRIDE = 3                         # glyphs are two tile rows tall; one blank tile row between lines
GLYPH_TOKEN = 0x1000                   # layout token of Arabic glyph number i is GLYPH_TOKEN + i

# code in $8B that loads and uploads the font block (all verified before patching)
SRC_BANK_AT = 0xA401                   # LDA #$9500 -> bank byte
SRC_ADDR_AT = 0xA405                   # LDA #$D089
DMA_SIZE_AT = 0xA48F                   # DMA word-size of the $7F:8000 -> VRAM $4000 transfer ($0900)

# The first page (white text, three lines) is not a record list but a compressed 32x32 BG3 tilemap
# ($97:8D12, 2048 bytes -> $7F:E000 -> VRAM $4C00).  Its 8x16 letters are tiles $30-$69 of the same font block (upper half
# at $30+n for A-P and $50+n-16 for Q-Z, lower half = upper + $10; '.' is only a lower half, $26), tilemap word $10xx.
LAST_SRC = (0x97, 0x8D12)
LAST_BANK_AT, LAST_ADDR_AT = 0xA445, 0xA449     # LDA #$9700 / STA $48 / LDA #$8D12 / STA $47 / JSL $80B0FF -> $7F:E000
LAST_TILE_SLOTS = list(range(0x30, 0x90))       # these 96 tiles hold only the white 16 px font (overwritten later anyway)
LAST_ROWS = (8, 11, 14)                          # first tile row of each of the three lines (two tile rows tall)
LAST_RIGHT = 26                                  # last column of the English block (line 1 spans columns 5-26)
LAST_LEFT = 5
LAST_PAL = 0x1000
LAST_BLANK_WORD = 0x002F
LAST_ENGLISH = {'sha1': 'bbf787d6f5019eca664600b049151e18a6352b35', 'cells': 148}                  # {sha1, cells} of the three English lines
LASTCS = A.Charset(space=0x2F, latin={}, punct={".": 0x26})

# (first record address, record count, {sha1, cells (non-blank characters)} of the English text decoded from the ROM: the original text itself is not stored here)
PAGES = [
    (0xC38C, 172, {'sha1': 'd0819b2beb79e708694d3037ed6943094db54e8f', 'cells': 135}),
    (0xC7A0, 155, {'sha1': '119122fbf8a498611d48c5e800d32754f7939e13', 'cells': 109}),
    (0xCB4E, 123, {'sha1': '787896056df28db6192e9e6f3d05c851a19267e3', 'cells': 117}),
    (0xCE3C, 133, {'sha1': '33123df19ca17fda7608d85b97da17658bf3b0ee', 'cells': 130}),
    (0xD166, 156, {'sha1': '83368ba1dea29de91850e3a2f1236161f19dcd5c', 'cells': 28}),
    (0xD51A, 31, {'sha1': 'd738cf008c06c49668cc02b95ecaebf9ed44a47e', 'cells': 49}),
]

# the intro font ($95:D089): A-Z = $00-$19, 0-9 = $1A-$23, '.' $24, ',' $25, ''' $27, '!' $2A, space = $2F (object $D67D)
_ENG = {" ": 0x2F, ".": 0x24, ",": 0x25, "'": 0x27, "!": 0x2A}
_ENG.update({chr(65 + i): i for i in range(26)})
_ENG.update({str(d): 0x1A + d for d in range(10)})
INTRO = A.Charset(
    space=0x2F,
    latin={**{chr(65 + i): i for i in range(26)}, **{str(d): 0x1A + d for d in range(10)}},
    punct={".": 0x24, ",": 0x25, "،": 0x25, "!": 0x2A})

INK, OUTLINE = 1, 3


def _rd(rom, bank, addr, n):
    return rom.read(pc(bank, addr), n)


def _ptr_of_tile(t):
    """Object address of an existing intro-font tile: $00-$28 are consecutive, '!' ($2A) sits right after them, space is $D67D."""
    if t == 0x2F:
        return SPACE_OBJ
    if t == 0x2A:
        return OBJ_TABLE + 6 * 0x29
    if 0 <= t <= 0x28:
        return OBJ_TABLE + 6 * t
    raise RomError(f"tile ${t:02X} has no glyph object")


def _tile_of_ptr(rom, ptr):
    if ptr == SPACE_OBJ:
        return 0x2F
    return _rd(rom, OBJ_BANK, ptr, 6)[4]


def _english_char(t):
    for ch, v in _ENG.items():
        if v == t:
            return ch
    return "?"


def _sha(text):
    return hashlib.sha1(text.encode()).hexdigest()


def read_pages(rom):
    """-> list of record lists; each record = [b0, col, row, ptr, b5, address]. Verifies the English text."""
    pages = []
    for first, count, expect in PAGES:
        recs = []
        for k in range(count):
            a = first + 6 * k
            b = _rd(rom, OBJ_BANK, a, 6)
            ptr = b[3] | (b[4] << 8)
            if b[0] != 0 or b[2] % 2 or not 4 <= b[2] <= 0x1C or not (ptr == SPACE_OBJ or 0xD685 <= ptr <= 0xD800):
                raise RomError(f"intro record {k} of the page at $8C:{first:04X} is not a text record: {b.hex()}")
            recs.append([b[0], b[1], b[2], ptr, b[5], a])
        rows = {}
        for _, col, row, ptr, _, _ in recs:
            rows.setdefault(row, {})[col] = _english_char(_tile_of_ptr(rom, ptr))
        got = ["".join(rows[r].get(c, "~") for c in range(1, 31)).rstrip("~") for r in sorted(rows)]
        if _sha("\n".join(got)) != expect["sha1"]:
            raise RomError(f"unexpected English text on the intro page at $8C:{first:04X}: {got}")
        pages.append(recs)
    return pages


def _verify_objects(rom):
    for t in list(range(0x29)) + [0x2A]:
        o = _rd(rom, OBJ_BANK, _ptr_of_tile(t), 6)
        if o != bytes([0x4D, 0x88, 0x01, 0x01, t, 0x20]):
            raise RomError(f"glyph object of tile ${t:02X} is not the expected one: {o.hex()}")


def _verify_code(rom):
    # LDA #$9500 / STA $48 / LDA #$D089 / STA $47 / JSL $80B0FF -> inline destination $7F:8000
    if _rd(rom, 0x8B, SRC_BANK_AT - 2, 16) != bytes.fromhex("A900958548A989D0854722FFB0800080"):
        raise RomError("unexpected code around the font-block pointer at $8B:A3FF")
    # LDA #$80 / STA $2115 / JSL $8091A9 with inline params: mode 01, reg $18, source $7F:8000, then the size word
    if _rd(rom, 0x8B, DMA_SIZE_AT - 15, 15) != bytes.fromhex("A9808D152122A9918001011800807F"):
        raise RomError("unexpected DMA parameters for the font block at $8B:A480")
    if _rd(rom, 0x8B, DMA_SIZE_AT, 2) != struct.pack("<H", FONT_LEN_ORIG):
        raise RomError("the font-block DMA size is not $0900")


def glyph_pixels16(letter, form):
    """16 rows x 8 columns of 0 (clear) / INK / OUTLINE: the big-menu-font glyph plus a 1 px 4-neighbour outline."""
    rows = FB.glyph16(letter, form)
    ink = {(x, y) for y in range(16) for x in range(8) if rows[y][x] == "#"}
    out = []
    for y in range(16):
        line = []
        for x in range(8):
            if (x, y) in ink:
                line.append(INK)
            elif any((x + dx, y + dy) in ink for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                line.append(OUTLINE)
            else:
                line.append(0)
        out.append(line)
    return out


def encode_half(pixels, y0):
    """8 rows of a 16-row pixel grid starting at y0 -> 16 bytes of SNES 2bpp."""
    out = bytearray()
    for y in range(y0, y0 + 8):
        p0 = p1 = 0
        for x in range(8):
            v = pixels[y][x]
            p0 |= (v & 1) << (7 - x)
            p1 |= (v >> 1) << (7 - x)
        out += bytes([p0, p1])
    return bytes(out)


def glyph_halves(letter, form):
    """(top tile bytes, bottom tile bytes) of one Arabic glyph form."""
    px = glyph_pixels16(letter, form)
    return encode_half(px, 0), encode_half(px, 8)


def layout_page(lines, n_slots, table):
    """Arabic lines (logical text) -> list of (col, row, token) in typing order (right to left, top to bottom).
    `table` maps glyph key -> layout token (an int >= GLYPH_TOKEN); Latin/punctuation/space are plain intro tile ids.
    Spaces are records too (object $D67D).  Surplus slots become blank space records after the last line."""
    placed = []
    for li, text in enumerate(lines):
        row = FIRST_ROW + ROW_STRIDE * li
        tiles = A.to_tiles(text, table, INTRO)            # visual left-to-right
        n = len(tiles)
        if n > len(COLS):
            raise RomError(f"intro line {text!r} needs {n} columns, only {len(COLS)} are available")
        first_col = COLS[-1] - n + 1                       # right-aligned
        for k in reversed(range(n)):                       # typing order: rightmost character first
            placed.append((first_col + k, row, tiles[k]))
    if len(placed) > n_slots:
        raise RomError(f"intro page needs {len(placed)} character records but only {n_slots} exist")
    last_row = FIRST_ROW + ROW_STRIDE * (len(lines) - 1)
    if last_row + 1 > 26:
        raise RomError("too many lines for the screen")
    while len(placed) < n_slots:
        placed.append((COLS[-1] + 1, last_row, INTRO.space))    # blank cell just right of the text area
    return placed


def changed_regions(info):
    """Every (start, end) file range build() may write; `info` is its return value."""
    out = [(pc(0x8B, SRC_BANK_AT), pc(0x8B, SRC_BANK_AT) + 1), (pc(0x8B, SRC_ADDR_AT), pc(0x8B, SRC_ADDR_AT) + 2),
           (pc(0x8B, DMA_SIZE_AT), pc(0x8B, DMA_SIZE_AT) + 2),
           (pc(*NEW_FONT_AT), pc(*NEW_FONT_AT) + info["font_bytes"]),
           (pc(*OBJ_AT), pc(*OBJ_AT) + OBJ_SIZE * info["glyphs"])]
    out += [(pc(OBJ_BANK, first), pc(OBJ_BANK, first) + 6 * n) for first, n, _ in PAGES]
    if info.get("last_at"):
        out += [(pc(*info["last_at"]), pc(*info["last_at"]) + info["last_bytes"]),
                (pc(0x8B, LAST_BANK_AT), pc(0x8B, LAST_BANK_AT) + 1), (pc(0x8B, LAST_ADDR_AT), pc(0x8B, LAST_ADDR_AT) + 2)]
    return out


def used_glyphs(pages_text):
    keys = set()
    for lines in pages_text:
        for text in lines:
            keys |= A.glyph_keys(text, INTRO)
    return sorted(keys, key=lambda k: (k[0], A.F.FORMS.index(k[1])))


def _allocate(keys, slots):
    """Deduplicate the non-blank halves of the glyphs in `keys` onto `slots`.
    -> (unique: tile bytes -> tile id, pairs: per glyph (top id, bottom id))."""
    blank = bytes(16)
    unique, pairs = {}, []
    for k in keys:
        pair = []
        for half in glyph_halves(*k):
            if half == blank:
                pair.append(BLANK_TILE)
                continue
            if half not in unique:
                if len(unique) >= len(slots):
                    raise RomError(f"the intro needs more than the {len(slots)} free tiles for its Arabic glyphs")
                unique[half] = slots[len(unique)]
            pair.append(unique[half])
        pairs.append(tuple(pair))
    return unique, pairs


def _verify_last_code(rom):
    # LDA #$9700 / STA $48 / LDA #$8D12 / STA $47 / JSL $80B0FF -> inline destination $7F:E000
    if _rd(rom, 0x8B, LAST_BANK_AT - 2, 17) != bytes.fromhex("A9009785" "48A9128D" "854722FF" "B08000E07F"):
        raise RomError("unexpected code around the page-tilemap pointer at $8B:A443")


def _decode_last(words):
    """Rows 8/9, 11/12, 14/15 of the original tilemap -> the three English lines (verified against LAST_ENGLISH)."""
    def letter(up):
        if 0x30 <= up <= 0x3F:
            return chr(65 + up - 0x30)
        if 0x50 <= up <= 0x59:
            return chr(65 + 16 + up - 0x50)
        return None
    lines = []
    for r in LAST_ROWS:
        s = ""
        for c in range(32):
            up, lo = words[r * 32 + c] & 0x3FF, words[(r + 1) * 32 + c] & 0x3FF
            if up == 0x2F and lo == 0x2F:
                s += " "
            elif up == 0x2F and lo == 0x26:
                s += "."
            elif letter(up) is not None and lo == up + 0x10:
                s += letter(up)
            else:
                raise RomError(f"unexpected tiles {up:#x}/{lo:#x} in row {r} column {c} of the first intro page")
        lines.append(s.strip())
    return lines


def layout_last(lines, table):
    """Arabic lines -> {(row, col): word} for the page tilemap; right-aligned at LAST_RIGHT. `table`: glyph key -> token."""
    if len(lines) > len(LAST_ROWS):
        raise RomError("the first intro page has room for three lines")
    words = {}
    for r, text in zip(LAST_ROWS, lines):
        toks = A.to_tiles(text, table, LASTCS)
        if len(toks) > LAST_RIGHT - LAST_LEFT + 1:
            raise RomError(f"first-page line {text!r} needs {len(toks)} columns, only {LAST_RIGHT - LAST_LEFT + 1} exist")
        c0 = LAST_RIGHT - len(toks) + 1
        for k, tok in enumerate(toks):
            words[(r, c0 + k)] = tok
    return words


def build(rom, pages_text, last_lines=None):
    """pages_text: list of 6 lists of Arabic lines (the typed Samus pages); last_lines: the three lines of the first,
    white page (optional). Returns a report dict."""
    if len(pages_text) != len(PAGES):
        raise RomError(f"expected {len(PAGES)} intro pages, got {len(pages_text)}")
    _verify_objects(rom)
    _verify_code(rom)
    pages = read_pages(rom)

    keys = used_glyphs(pages_text)
    unique, glyph_tiles = _allocate(keys, NEW_TILE_SLOTS)
    table = {k: GLYPH_TOKEN + i for i, k in enumerate(keys)}

    # 1. font block: original 144 tiles + the Arabic tiles, recompressed into free space
    orig, _ = sm_lz.decompress(bytes(rom.data), pc(*FONT_SRC), 0x2000)
    if len(orig) != FONT_LEN_ORIG:
        raise RomError(f"unexpected font block length {len(orig):#x}")
    block = bytearray(orig) + bytearray(FONT_LEN_NEW - FONT_LEN_ORIG)
    for t in NEW_TILE_SLOTS:
        if any(block[t * 16:t * 16 + 16]):
            raise RomError(f"tile ${t:02X} of the font block is not blank")
    for half, t in unique.items():
        block[t * 16:t * 16 + 16] = half

    # 1b. first page: its own glyph tiles replace the white English font ($30-$8F, only used by that page)
    last = None
    if last_lines is not None:
        _verify_last_code(rom)
        tm, _ = sm_lz.decompress(bytes(rom.data), pc(*LAST_SRC), 0x1000)
        if len(tm) != 2048:
            raise RomError(f"unexpected first-page tilemap length {len(tm)}")
        words = list(struct.unpack("<1024H", tm))
        if _sha("\n".join(_decode_last(words))) != LAST_ENGLISH["sha1"]:
            raise RomError("unexpected English text on the first intro page")
        lkeys = sorted({k for text in last_lines for k in A.glyph_keys(text, LASTCS)},
                       key=lambda k: (k[0], A.F.FORMS.index(k[1])))
        lunique, lpairs = _allocate(lkeys, LAST_TILE_SLOTS)
        for half, t in lunique.items():
            block[t * 16:t * 16 + 16] = half
        ltable = {k: GLYPH_TOKEN + i for i, k in enumerate(lkeys)}
        for r in LAST_ROWS:                                    # clear the English text rows
            for c in range(32):
                for rr in (r, r + 1):
                    words[rr * 32 + c] = LAST_BLANK_WORD
        for (r, c), tok in layout_last(last_lines, ltable).items():
            if tok >= GLYPH_TOKEN:
                up, lo = lpairs[tok - GLYPH_TOKEN]
            elif tok == 0x26:
                up, lo = BLANK_TILE, 0x26
            else:
                up, lo = BLANK_TILE, BLANK_TILE
            if (up, lo) == (BLANK_TILE, BLANK_TILE):
                continue
            words[r * 32 + c] = LAST_PAL | up
            words[(r + 1) * 32 + c] = LAST_PAL | lo
        last = {"words": words, "tiles": len(lunique), "glyphs": len(lkeys)}

    comp = sm_lz.compress(bytes(block))
    if sm_lz.decompress(comp, 0, 0x2000)[0] != bytes(block):
        raise RomError("font block compression does not round-trip")
    if rom.read(pc(*NEW_FONT_AT), len(comp)) != b"\xFF" * len(comp):
        raise RomError(f"$89:AEFD is not free for {len(comp)} bytes")
    rom.write(pc(*NEW_FONT_AT), comp)
    rom.write(pc(0x8B, SRC_BANK_AT), bytes([NEW_FONT_AT[0]]))
    rom.write(pc(0x8B, SRC_ADDR_AT), struct.pack("<H", NEW_FONT_AT[1]))
    rom.write(pc(0x8B, DMA_SIZE_AT), struct.pack("<H", FONT_LEN_NEW))

    last_at, last_bytes = None, 0
    if last is not None:
        tmap = sm_lz.compress(struct.pack("<1024H", *last["words"]))
        if sm_lz.decompress(tmap, 0, 0x1000)[0] != struct.pack("<1024H", *last["words"]):
            raise RomError("first-page tilemap compression does not round-trip")
        last_at = (NEW_FONT_AT[0], NEW_FONT_AT[1] + len(comp))
        if last_at[1] + len(tmap) > 0x10000 or rom.read(pc(*last_at), len(tmap)) != b"\xFF" * len(tmap):
            raise RomError("no room for the first-page tilemap after the font block")
        rom.write(pc(*last_at), tmap)
        rom.write(pc(0x8B, LAST_BANK_AT), bytes([last_at[0]]))
        rom.write(pc(0x8B, LAST_ADDR_AT), struct.pack("<H", last_at[1]))
        last_bytes = len(tmap)

    # 2. one two-tile glyph object per Arabic glyph form
    blob = bytearray()
    for top, bottom in glyph_tiles:
        blob += bytes([0x4D, 0x88, 0x01, 0x02, top, 0x20, bottom, 0x20])
    if OBJ_AT[1] + len(blob) > 0x10000 or rom.read(pc(*OBJ_AT), len(blob)) != b"\xFF" * len(blob):
        raise RomError("no room for the intro glyph objects at $8C:F3E9")
    rom.write(pc(*OBJ_AT), bytes(blob))

    # 3. rewrite the records of every page
    for recs, lines in zip(pages, pages_text):
        placed = layout_page(lines, len(recs), table)
        for rec, (col, row, tok) in zip(recs, placed):
            ptr = OBJ_AT[1] + OBJ_SIZE * (tok - GLYPH_TOKEN) if tok >= GLYPH_TOKEN else _ptr_of_tile(tok)
            rom.write(pc(OBJ_BANK, rec[5] + 1), bytes([col, row]) + struct.pack("<H", ptr))
    return {"glyphs": len(keys), "tiles": len(unique), "font_bytes": len(comp), "pages": len(pages),
            "table": dict(zip(keys, glyph_tiles)), "last_at": last_at, "last_bytes": last_bytes,
            "last_tiles": last["tiles"] if last else 0}