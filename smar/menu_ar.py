"""Arabic for the file-select menu strings (bank $81), drawn with the 4bpp BG1 menu font.

How the pieces fit (all verified against the running game, see tests/emu_menu_test.py):
  * the menu tile set is the uncompressed 4bpp block at $8E:8000, 0x5600 bytes = tiles 0..$2AF, DMA'd to VRAM word $0000
    by the loader at $81:8DF1 (inline DMA parameters: channel, mode, B-bus reg, 24-bit source, 16-bit size);
  * the same loader then DMAs $B6:8000 to VRAM word $3000, so only tile ids $2B0-$2FF (80 tiles) are free;
  * we copy the original 0x5600 bytes to the free bank $B8 and append the Arabic tiles right after them (tile $2B0 starts
    exactly at offset 0x5600), then repoint that one DMA (source bank $8E -> $B8, size 0x5600 -> 0x5600 + new tiles).
    No code is changed, only the 3 + 2 bytes of the loader's inline parameter block.
  * strings are lists of 16-bit tilemap words ended by $FFFF; the Arabic version keeps the SAME word count (padding with
    the original space words), so no pointer anywhere needs fixing.
"""
import struct

from . import arabic as AR
from . import font_ar as F
from . import font_big as FB
from . import option_ar
from .rom import Rom, RomError, pc

SRC_BANK, SRC_ADDR, SRC_SIZE = 0x8E, 0x8000, 0x5600
NEW_BANK, NEW_ADDR = 0xB8, 0x8000
FIRST_TILE = SRC_SIZE // 32                                             # $2B0
SAFE_TILES = 0x300 - FIRST_TILE                                         # 80: up to $2FF without touching the second DMA
MAX_TILES = 0x400 - FIRST_TILE                                          # 336: up to $3FF once the second DMA is neutralised
# The loader's SECOND DMA ($B6:8000 x 0x2000 -> VRAM word $3000, i.e. tile ids $300-$3FF) is dead weight for the menu family:
# verified in the running game for the file-select, option-mode and game-over screens (highest BG tile id referenced
# is $2AB) and statically for every option tilemap. We overwrite it with NOPs only when the Arabic tiles need that room.
DMA2_ADDR = 0x8DFE
DMA2_ORIG = bytes([0xA9, 0x00, 0x8D, 0x16, 0x21, 0xA9, 0x30, 0x8D, 0x17, 0x21, 0xA9, 0x80, 0x8D, 0x15, 0x21,
                   0x22, 0xA9, 0x91, 0x80, 0x01, 0x01, 0x18, 0x00, 0x80, 0xB6, 0x00, 0x20,
                   0xA9, 0x02, 0x8D, 0x0B, 0x42])
BANK_B8_SIZE = 0x8000
LOADER = (0x81, 0x8DF1)                                                 # inline DMA parameter block
LOADER_ORIG = bytes([0x01, 0x01, 0x18, 0x00, 0x80, 0x8E, 0x00, 0x56])
INK, SHADOW = 14, 13                                                    # colour indices of the English menu font

# strings we translate: address in bank $81 -> exact English text expected there (guards against patching the wrong data)
ENGLISH = {
    0xB4AC: " NO DATA   ",
    0xB4C4: "DATA COPY",
    0xB4D8: "DATA CLEAR",
    0xB4EE: "EXIT",
    0xB574: "COPY WHICH DATA?",
    0xB602: "IS THIS OK?",
    0xB63A: "COPY COMPLETED.",
    0xB65A: "       CLEAR WHICH DATA?       ",
    0xB6DA: "        DATA CLEARED...        ",
}

_PUNCT_BY_TILE = {v: k for k, v in AR.MENU.punct.items() if k in "!?+-.,():"}


def decode_english(words):
    """Words -> text using the menu charset; None if any word is something else (icon, control code...)."""
    out = []
    for w in words:
        t = w & 0x3FF
        if 0x6A <= t < 0x6A + 26:
            out.append(chr(65 + t - 0x6A))
        elif t == AR.MENU.space:
            out.append(" ")
        elif t in _PUNCT_BY_TILE:
            out.append(_PUNCT_BY_TILE[t])
        else:
            return None
    return "".join(out)


