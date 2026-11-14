"""Write the translation review files: every Arabic text of the project next to its English original.
Usage: python tools/make_review.py <out_dir>      (needs data/messages.json made by `python smar_cli.py extract`)
Outputs <out_dir>/TRANSLATION_REVIEW.md (readable) and <out_dir>/translations_review.csv (UTF-8 with BOM, opens in Excel/Sheets)."""
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from smar import gameover_ar as G  # noqa: E402
from smar import intro_ar as I  # noqa: E402
from smar import menu_ar as M  # noqa: E402

with open(os.path.join(ROOT, "data", "translations_ar.json"), encoding="utf-8") as f:
    TR = json.load(f)
with open(os.path.join(ROOT, "data", "messages.json"), encoding="utf-8") as f:
    DOC = json.load(f)

rows = []          # (section, where, english, arabic, note)


def add(section, where, en, ar, note=""):
    rows.append((section, where, en, ar, note))


def clean(line):
    return " ".join(line.replace("|", " ").replace("·", " ").split())


# 1. message boxes ($85 table): line 0 is the title, other lines are sentences (some contain icons/buttons)
for b in DOC["blocks"]:
    tr = TR.get(b["id"], {})
    title_en = clean(b["text"][0])
    for k, v in tr.items():
        text = v["text"] if isinstance(v, dict) else v
        raw = clean(b["text"][int(k)]) if int(k) < len(b["text"]) else ""
        en = raw if sum(c.isalpha() for c in raw) >= 8 else "(sentence drawn with icon/button tiles: see the in-game text)"
        add("رسائل الصناديق / Message boxes", f"{b['id']} line {k}", en if k != "0" else title_en, text,
            "" if k == "0" else f"block: {title_en}")

# 2. file-select strings
for a, v in TR["_menus"]["strings"].items():
    add("قوائم الملفات / File select", f"${a}", M.ENGLISH[int(a, 16)].strip(), v)
for a, v in TR["_menus"]["big_strings"].items():
    add("عناوين كبيرة / Big titles", f"${a}", M.BIG_ENGLISH[int(a, 16)], v)
add("نعم/لا / Yes-No", "YES", "YES", TR["_yes_no"]["yes"])
add("نعم/لا / Yes-No", "NO", "NO", TR["_yes_no"]["no"])

# 3. option mode (English labels are only tile pairs in the ROM; see the screenshots for the originals)
for s in TR["_menus"]["options"]["slots"]:
    add("OPTION MODE", f"map {s['map']} row {s['row']} ({s['kind']})", "(see screenshot of the original screen)", s["text"])

# 4. game over and the (SAMUS _) dialogs
GO_EN = {"title": "GAME OVER", "find": "FIND THE METROID LARVA!", "again": "TRY AGAIN ?", "yes_big": "YES", "yes_small": "(RETURN TO GAME)",
         "no_big": "NO", "no_small": "(GO TO TITLE)"}
for k, v in TR["_menus"]["game_over"].items():
    add("GAME OVER", k, GO_EN[k], v)
SL_EN = {"copy_from": "COPY (SAMUS _) TO WHERE?", "copy_both": "COPY (SAMUS _) TO (SAMUS _).", "clear": "CLEAR (SAMUS _)."}
for k, v in TR["_menus"]["slot_dialogs"].items():
    add("حوارات الملفات / File dialogs", k, SL_EN[k], v + "   ( # = file letter أ/ب/ج )")

# 5. intro
for i, (page, ar) in enumerate(zip(I.PAGES, TR["_intro"]["pages"]), 1):
    add("المقدمة / Intro story", f"page {i}", "(original text: see the game)", " ".join(ar))
add("المقدمة / Intro story", "first white page", "(original text: see the game)", " ".join(TR["_intro"]["last"]))

# 6. pause screens, HUD, areas
PAUSE_EN = {"title": "SAMUS (equipment title)", "supply": "SUPPLY", "beam": "BEAM", "suit": "SUIT", "misc": "MISC.", "boots": "BOOTS",
            "map": "MAP (button)", "samus_btn": "SAMUS (button)", "start": "START (button)", "exit": "EXIT (button)",
            "item_varia": "VARIA (SUIT)", "item_suit": "(VARIA/GRAVITY) SUIT", "item_gravity": "GRAVITY (SUIT)", "item_morph": "MORPHING BALL",
            "item_bomb": "BOMB", "item_spring": "SPRING BALL", "item_screw": "SCREW ATTACK", "item_charge": "CHARGE", "item_ice": "ICE",
            "item_wave": "WAVE", "item_spazer": "SPAZER", "item_plasma": "PLASMA", "item_hijump": "HI-JUMP BOOTS",
            "item_space": "SPACE JUMP", "item_speed": "SPEED BOOSTER"}
for k, v in TR["_pause"].items():
    add("شاشة التوقف / Pause screens", k, PAUSE_EN[k], v)
for k, v in TR["_hud"].items():
    add("الواجهة / HUD", k, k.upper(), v)
for k, v in TR["_areas"].items():
    add("أسماء المناطق / Area names", k, k, v)

with open(os.path.join(sys.argv[1], "translations_review.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["section", "where", "english", "arabic", "note", "your correction"])
    for r in rows:
        w.writerow(list(r) + [""])

with open(os.path.join(sys.argv[1], "TRANSLATION_REVIEW.md"), "w", encoding="utf-8") as f:
    f.write("# مراجعة الترجمة / Translation review\n\n")
    f.write("كل النصوص العربية في التعريب مع أصلها الإنجليزي. اكتب تصحيحك بجانب أي سطر وأرسله (أو افتح Issue).\n")
    f.write("Every Arabic text of the patch next to its English original. Add your correction next to any line.\n\n")
    f.write(f"عدد النصوص / entries: **{len(rows)}**\n")
    section = None
    for sec, where, en, ar, note in rows:
        if sec != section:
            f.write(f"\n## {sec}\n\n| where | English | العربية | note |\n|---|---|---|---|\n")
            section = sec
        f.write(f"| {where} | {en} | {ar} | {note} |\n")
print(len(rows), "entries ->", sys.argv[1])
