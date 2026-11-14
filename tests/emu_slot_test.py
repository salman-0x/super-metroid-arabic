"""Real-game test of the "(SAMUS _)" dialogs of the file-select screen.
tools/make_save_stub.py makes copies of both ROMs that first write three valid save slots, so the game's own menus offer
SAMUS A/B/C.  A scripted run (tests/nav_slot.lua) reaches
  * DATA COPY -> slot A -> slot C   : "COPY (SAMUS A) TO WHERE?" then "COPY (SAMUS A) TO (SAMUS C)." + IS THIS OK?
  * DATA CLEAR -> slot A            : "CLEAR (SAMUS A)." + IS THIS OK?
and the test compares the BG1 tilemap the running game shows with what the patched ROM says it should: the dialog string words, the
file letters the code writes into the placeholder cells (first tile of the three Arabic letters + 0/2/0 for A/C/A), and that no
English word is left where the original dialog was.
Usage: python tests/emu_slot_test.py <original.sfc> <arabic.sfc>"""
import glob
import os
import struct
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from smar import slot_ar as S  # noqa: E402
from smar.rom import Rom, pc  # noqa: E402
import make_save_stub  # noqa: E402

MESEN = glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\SourMesen.Mesen2*\Mesen.exe"))[0]
COPY_PLAN = "add(20,'down') add(50,'down') add(80,'down') add(120,'a') add(220,'a') add(320,'down') add(360,'a')"
CLEAR_PLAN = "add(20,'down') add(50,'down') add(80,'down') add(110,'down') add(150,'a') add(250,'a')"


def run_nav(rom_path, outdir, plan, dump_at, last):
    src = open(os.path.join(ROOT, "tests", "nav_slot.lua"), encoding="utf-8").read()
    src = src.replace("C:/PLACEHOLDER/", outdir.replace("\\", "/") + "/").replace("local LAST = 600", f"local LAST = {last}")
    src = src.replace("--@@PLAN@@", plan + f"\ndumps[{dump_at}] = 'x'")
    lua = os.path.join(outdir, "_run.lua")
    open(lua, "w", encoding="ascii").write(src)
    p = subprocess.Popen([MESEN, "--testRunner", rom_path, lua])
    try:
        p.wait(timeout=250)
    except subprocess.TimeoutExpired:
        p.kill()
        raise SystemExit("Mesen timed out")
    vram = open(os.path.join(outdir, "vram_x.bin"), "rb").read()
    st = {}
    for line in open(os.path.join(outdir, "state_x.txt"), encoding="utf-8", errors="replace"):
        if "=" in line:
            k, v = line.rstrip("\n").split("=", 1)
            st[k] = v
    mw = int(st["ppu.layers[0].tilemapAddress"])
    return [struct.unpack_from("<H", vram, ((mw + k) * 2) % 0x10000)[0] for k in range(1024)]


def main():
    orig_path, ar_path = (os.path.abspath(p) for p in sys.argv[1:3])
    ar = Rom.load(ar_path)
    bad = 0

    def check(name, ok, detail=""):
        nonlocal bad
        bad += not ok
        print(f"  {'OK  ' if ok else 'FAIL'} {name}{(' - ' + detail) if detail and not ok else ''}")

    with tempfile.TemporaryDirectory() as td:
        stubs = {}
        for label, path in (("orig", orig_path), ("ar", ar_path)):
            stubs[label] = os.path.join(td, f"{label}_stub.sfc")
            make_save_stub.make(path, stubs[label])
        cases = [("copy_from", "COPY ... TO WHERE?", COPY_PLAN, 300, 310, [0]),
                 ("copy_both", "COPY ... TO ...", COPY_PLAN, 420, 430, [0, 2]),
                 ("clear", "CLEAR ...", CLEAR_PLAN, 330, 340, [0])]
        for name, title, plan, dump_at, last, letters in cases:
            print(f"dialog {name!r}: {title}")
            screens = {}
            for label in ("orig", "ar"):
                d = os.path.join(td, f"{label}_{name}")
                os.makedirs(d)
                screens[label] = run_nav(stubs[label], d, plan, dump_at, last)
            ldy, ldx, addr, x, hexwords, sites = S.ENTRIES[name]
            ptr = struct.unpack_from("<H", ar.data, pc(S.BANK, ldy + 1))[0]
            nx = struct.unpack_from("<H", ar.data, pc(S.BANK, ldx + 1))[0]
            words = S._read_words(ar, ptr)
            row, col = nx // 0x40, (nx % 0x40) // 2
            holes = []
            for adc, sta, _ in sites:
                holes.append(struct.unpack_from("<H", ar.data, pc(S.BANK, sta + 1))[0])
            base = struct.unpack_from("<H", ar.data, pc(S.BANK, sites[0][0] + 1))[0]
            hole_cells = {((h - S.BUFFER) // 2 // 32, ((h - S.BUFFER) // 2) % 32) for h in holes}
            got = screens["ar"]
            wrong = []
            for k, w in enumerate(words):
                rc = (row, col + k)
                if rc in hole_cells:
                    continue
                g = got[rc[0] * 32 + rc[1]]
                if (g & 0x3FF) != (w & 0x3FF) or ((w & 0x3FF) != S.SPACE and g != w):
                    wrong.append((rc, w, g))
            check(f"Arabic string ({len(words)} cells) is on screen word for word", not wrong, str(wrong[:5]))
            bad_letters = []
            for (adc, sta, _), hole, letter in zip(sites, holes, letters):
                r, c = ((hole - S.BUFFER) // 2) // 32, ((hole - S.BUFFER) // 2) % 32
                want = (base & 0x3FF) + letter
                if (got[r * 32 + c] & 0x3FF) != want:
                    bad_letters.append(((r, c), got[r * 32 + c] & 0x3FF, want))
            check("file letters (Arabic أ/ب/ج) sit in the placeholder cells", not bad_letters, str(bad_letters))
            orig_row, orig_col = x // 0x40, (x % 0x40) // 2
            new_cells = {(row, col + k) for k in range(len(words))}
            left = [(orig_row, orig_col + k) for k in range(len(hexwords.split()))
                    if (orig_row, orig_col + k) not in new_cells and (got[orig_row * 32 + orig_col + k] & 0x3FF) != S.SPACE]
            check("no English word is left where the original dialog was", not left, str(left[:6]))
            # the original screen shows the English dialog at the original place (control: the navigation really got there)
            ow = screens["orig"]
            owords = [int(w, 16) for w in hexwords.split()]
            old_cells = {(((off - S.BUFFER) // 2) // 32, ((off - S.BUFFER) // 2) % 32) for _a, _s, off in sites}
            diff = [k for k in range(len(owords)) if (orig_row, orig_col + k) not in old_cells and
                    (ow[orig_row * 32 + orig_col + k] & 0x3FF) != (owords[k] & 0x3FF)]
            check("control: the original ROM shows its English dialog at the original place (letter cells excluded)", not diff,
                  str(diff[:6]))
    print("RESULT:", "ALL OK" if not bad else f"{bad} failing check(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