def read_string(rom: Rom, addr):
    words = []
    a = addr
    while True:
        w = struct.unpack_from("<H", rom.data, pc(0x81, a))[0]
        if w == 0xFFFF:
            return words
        words.append(w)
        a += 2
        if len(words) > 200:
            raise RomError(f"string at $81:{addr:04X} has no terminator")


# ------------------------------------------------------------------ glyphs -> 4bpp tiles
STYLE = "base"            # chosen by comparing the variants on the real menu strings (tools/menu_style_preview.py):
#                           weight only on the connecting baseline, so teeth gaps, holes and dots stay open.
#                           (bold_hv, used in the first build, merged teeth/dots/holes into solid bars)


def glyph_pixels4(rows, style=None):
    """8x8 grid of colour indices (0 / SHADOW / INK) for a glyph.
    styles: "base"    (default) the art as drawn, plus a second row under the connecting baseline (row 4) and a drop shadow;
            "base_h"  like base, plus 1-px-wide vertical runs of the upper body widened;
            "shadow"  1-px strokes + drop shadow (down-right);
            "bold_h"  every ink pixel is widened to 2 px (x, x+1) -> vertical strokes and dots 2 px, like the 2-px
                      strokes of the English menu font, then a drop shadow;
            "bold_hv" widened to 2x2 (also thicker horizontals; dots below may lose their gap)."""
    style = style or STYLE
    ink = [[False] * 8 for _ in range(8)]
    for y, r in enumerate(rows):
        for x, c in enumerate(r):
            if c == "#":
                ink[y][x] = True
                if style in ("bold_h", "bold_hv") and x + 1 < 8:
                    ink[y][x + 1] = True
                if style == "bold_hv" and y + 1 < 8:
                    ink[y + 1][x] = True
                    if x + 1 < 8:
                        ink[y + 1][x + 1] = True
    if style.startswith("base"):
        # weight only along the connecting baseline (row 4): fill the cell below it where that is free, so counters
        # (teeth gaps, holes of ص/ف/م) and the gap above the lower dots stay open
        for x in range(8):
            if ink[4][x] and not ink[5][x] and not any(ink[6][x:x + 1]) and ink[4][x]:
                ink[5][x] = True
        if style == "base_h":                     # additionally widen vertical-only runs (stems) by one pixel
            for y in range(8):
                for x in range(7):
                    if rows[y][x] == "#" and rows[y][x + 1] != "#" and (x == 0 or rows[y][x - 1] != "#") and 0 <= y <= 3:
                        if (y > 0 and rows[y - 1][x] == "#") or (y < 7 and rows[y + 1][x] == "#"):
                            ink[y][x + 1] = True
    px = [[INK if ink[y][x] else 0 for x in range(8)] for y in range(8)]
    for y in range(8):
        for x in range(8):
            if ink[y][x] and x + 1 < 8 and y + 1 < 8 and px[y + 1][x + 1] == 0:
                px[y + 1][x + 1] = SHADOW
    return px


