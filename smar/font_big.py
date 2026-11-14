"""8x16 Arabic glyphs for the big (16-px) menu font, rasterised from DejaVu Sans Bold's Arabic presentation forms.

DejaVu Sans (Bitstream Vera licence + public-domain additions) is free to use, modify and embed; the ROM only receives the
resulting 1-bit bitmaps.  The rasteriser is deterministic and its parameters are pinned below, so rebuilding gives the same
tiles.  Rules that make the bitmaps work as a monospaced, joined font on the 8x16 tile cell:

  * font-wide vertical scale (one pixels-per-em for every glyph) with the BASELINE pinned: the connecting stroke always
    occupies the same rows, so letters line up when placed side by side
  * connecting forms are scaled horizontally so the ink spans the cell edge to edge on the joined sides, then the joins are
    made explicit (ink on both baseline rows at column 0 / 7), exactly like the 8x8 font
  * non-joining sides keep a margin; narrow letters (alef, dal, ...) keep their natural width, thickened to >= 2 px
  * DOTS are found as small separate blobs in the high-resolution rasterisation, removed from the body, and redrawn as solid
    2x2 dots at their scaled positions (spaced apart so groups of two/three stay distinct).  Left to the downscaler they
    vanish: a 1.4 px dot averages below any sensible ink threshold.
"""
import os
import unicodedata

from PIL import Image, ImageDraw, ImageFont

from . import font_ar as F

PX_PER_EM = 14.0
BASELINE_BOTTOM = 12            # lower edge of the baseline stroke -> stroke rows 10-11
BASE_ROWS = (10, 11)
CELL_W, CELL_H = 8, 16
SS = 160                        # render size (supersampling)
RED = 4                         # component labelling happens at 1/RED of SS
WEIGHT = "regular"             # chosen by comparing weights/thresholds on real words (tools/preview_big_variants.py): the Bold
THRESHOLD = 0.30               # weight fills in loop counters (ف ق ه م ع ك turn to blobs), Regular keeps them open
MIN_STEM = 2
DOT_MAX_AREA = 20               # (at SS/RED = 40 px per em) measured: real dots are ~9-12 px^2 and 3-4 px wide, while hamza is
DOT_MAX_SIDE = 5                # ~36 px^2 and 7-9 px wide, so these limits separate the two
DOT_MIN_AREA = 5
DOT_GAP = 3                     # minimum distance between dot centres (2x2 dots + a 1-px gap)
TOP_MARGIN = 0.3                # ink must stay at least this far inside the top / bottom edge of the cell
TAIL_MARGIN = 0.3
EXTENTS = {}                    # (letter, form) -> (top, bottom) of the ink in cell rows, filled by glyph16 (used by the tests)


WEIGHTS = {"bold": "DejaVuSans-Bold.ttf", "regular": "DejaVuSans.ttf"}


def font_path(weight="bold"):
    import matplotlib
    name = WEIGHTS[weight]
    p = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf", name)
    if not os.path.exists(p):
        raise FileNotFoundError(f"{name} not found (it ships with matplotlib)")
    return p


_TAG = {"I": "<isolated>", "N": "<initial>", "M": "<medial>", "F": "<final>"}
_PRES = {}
for _cp in range(0xFE70, 0xFEFD):
    _d = unicodedata.decomposition(chr(_cp))
    if _d.startswith("<") and " " in _d:
        _tag, _rest = _d.split(" ", 1)
        _PRES[(_tag, _rest)] = chr(_cp)


def presentation(letter, form):
    """Unicode presentation-form character for (base letter, form) or None."""
    if letter == "ﻻ":                                   # lam-alef ligature: its own presentation forms
        return {"I": "ﻻ", "F": "ﻼ"}.get(form)
    return _PRES.get((_TAG[form], f"{ord(letter):04X}"))


_fonts = {}


def _font_obj(weight="bold"):
    if weight not in _fonts:
        _fonts[weight] = ImageFont.truetype(font_path(weight), SS)
    return _fonts[weight]


