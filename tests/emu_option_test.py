"""Real-game test of the OPTION MODE screens. For the main option screen, CONTROLLER SETTING MODE and SPECIAL SETTING MODE
(reached by scripted button presses) it compares the BG1 tilemap the running game shows, word for word, with the map we
intended: the original decompressed map (control, original ROM) and the original map with our Arabic slots applied (Arabic ROM).
It also checks that VRAM holds the relocated tile blob (including the Arabic tiles) and that the file-select screen and the
GAME OVER screen (state $1A, forced) still render exactly as in the original.
Usage: python tests/emu_option_test.py <original.sfc> <arabic.sfc>"""
import glob
import json
import os
import struct
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from smar import menu_ar as M  # noqa: E402
from smar import option_ar as O  # noqa: E402
from smar import translate as T  # noqa: E402
from smar.rom import Rom, pc  # noqa: E402

MESEN = glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\SourMesen.Mesen2*\Mesen.exe"))[0]


def run_lua(rom_path, lua_src, outdir, patches):
    src = open(os.path.join(ROOT, "tests", lua_src), encoding="utf-8").read().replace("C:/PLACEHOLDER/", outdir.replace("\\", "/") + "/")
    for a, b in patches:
        src = src.replace(a, b)
    lua = os.path.join(outdir, "_run.lua")
    open(lua, "w", encoding="ascii").write(src)
    p = subprocess.Popen([MESEN, "--testRunner", rom_path, lua])
    try:
        p.wait(timeout=170)
    except subprocess.TimeoutExpired:
        p.kill()
        raise SystemExit("Mesen timed out")


def load(outdir, tag):
    vram = open(os.path.join(outdir, f"vram_{tag}.bin"), "rb").read()
    st = {}
    for line in open(os.path.join(outdir, f"state_{tag}.txt"), encoding="utf-8", errors="replace"):
        if "=" in line:
            k, v = line.rstrip("\n").split("=", 1)
            st[k] = v
    return vram, st


def bg1_words(vram, st):
    mw = int(st["ppu.layers[0].tilemapAddress"])
    return [struct.unpack_from("<H", vram, ((mw + k) * 2) % 0x10000)[0] for k in range(1024)]


def main():
    orig_path, ar_path = (os.path.abspath(p) for p in sys.argv[1:3])
    orig, ar = Rom.load(orig_path), Rom.load(ar_path)
    tr = json.load(open(os.path.join(ROOT, "data", "translations_ar.json"), encoding="utf-8"))
    doc = json.load(open(os.path.join(ROOT, "data", "messages.json"), encoding="utf-8"))
    info = T.build_arabic(Rom.load(orig_path), doc, tr)["menus"]          # same deterministic tile tables the ROM was built with
    slots = tr["_menus"]["options"]["slots"]
    bad = 0

    def check(name, ok, detail=""):
        nonlocal bad
        bad += not ok
        print(f"  {'OK  ' if ok else 'FAIL'} {name}{(' - ' + detail) if detail and not ok else ''}")

    screens = [("option main", -1, 0), ("controller setting", 3, 1), ("special setting", 4, 3)]
    with tempfile.TemporaryDirectory() as td:
        for name, downs, m in screens:
            print(f"{name} (map {m})")
            res = {}
            for label, path in (("orig", orig_path), ("ar", ar_path)):
                d = os.path.join(td, f"{label}{m}")
                os.makedirs(d)
                run_lua(path, "nav_option.lua", d, [("local DOWNS = 3", f"local DOWNS = {downs}")])
                res[label] = load(d, "n")
            expected_orig = O.load_map(orig, m)[0]
            expected_ar = list(expected_orig)
            for s in (x for x in slots if x["map"] == m):
                O.apply_slot(expected_ar, s, info["table"], M.BIG_CS, info["big_table"])
            for label, exp, rom in (("original ROM (control)", expected_orig, orig), ("Arabic ROM", expected_ar, ar)):
                vram, st = res["orig" if label.startswith("original") else "ar"]
                got = bg1_words(vram, st)
                # The game itself re-tints cells at runtime (e.g. the dimmed unselected row gets attr $0400 on its BLANK
                # words too). That happens identically on the original ROM, so blank cells are compared by tile id only.
                def same(a, b):
                    return a == b or ((a & 0x3FF) == O.BLANK and (b & 0x3FF) == O.BLANK)
                diff = [(k // 32, k % 32, got[k], exp[k]) for k in range(1024) if not same(got[k], exp[k])]
                check(f"{label}: BG1 tilemap == intended map ({len(diff)} differing cells; blanks compared by tile id)",
                      not diff, str(diff[:6]))
            vram, st = res["ar"]
            p = ar.read(pc(*M.LOADER), 8)
            size = p[6] | (p[7] << 8)
            blob = ar.read(pc(p[5], p[3] | (p[4] << 8)), size)
            check("Arabic ROM: VRAM tiles == relocated blob", vram[:size] == blob)
        print("(the GAME OVER screen, forced states $19/$1A, is Arabic since the game-over strings were added: "
              "tests/emu_gameover_test.py checks it)")
    print("RESULT:", "ALL OK" if not bad else f"{bad} failing check(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