def glyph_to_tile4(rows, style=None):
    """8 strings of '#'/'.' -> 32 bytes of SNES 4bpp (ink = 14, drop shadow = 13)."""
    px = glyph_pixels4(rows, style)
    out = bytearray(32)
    for y in range(8):
        for plane in range(4):
            b = 0
            for x in range(8):
                b |= ((px[y][x] >> plane) & 1) << (7 - x)
            out[(plane // 2) * 16 + 2 * y + (plane & 1)] = b
    return bytes(out)


def tile4_to_pixels(b):
    return [[sum(((b[(p // 2) * 16 + 2 * y + (p & 1)] >> (7 - x)) & 1) << p for p in range(4)) for x in range(8)]
            for y in range(8)]


def allocate(keys):
    keys = sorted(keys, key=lambda k: (k[0], F.FORMS.index(k[1])))
    if len(keys) > MAX_TILES:
        raise RomError(f"menu needs {len(keys)} Arabic tiles but only {MAX_TILES} are free")
    return {k: FIRST_TILE + i for i, k in enumerate(keys)}


# ------------------------------------------------------------------ big (16-px) glyphs = tile pairs
def big_rows(key):
    """The 16 rows ('#'/'.') of the big glyph for a glyph key: dedicated 8x16 art rasterised from DejaVu Sans
    (smar.font_big); the 8x8 art stretched x2 is only a fallback for a form DejaVu lacks (none today)."""
    g = FB.glyph16(*key)
    if g is not None:
        return g
    art = F.glyph_pixels(*key)
    return [art[y // 2] for y in range(16)]


def big_pixels4(rows):
    """16x8 grid (rows x cols) of colour indices for a big glyph, with a drop shadow computed on the whole 16-row image so
    it flows across the tile seam.  `rows` is 16 rows of 8 characters; an 8-row glyph is stretched vertically x2 first."""
    if len(rows) == 8:
        rows = [rows[y // 2] for y in range(16)]
    ink = [[rows[y][x] == "#" for x in range(8)] for y in range(16)]
    px = [[INK if ink[y][x] else 0 for x in range(8)] for y in range(16)]
    for y in range(16):
        for x in range(8):
            if ink[y][x] and x + 1 < 8 and y + 1 < 16 and px[y + 1][x + 1] == 0:
                px[y + 1][x + 1] = SHADOW
    return px


def _encode4(px8):
    out = bytearray(32)
    for y in range(8):
        for plane in range(4):
            b = 0
            for x in range(8):
                b |= ((px8[y][x] >> plane) & 1) << (7 - x)
            out[(plane // 2) * 16 + 2 * y + (plane & 1)] = b
    return bytes(out)


def big_glyph_tiles(rows):
    """-> (top tile bytes, bottom tile bytes) for a big glyph."""
    px = big_pixels4(rows)
    return _encode4(px[:8]), _encode4(px[8:])


def allocate_all(small_keys, big_keys):
    """Small glyphs take one tile each, big glyphs two consecutive tiles (top, bottom). Deterministic order."""
    order = lambda k: (k[0], F.FORMS.index(k[1]))                   # noqa: E731
    small, big = sorted(small_keys, key=order), sorted(big_keys, key=order)
    need = len(small) + 2 * len(big)
    if need > MAX_TILES:
        raise RomError(f"menu needs {need} Arabic tiles ({len(small)} small + 2x{len(big)} big) but only {MAX_TILES} are free")
    small_table = {k: FIRST_TILE + i for i, k in enumerate(small)}
    base = FIRST_TILE + len(small)
    big_table = {k: (base + 2 * i, base + 2 * i + 1) for i, k in enumerate(big)}
    return small_table, big_table


# the big (two-row) strings of the file-select system: exact original words, top row + $FFFE + bottom row
BIG_CS = AR.Charset(space=0x00F, latin={}, punct={})
BIG_ENGLISH = {
    0xB40A: "SAMUS DATA (title)",
    0xB436: "SAMUS A", 0xB456: "SAMUS B", 0xB476: "SAMUS C",
    0xB4F8: "DATA COPY MODE", 0xB534: "DATA CLEAR MODE",
    0xB61A: "YES", 0xB62A: "NO",
}
BIG_ORIGINAL_WORDS = {
    0xB40A: "202B 200A 2026 202D 202B 200F 200D 200A 202C 200A FFFE 203B 201A 2036 2010 203B 200F 201D 201A 2011 201A",
    0xB436: "202B 200A 2026 202D 202B 200F 200A FFFE 203B 201A 2036 2010 203B 200F 201A",
    0xB456: "202B 200A 2026 202D 202B 200F 200B FFFE 203B 201A 2036 2010 203B 200F 201B",
    0xB476: "202B 200A 2026 202D 202B 200F 200C FFFE 203B 201A 2036 2010 203B 200F 201C",
    0xB4F8: "000D 200A 202C 200A 200F 200C 2000 200D 2041 200F 2026 2000 200D 200E FFFE "
            "201D 201A 2011 201A 200F 201C 2010 2038 2017 200F 2036 2010 201D 201E",
    0xB534: "000D 000A 002C 000A 000F 000C 0025 000E 000A 000D 000F 0026 0000 000D 000E FFFE "
            "001D 001A 0011 001A 000F 001C 0035 001E 001A 003A 000F 0036 0010 001D 001E",
    0xB61A: "2041 200E 202B FFFE 2017 201E 203B",
    0xB62A: "2027 200F 2000 FFFE 2037 200F 2010",
}


def render_big_string(orig_words, text, big_table):
    """New words for a two-row big string: Arabic glyph pairs centred in the row width, same word count."""
    if orig_words.count(0xFFFE) != 1:
        raise RomError("big string must contain exactly one $FFFE line break")
    cut = orig_words.index(0xFFFE)
    top, bottom = orig_words[:cut], orig_words[cut + 1:]
    if len(top) != len(bottom):
        raise RomError("big string rows have different lengths")
    n = len(top)
    attrs = [w & 0xFC00 for w in top + bottom if (w & 0x3FF) != AR.MENU.space]
    attr = max(set(attrs), key=attrs.count)
    tiles = AR.to_tiles(text, {k: v[0] for k, v in big_table.items()}, BIG_CS)
    bottom_of = {v[0]: v[1] for v in big_table.values()}
    if len(tiles) > n:
        raise RomError(f"{text!r} needs {len(tiles)} columns but the big string row has {n}")
    ntop, nbot = [attr | AR.MENU.space] * n, [attr | AR.MENU.space] * n
    start = (n - len(tiles)) // 2
    for j, t in enumerate(tiles):
        if t != AR.MENU.space:
            ntop[start + j], nbot[start + j] = attr | t, attr | bottom_of[t]
    return ntop + [0xFFFE] + nbot


# ------------------------------------------------------------------ strings
def render_string(orig_words, text, table):
    """New words for `text`, centred in the region of the original string, same word count."""
    if any(w & 0x3FF in (0x3FE, 0x3FF) for w in orig_words):
        raise RomError("string contains control codes; not handled")
    letters = [w for w in orig_words if (w & 0x3FF) != AR.MENU.space]
    if not letters:
        raise RomError("string has no non-space word to take attribute bits from")
    attr = letters[0] & 0xFC00
    tiles = AR.to_tiles(text, table, AR.MENU)
    n = len(orig_words)
    if len(tiles) > n:
        raise RomError(f"{text!r} needs {len(tiles)} tiles but the original string has only {n} words")
    out = [w if (w & 0x3FF) == AR.MENU.space else (attr | AR.MENU.space) for w in orig_words]
    start = (n - len(tiles)) // 2
    for i, t in enumerate(tiles):
        out[start + i] = (out[start + i] & 0xFC00 if (out[start + i] & 0x3FF) == AR.MENU.space else attr) | t
    return out


def build(rom: Rom, spec: dict):
    """spec: {"strings": {"B4AC": "text", ...}, "big_strings": {"B40A": "text", ...}}. Modifies rom in place."""
    strings = {int(k, 16): v for k, v in spec.get("strings", {}).items()}
    big_strings = {int(k, 16): v for k, v in spec.get("big_strings", {}).items()}
    for addr in strings:
        if addr not in ENGLISH:
            raise RomError(f"$81:{addr:04X} is not a known translatable string")
    for addr in big_strings:
        if addr not in BIG_ENGLISH:
            raise RomError(f"$81:{addr:04X} is not a known translatable big string")
    # guard: the ROM must still hold the original English at every address and the loader must be untouched
    for addr, text in ENGLISH.items():
        if decode_english(read_string(rom, addr)) != text:
            raise RomError(f"$81:{addr:04X} does not hold the expected English string {text!r}")
    for addr, hexwords in BIG_ORIGINAL_WORDS.items():
        want = [int(x, 16) for x in hexwords.split()]
        if read_string(rom, addr) != want:
            raise RomError(f"$81:{addr:04X} does not hold the expected big string {BIG_ENGLISH[addr]!r}")
    if rom.read(pc(*LOADER), len(LOADER_ORIG)) != LOADER_ORIG:
        raise RomError("menu tile-set loader at $81:8DF1 is not the original one")
    if set(rom.read(pc(NEW_BANK, NEW_ADDR), 0x8000)) != {0xFF}:
        raise RomError("bank $B8 is not free")

    options = spec.get("options", {}).get("slots", [])
    small_keys, big_keys = set(), set()
    for text in strings.values():
        small_keys |= AR.glyph_keys(text, AR.MENU)
    for text in big_strings.values():
        big_keys |= AR.glyph_keys(text, BIG_CS)
    for s in options:
        if s["kind"] == "big":
            big_keys |= AR.glyph_keys(s["text"], BIG_CS)
        else:
            small_keys |= AR.glyph_keys(s["text"], AR.MENU)
    game_over = spec.get("game_over")
    if game_over:
        from . import gameover_ar
        small_keys |= gameover_ar.small_keys(game_over)
        big_keys |= gameover_ar.big_keys(game_over)
    slot_dialogs = spec.get("slot_dialogs")
    if slot_dialogs:
        from . import slot_ar
        small_keys |= slot_ar.small_keys(slot_dialogs)
    table, big_table = allocate_all(small_keys, big_keys)

    n_tiles = len(table) + 2 * len(big_table)
    slot_base = FIRST_TILE + n_tiles                       # three consecutive tiles: the file letters A, B, C
    if slot_dialogs:
        n_tiles += 3
        if n_tiles > MAX_TILES:
            raise RomError(f"menu needs {n_tiles} Arabic tiles but only {MAX_TILES} are free")
    if SRC_SIZE + 32 * n_tiles > BANK_B8_SIZE:
        raise RomError("the relocated tile set does not fit in bank $B8")
    dma2_removed = n_tiles > SAFE_TILES
    if dma2_removed:
        if rom.read(pc(0x81, DMA2_ADDR), len(DMA2_ORIG)) != DMA2_ORIG:
            raise RomError("second menu DMA at $81:8DFE is not the original one")
        rom.write(pc(0x81, DMA2_ADDR), bytes([0xEA]) * len(DMA2_ORIG))      # NOP x32
    blob = bytearray(rom.read(pc(SRC_BANK, SRC_ADDR), SRC_SIZE))
    blob += bytes(32 * n_tiles)
    for key, tid in table.items():
        off = tid * 32
        blob[off:off + 32] = glyph_to_tile4(F.glyph_pixels(*key))
    for key, (top_id, bottom_id) in big_table.items():
        top, bottom = big_glyph_tiles(big_rows(key))
        blob[top_id * 32:top_id * 32 + 32] = top
        blob[bottom_id * 32:bottom_id * 32 + 32] = bottom
    if slot_dialogs:
        for i, rows in enumerate(slot_ar.letter_tiles()):
            blob[(slot_base + i) * 32:(slot_base + i) * 32 + 32] = glyph_to_tile4(rows)
    rom.write(pc(NEW_BANK, NEW_ADDR), bytes(blob))

    patched = bytearray(LOADER_ORIG)
    patched[5] = NEW_BANK                                 # source bank
    patched[6:8] = struct.pack("<H", len(blob))           # size in bytes
    rom.write(pc(*LOADER), bytes(patched))

    for addr, text in strings.items():
        orig = read_string(rom, addr)
        new = render_string(orig, text, table)
        assert len(new) == len(orig)
        rom.write(pc(0x81, addr), struct.pack(f"<{len(new)}H", *new))
    for addr, text in big_strings.items():
        orig = read_string(rom, addr)
        new = render_big_string(orig, text, big_table)
        assert len(new) == len(orig)
        rom.write(pc(0x81, addr), struct.pack(f"<{len(new)}H", *new))
    opt_info = option_ar.build_maps(rom, options, table, BIG_CS, big_table) if options else {}
    go_info = gameover_ar.build(rom, game_over, table, big_table) if game_over else None
    slot_info = slot_ar.build(rom, slot_dialogs, table, slot_base) if slot_dialogs else None
    return {"tiles": n_tiles, "table": table, "big_table": big_table, "blob_size": len(blob),
            "strings": len(strings), "big_strings": len(big_strings), "dma2_removed": dma2_removed,
            "options": opt_info, "game_over": go_info, "slot_dialogs": slot_info}
