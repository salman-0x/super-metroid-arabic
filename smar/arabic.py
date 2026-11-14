"""Arabic text -> sequence of tile ids in *visual left-to-right* order (what a tilemap needs).

Steps: normalise -> contextual shaping (I/N/M/F, lam-alef ligature) -> simplified bidi (Arabic RTL paragraph,
Latin runs stay LTR) -> tile ids.  Unsupported characters raise ArabicError: nothing is silently dropped.

The tile numbers of spaces, Latin letters and punctuation depend on the font the text is drawn with, so they live in a
`Charset`: MESSAGES (BG3 2bpp message font) and MENU (BG1 4bpp menu font).
"""
from dataclasses import dataclass, field

from . import font_ar as F


@dataclass(frozen=True)
class Charset:
    space: int
    latin: dict
    punct: dict = field(default_factory=dict)


# message-box font ($9A:B200): existing English-font tiles we reuse (see the rendered font sheet)
MESSAGES = Charset(
    space=0x04E,
    latin={chr(ord("A") + i): 0x0E0 + i for i in range(26)},
    punct={".": 0x0FA, ",": 0x0FB, "?": 0x0FE, "!": 0x0FF, "-": 0x0CF, "'": 0x0FC,
           "؟": 0x0FE,     # ؟ (drawn with the existing '?' tile)
           "،": 0x0FB})    # ، (drawn with the existing ',' tile)

# menu font ($8E:8000, 4bpp): digits $60-$69, letters $6A-$83, ! ? + - . , ( ) : = $84-$8C
MENU = Charset(
    space=0x00F,
    latin={chr(ord("A") + i): 0x06A + i for i in range(26)},
    punct={"!": 0x084, "?": 0x085, "؟": 0x085, "+": 0x086, "-": 0x087, ".": 0x088, ",": 0x089, "،": 0x089,
           "(": 0x08A, ")": 0x08B, ":": 0x08C})

# backwards-compatible module constants (message font)
SPACE_TILE = MESSAGES.space
LATIN = MESSAGES.latin
PUNCT = MESSAGES.punct
TASHKEEL = set(range(0x064B, 0x0660)) | {0x0670}
LAM, ALEF = "ل", "ا"
LAMALEF = "ﻻ"


class ArabicError(ValueError):
    pass


def normalise(text: str) -> str:
    out = []
    for ch in text:
        o = ord(ch)
        if o in TASHKEEL or ch == "ـ" or ch in "‍‌‎‏":
            continue          # diacritics, tatweel and joiner/direction marks carry no glyph here
        out.append(ch)
    return "".join(out)


def _joins_next(ch):   # can this letter connect to the letter on its left (next in logical order)?
    return ch in F.DUAL


def _joinable(ch):     # can this letter accept a connection from the previous letter?
    return ch in F.DUAL or ch in F.RIGHT_ONLY


def shape(text: str, cs: Charset = MESSAGES):
    """-> list of units in LOGICAL order: ('R', glyph_key) | ('L', tile) | ('N', tile)."""
    s = normalise(text)
    units, i = [], 0
    while i < len(s):
        ch = s[i]
        prev = s[i - 1] if i else ""
        if ch in cs.latin:
            units.append(("L", cs.latin[ch]))
            i += 1
            continue
        if ch == " ":
            units.append(("N", cs.space))
            i += 1
            continue
        if ch in cs.punct:
            # '-' between two Latin letters belongs to the Latin run (X-RAY)
            nxt = s[i + 1] if i + 1 < len(s) else ""
            if ch == "-" and prev in cs.latin and nxt in cs.latin:
                units.append(("L", cs.punct[ch]))
            else:
                units.append(("N", cs.punct[ch]))
            i += 1
            continue
        if ch not in F.LETTERS:
            raise ArabicError(f"unsupported character {ch!r} (U+{ord(ch):04X}) in {text!r}")
        join_prev = bool(prev) and _joins_next(prev) and _joinable(ch)
        if ch == LAM and i + 1 < len(s) and s[i + 1] == ALEF:        # لا ligature
            units.append(("R", (LAMALEF, "F" if join_prev else "I")))
            i += 2
            continue
        nxt = s[i + 1] if i + 1 < len(s) else ""
        join_next = _joins_next(ch) and bool(nxt) and _joinable(nxt) and nxt != ""
        if ch in F.RIGHT_ONLY or ch in F.NON_JOINING:
            form = "F" if (join_prev and ch in F.RIGHT_ONLY) else "I"
        else:
            form = {(False, False): "I", (True, False): "F", (False, True): "N", (True, True): "M"}[(join_prev, join_next)]
        if form not in F.LETTERS[ch]:
            # e.g. alef maqsura has no N/M art: fall back to the closest available form
            form = "F" if "F" in F.LETTERS[ch] else "I"
        units.append(("R", (ch, form)))
        i += 1
    return units


def glyph_keys(text: str, cs: Charset = MESSAGES):
    """The set of Arabic glyph keys (letter, form) a text needs."""
    return {u[1] for u in shape(text, cs) if u[0] == "R"}


def to_tiles(text: str, table=None, cs: Charset = MESSAGES):
    """Visual left-to-right tile ids for one line of text. `table` maps glyph key -> tile id."""
    table = table or F.tile_table()
    units = shape(text, cs)
    # group consecutive Latin units into LTR runs
    tokens, run = [], []
    for kind, val in units:
        if kind == "L":
            run.append(val)
            continue
        if run:
            tokens.append(("L", run)); run = []
        tokens.append((kind, [table[val] if kind == "R" else val]))
    if run:
        tokens.append(("L", run))
    visual = []
    for _, tiles in reversed(tokens):      # RTL paragraph: reverse token order; Latin runs keep inner order
        visual.extend(tiles)
    return visual