def _render(ch, weight="bold"):
    """-> (alpha image, baseline y). The character is drawn with its origin at (SS/2, baseline)."""
    f = _font_obj(weight)
    img = Image.new("L", (SS * 2, SS * 3), 0)
    base = int(SS * 1.9)
    ImageDraw.Draw(img).text((SS // 2, base), ch, font=f, fill=255, anchor="ls")
    return img, base


def _blobs(img):
    """Connected components (4-neighbour) of the image thresholded at 128, found at 1/RED resolution.
    -> list of dicts with area, bbox (full-res px), centroid (full-res px)."""
    small = img.resize((img.width // RED, img.height // RED), Image.BOX)
    w, h = small.size
    px = small.load()
    seen = [[False] * w for _ in range(h)]
    out = []
    for y in range(h):
        for x in range(w):
            if px[x, y] >= 100 and not seen[y][x]:
                stack, pts = [(x, y)], []
                seen[y][x] = True
                while stack:
                    cx, cy = stack.pop()
                    pts.append((cx, cy))
                    for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                        if 0 <= nx < w and 0 <= ny < h and px[nx, ny] >= 100 and not seen[ny][nx]:
                            seen[ny][nx] = True
                            stack.append((nx, ny))
                xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                out.append({"area": len(pts), "bbox": (min(xs), min(ys), max(xs) + 1, max(ys) + 1),
                            "centroid": ((sum(xs) / len(xs) + 0.5) * RED, (sum(ys) / len(ys) + 0.5) * RED)})
    return out


def _is_dot(b, biggest):
    x0, y0, x1, y1 = b["bbox"]
    w, h = x1 - x0, y1 - y0
    return (b is not biggest and DOT_MIN_AREA <= b["area"] <= DOT_MAX_AREA and w <= DOT_MAX_SIDE and h <= DOT_MAX_SIDE
            and 0.55 <= (w / max(h, 1)) <= 1.8)


def _space_dots(dots):
    """dots: list of [x, y] target centres. Push apart groups that are closer than DOT_GAP so each 2x2 dot stays separate."""
    for _ in range(6):
        moved = False
        for i in range(len(dots)):
            for j in range(i + 1, len(dots)):
                dx, dy = dots[j][0] - dots[i][0], dots[j][1] - dots[i][1]
                if abs(dx) < DOT_GAP and abs(dy) < DOT_GAP:
                    if abs(dx) >= abs(dy):
                        push = (DOT_GAP - abs(dx)) / 2.0 + 0.01
                        s = 1 if dx >= 0 else -1
                        dots[i][0] -= s * push
                        dots[j][0] += s * push
                    else:
                        push = (DOT_GAP - abs(dy)) / 2.0 + 0.01
                        s = 1 if dy >= 0 else -1
                        dots[i][1] -= s * push
                        dots[j][1] += s * push
                    moved = True
        if not moved:
            break


# Hand-drawn bodies where the outline raster fails: DejaVu's three seen/sheen teeth are ~1 px each at this size and the
# downscaler merges them into one 4-px block, so the letter loses its identity.  Dots are still added by glyph16.
def _art(*rows):
    rows = list(rows) + ["........"] * (16 - len(rows))
    assert len(rows) == 16 and all(len(r) == 8 for r in rows), rows
    return rows


_SEEN_TEETH = {"N": ".#.#.#..", "M": ".#.#.#.#", "F": "..#.#.#.", "I": "..#.#.#."}
_SEEN_BASE = {"N": "#######.", "M": "########", "F": ".#######", "I": ".######."}
_SEEN_BOWL = {"N": [], "M": [],
              "F": ["##....##", "##....##", ".######."],
              "I": ["##....#.", "##....#.", ".#####.."]}


def _seen_body(form):
    rows = ["........"] * 7 + [_SEEN_TEETH[form]] * 3 + [_SEEN_BASE[form]] * 2 + _SEEN_BOWL[form]
    return _art(*rows)


BODY_OVERRIDES = {(ch, f): _seen_body(f) for ch in "سش" for f in "NMFI"}


def _widen_thin_verticals(rows):
    """Minimum stroke width: a vertical stroke that is only 1 px wide (lam and tah stems come out that way from the outline at
    this size, while alef is 2 px) is widened to 2 px.  The extra pixel goes on the side with more free space and only where
    the pixel beyond it is empty, so gaps between neighbouring strokes are never closed."""
    h, w = len(rows), len(rows[0])
    add = []
    for y in range(h):
        for x in range(w):
            if rows[y][x] != "#":
                continue
            left = x > 0 and rows[y][x - 1] == "#"
            right = x < w - 1 and rows[y][x + 1] == "#"
            if left or right:
                continue                                          # already part of a wider run
            vertical = (y > 0 and rows[y - 1][x] == "#") or (y < h - 1 and rows[y + 1][x] == "#")
            if not vertical:
                continue
            free_left = 0
            while x - 1 - free_left >= 0 and rows[y][x - 1 - free_left] == "." and free_left < 3:
                free_left += 1
            free_right = 0
            while x + 1 + free_right < w and rows[y][x + 1 + free_right] == "." and free_right < 3:
                free_right += 1
            if free_left >= 2 and free_left >= free_right:
                add.append((x - 1, y))
            elif free_right >= 2:
                add.append((x + 1, y))
            elif free_left >= 2:
                add.append((x - 1, y))
    for x, y in add:
        rows[y][x] = "#"


def _triangle(centres):
    """Three dots (ث ش): lay them out as an apex over a pair, each a 2x2 block separated by one pixel:
         ..##..          apex centred above the pair; the pair sits one blank row below it, one blank column between
         ......          them and the apex's columns.  Orientation (apex up/down) follows the original glyph.
         ##..##"""
    cx = sum(c[0] for c in centres) / 3.0
    cy = sum(c[1] for c in centres) / 3.0
    by_y = sorted(centres, key=lambda c: c[1])
    apex_up = (by_y[1][1] - by_y[0][1]) > (by_y[2][1] - by_y[1][1])          # one dot clearly above the other two
    top_y, bot_y = cy - 1.5, cy + 1.5
    apex = [cx, top_y if apex_up else bot_y]
    pair_y = bot_y if apex_up else top_y
    # centres are used as "centre - 1" later, so give 2x2 block centres: apex over the middle, pair 3 px apart
    return [apex, [cx - 1.5, pair_y], [cx + 1.5, pair_y]]


def glyph16(letter, form, weight=None, threshold=None):
    """8x16 rows ('#'/'.') for a glyph, or None if DejaVu has no presentation form for it."""
    thr = THRESHOLD if threshold is None else threshold
    weight = weight or WEIGHT
    ch = presentation(letter, form)
    if ch is None:
        return None
    img, base = _render(ch, weight)
    blobs = _blobs(img)
    if not blobs:
        return None
    biggest = max(blobs, key=lambda b: b["area"])
    dots = [b for b in blobs if _is_dot(b, biggest)]
    body = img.copy()
    draw = ImageDraw.Draw(body)
    for b in dots:                                              # erase the dots (with a margin) from the body image
        x0, y0, x1, y1 = b["bbox"]
        draw.rectangle([x0 * RED - RED, y0 * RED - RED, x1 * RED + RED, y1 * RED + RED], fill=0)
    if dots:
        biggest = max(_blobs(body), key=lambda b: b["area"]) if _blobs(body) else biggest
    bbox = body.getbbox()
    if bbox is None:
        return None
    x0, y0, x1, y1 = bbox
    sy = PX_PER_EM / SS
    # Tall glyphs (alef + hamza/madda) would rise above row 0 and the deepest tails below row 15, which clips the mark:
    # shrink such a glyph (vertically only, about the baseline) just enough to fit.  Plain letters are unaffected.
    all_y0 = min([y0] + [b["bbox"][1] * RED for b in dots])
    all_y1 = max([y1] + [b["bbox"][3] * RED for b in dots])
    up_room, down_room = BASELINE_BOTTOM - TOP_MARGIN, CELL_H - TAIL_MARGIN - BASELINE_BOTTOM
    up, down = (base - all_y0) * sy, (all_y1 - base) * sy
    sy *= min(1.0, up_room / up if up > 0 else 1.0, down_room / down if down > 0 else 1.0)
    EXTENTS[(letter, form)] = (BASELINE_BOTTOM + (all_y0 - base) * sy, BASELINE_BOTTOM + (all_y1 - base) * sy)
    nat_w = (x1 - x0) * sy
    joins_left, joins_right = form in "NM", form in "MF"
    if joins_left and joins_right:
        tx0, tx1 = 0.0, 8.0
    elif joins_left:
        tx0 = 0.0
        tx1 = 7.0 if nat_w > 4.0 else max(nat_w, 2.0)
    elif joins_right:
        tx1 = 8.0
        tx0 = 1.0 if nat_w > 4.0 else 8.0 - max(min(nat_w, 7.0), 2.0)
    else:
        w = max(min(nat_w, 6.0), float(MIN_STEM))
        tx0 = (8.0 - w) / 2.0
        tx1 = tx0 + w
    sx = (tx1 - tx0) / max(x1 - x0, 1)
    top = BASELINE_BOTTOM + (y0 - base) * sy
    crop = body.crop((x0, y0, x1, y1))
    tw, th = max(1, round((tx1 - tx0) * 8)), max(1, round((y1 - y0) * sy * 8))
    canvas = Image.new("L", (CELL_W * 8, CELL_H * 8), 0)
    canvas.paste(crop.resize((tw, th), Image.BOX), (round(tx0 * 8), round(top * 8)))
    px = canvas.resize((CELL_W, CELL_H), Image.BOX).load()
    rows = [["#" if px[x, y] / 255.0 >= thr else "." for x in range(CELL_W)] for y in range(CELL_H)]
    for y in BASE_ROWS:                                         # explicit joins on the baseline rows
        if joins_left and "#" in rows[y]:
            for x in range(0, rows[y].index("#")):
                rows[y][x] = "#"
        if joins_right and "#" in rows[y]:
            last = max(x for x in range(CELL_W) if rows[y][x] == "#")
            for x in range(last, CELL_W):
                rows[y][x] = "#"
    _widen_thin_verticals(rows)
    if (letter, form) in BODY_OVERRIDES:
        rows = [list(r) for r in BODY_OVERRIDES[(letter, form)]]
    centres = []
    for b in dots:
        cx, cy = b["centroid"]
        centres.append([tx0 + (cx - x0) * sx, BASELINE_BOTTOM + (cy - base) * sy])
    if len(centres) == 3:
        centres = _triangle(centres)
    else:
        _space_dots(centres)
    body_ink = [(x, y) for y in range(CELL_H) for x in range(CELL_W) if rows[y][x] == "#"]
    body_cy = (sum(y for _, y in body_ink) / len(body_ink)) if body_ink else BASELINE_BOTTOM
    blocks = [(min(max(int(round(cx - 1.0)), 0), CELL_W - 2), min(max(int(round(cy - 1.0)), 0), CELL_H - 2))
              for cx, cy in centres]
    if blocks:
        mean_cy = sum(c[1] for c in centres) / len(centres)
        step = -1 if mean_cy < body_cy else 1            # dot groups above the body move up, groups below move down
        placed, (bw, bh) = _place_group(body_ink, blocks, step)
        for x0d, y0d in placed:
            for y in range(y0d, y0d + bh):
                for x in range(x0d, x0d + bw):
                    rows[y][x] = "#"
    return ["".join(r) for r in rows]


def _touches(body_ink, x0, y0, w=2, h=2):
    """True if any body pixel lies within one pixel of the w x h block at (x0, y0) (i.e. there would be no gap)."""
    return any(x0 - 1 <= x <= x0 + w and y0 - 1 <= y <= y0 + h for x, y in body_ink)


def _place_group(body_ink, blocks, step):
    """Move the whole dot group (so its internal layout survives) away from the body until every block has a one-pixel gap.
    Preference: 2x2 dots; if the cell has no room, flatten them to 2x1 (still clearly a dot, and the gap is restored)."""
    for size in ((2, 2), (2, 1), (1, 1)):
        w, h = size
        # displacement candidates, smallest first; vertical moves away from the body are preferred over sideways ones
        moves = sorted(((dx, step * s) for s in range(0, 9) for dx in (0, 1, -1, 2, -2)),
                       key=lambda m: (abs(m[0]) + abs(m[1]), abs(m[0])))
        for dx, dy in moves:
            cand = [(x + dx, y + dy) for x, y in blocks]
            if any(not (0 <= y <= CELL_H - h and 0 <= x <= CELL_W - w) for x, y in cand):
                continue
            if not any(_touches(body_ink, x, y, w, h) for x, y in cand):
                return cand, size
    return blocks, (2, 2)                                # no room at all: keep them where they are (touching)


def all_forms():
    return [(ch, f) for ch, f in F.all_glyph_keys()]
