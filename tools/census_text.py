"""Text census: how much English text the game has in each place, and how much of it the Arabic build replaces.
Unit = one non-blank character cell of the ORIGINAL English text (a letter, digit or punctuation mark; spaces and filler don't count).
Exact part: text stored as data we can read (message boxes, menu strings, option maps, intro pages, game-over, file dialogs).
Measured-by-eye part: text that is part of graphics (HUD, pause screens, title, credits) - counted from emulator screenshots, see
the comments below; the ending/credits volume is an ESTIMATE (it was only seen in part).
Usage: python tools/census_text.py"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from smar import gameover_ar as G  # noqa: E402
from smar import intro_ar as I  # noqa: E402
from smar import menu_ar as M  # noqa: E402
from smar import slot_ar as S  # noqa: E402

doc = json.load(open(os.path.join(ROOT, "data", "messages.json"), encoding="utf-8"))
tr = json.load(open(os.path.join(ROOT, "data", "translations_ar.json"), encoding="utf-8"))


def cells(text):
    return sum(1 for ch in text if ch not in " |~")


def words_cells(hexwords):
    return sum(1 for w in hexwords.split() if w not in ("FFFE", "FFFF") and (int(w, 16) & 0x3FF) != 0x0F)


rows = []     # (category, units, translated?, how known)
msg_units = sum(cells(line) for b in doc["blocks"] for line in b["text"])
msg_done = sum(cells(line) for b in doc["blocks"] if b["id"] in tr for line in b["text"])
rows.append(("message boxes (26 blocks)", msg_units, msg_done, "data"))

menu_small = sum(cells(t) for t in M.ENGLISH.values())
menu_big = sum(words_cells(h) // 2 for h in M.BIG_ORIGINAL_WORDS.values())
done_small = sum(cells(M.ENGLISH[int(a, 16)]) for a in tr["_menus"]["strings"])
done_big = sum(words_cells(M.BIG_ORIGINAL_WORDS[int(a, 16)]) // 2 for a in tr["_menus"]["big_strings"])
rows.append(("file-select strings + big titles", menu_small + menu_big, done_small + done_big, "data"))

opt = tr["_menus"]["options"]["slots"]
opt_units = sum(sum(1 for t in s.get("expect_top", s.get("expect", [])) if t not in ("00F", "000")) for s in opt)
rows.append(("OPTION MODE labels (5 screens)", opt_units, opt_units, "data (slots = every label found on the 5 maps)"))

go_units = sum(words_cells(e[5]) // (2 if e[4] != "small" else 1) for e in G.ENTRIES.values())
rows.append(("GAME OVER screen", go_units, go_units, "data"))
slot_units = sum(words_cells(e[4]) for e in S.ENTRIES.values())
rows.append(("(SAMUS _) dialogs", slot_units, slot_units, "data"))

intro_units = sum(d["cells"] for _, _, d in I.PAGES) + I.LAST_ENGLISH["cells"]
rows.append(("intro story (7 pages)", intro_units, intro_units, "data"))

# ---- text inside graphics / ending, counted from real emulator screenshots (analysis/game_*/shot_*.png)
# Letters only; spaces and punctuation are not counted, staff NAMES (about 100 proper names) are not counted because they stay as they are.
def letters(*texts):
    return sum(1 for t in texts for ch in t if ch.isalpha())


HUD = letters("ENERGY", "AUTO")                                                  # RESERVE/AUTO/ammo icons were not captured
AREAS = ("CRATERIA", "BRINSTAR", "NORFAIR", "WRECKED SHIP", "MARIDIA", "TOURIAN", "COLONY")
pause_map = letters(*AREAS, "L", "EXIT", "START", "SAMUS", "R")
pause_equip = letters("SUPPLY", "BEAM", "SUIT", "MISC", "BOOTS", "SAMUS", "MAP", "EXIT", "START", "L", "R")
# The title screen (logo, copyright line) is excluded by the user: a cosmetic extra, not counted.
title = 0               # logo + lines seen/known; the title screen was not captured whole
# The staff credits (role headings and names) are deliberately left out of the project: the user does not want them translated.
ending = 0   # the ending story lines (sprites) are excluded by the user, like the credits and the title screen
items = letters("VARIA SUIT", "GRAVITY SUIT", "MORPHING BALL", "BOMB", "SPRING BALL", "SCREW ATTACK", "CHARGE", "ICE", "WAVE", "SPAZER",
                "PLASMA", "HI-JUMP BOOTS", "SPACE JUMP", "SPEED BOOSTER")   # equipment-screen item names (14 strips of tiles)
reserve = letters("MODE", "AUTO", "RESERVE", "TANK")              # equipment screen reserve-tank box (the MANUAL value is the same slot)
planet = letters("PLANET", "ZEBES")                                # title of the save-load map screen (found with the all-items save test)
graphics = [("pause: equipment item names", items), ("HUD (energy etc.)", HUD), ("pause: map screen", pause_map), ("pause: equipment screen", pause_equip),
            ("pause: reserve-tank box", reserve), ("load map screen title", planet),
            ]

# graphics text translated by editing tile art in place (smar/pause_ar.py): the six equipment-screen labels
DONE_GFX = {"HUD (energy etc.)": HUD, "pause: equipment item names": items, "pause: reserve-tank box": reserve, "load map screen title": planet,
            "pause: equipment screen": letters("SUPPLY", "BEAM", "SUIT", "MISC", "BOOTS", "SAMUS", "MAP", "EXIT"),
            "pause: map screen": letters(*AREAS, "EXIT", "START", "SAMUS")}     # L and R are the names of the physical shoulder buttons: kept
done = sum(r[2] for r in rows) + sum(DONE_GFX.values())
known = sum(r[1] for r in rows)
gfx = sum(v for _, v in graphics)
print(f"{'category':38s} {'units':>6s} {'translated':>11s}")
for name, units, d, _ in rows:
    print(f"{name:38s} {units:6d} {d:11d}")
data_done = done - sum(DONE_GFX.values())
print(f"{'-- data subtotal':38s} {known:6d} {data_done:11d}")
for name, v in graphics:
    print(f"{name:38s} {v:6d} {DONE_GFX.get(name, 0):11d}")
total = known + gfx
print()
print(f"all counted units: {total}   translated: {done}   not translated: {total - done}")
print(f"SHARE TRANSLATED BY CHARACTER VOLUME: {done / total * 100:.1f}%")
print(f"share of the text stored as DATA that is translated: {data_done / known * 100:.1f}%")
