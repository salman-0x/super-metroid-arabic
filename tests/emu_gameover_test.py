"""Real-game test of the GAME OVER screen (game state $1A, forced after the file-select screen has been reached).
Runs the original and the Arabic ROM in Mesen 2 and checks on the BG1 tilemap the running game shows:
  1. every Arabic string (pointer/offset read back from the patched LDY/LDX operands) appears word for word at its row/column
  2. every cell outside the footprint of the original and of the new strings is identical to the original ROM's screen
  3. VRAM tiles hold the relocated tile blob (so the Arabic glyph tiles the strings reference are really there)
Usage: python tests/emu_gameover_test.py <original.sfc> <arabic.sfc>"""
import glob
import os
import struct
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from smar import gameover_ar as G  # noqa: E402
from smar import menu_ar as M  # noqa: E402
from smar.rom import Rom, pc  # noqa: E402

MESEN = glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\SourMesen.Mesen2*\Mesen.exe"))[0]


def run_forced(rom_path, outdir, state):
    src = open(os.path.join(ROOT, "tests", "force_state.lua"), encoding="utf-8").read()
    src = src.replace("C:/PLACEHOLDER/", outdir.replace("\\", "/") + "/").replace("local FORCED = 0x19", f"local FORCED = 0x{state:02X}")
    lua = os.path.join(outdir, "_run.lua")
    open(lua, "w", encoding="ascii").write(src)
    p = subprocess.Popen([MESEN, "--testRunner", rom_path, lua])
    try:
        p.wait(timeout=170)
    except subprocess.TimeoutExpired:
        p.kill()
        raise SystemExit("Mesen timed out")
    vram = open(os.path.join(outdir, "vram_s.bin"), "rb").read()
    st = {}
    for line in open(os.path.join(outdir, "state_s.txt"), encoding="utf-8", errors="replace"):
        if "=" in line:
            k, v = line.rstrip("\n").split("=", 1)
            st[k] = v
    mw = int(st["ppu.layers[0].tilemapAddress"])
    words = [struct.unpack_from("<H", vram, ((mw + k) * 2) % 0x10000)[0] for k in range(1024)]
    return words, vram


def read_words(rom, addr):
    out = []
    while True:
        w = struct.unpack_from("<H", rom.data, pc(G.BANK, addr))[0]
        if w == 0xFFFF:
            return out
        out.append(w)
        addr += 2


def cells(rom, addr, x):
    """{(row, col): word} a string drawn by $B3E2 at buffer offset x covers."""
    row, col = x // 0x40, (x % 0x40) // 2
    out, c, r = {}, col, row
    for w in read_words(rom, addr):
        if w == 0xFFFE:
            r, c = r + 1, col
            continue
        out[(r, c)] = w
        c += 1
    return out


def main():
    orig_path, ar_path = (os.path.abspath(p) for p in sys.argv[1:3])
    orig, ar = Rom.load(orig_path), Rom.load(ar_path)
    bad = 0

    def check(name, ok, detail=""):
        nonlocal bad
        bad += not ok
        print(f"  {'OK  ' if ok else 'FAIL'} {name}{(' - ' + detail) if detail and not ok else ''}")

    with tempfile.TemporaryDirectory() as td:
        for state in (0x19, 0x1A):                              # $19 leads into $1A: both end on the GAME OVER screen
            print(f"forced game state ${state:02X}")
            run_state(orig, ar, orig_path, ar_path, td, state, check)
    print("RESULT:", "ALL OK" if not bad else f"{bad} failing check(s)")
    return 1 if bad else 0


def run_state(orig, ar, orig_path, ar_path, td, state, check):
    res = {}
    for label, path in (("orig", orig_path), ("ar", ar_path)):
        d = os.path.join(td, f"{label}{state:02X}")
        os.makedirs(d)
        res[label] = run_forced(path, d, state)
    o_words, _ = res["orig"]
    a_words, a_vram = res["ar"]

    orig_cells, new_cells = {}, {}
    for name, (ldy, ldx, addr, x, kind, _) in G.ENTRIES.items():
        orig_cells.update(cells(orig, addr, x))
        nptr = struct.unpack_from("<H", ar.data, pc(G.BANK, ldy + 1))[0]
        nx = struct.unpack_from("<H", ar.data, pc(G.BANK, ldx + 1))[0]
        mine = cells(ar, nptr, nx)
        new_cells.update(mine)
        wrong = [(rc, w, a_words[rc[0] * 32 + rc[1]]) for rc, w in mine.items()
                 if (a_words[rc[0] * 32 + rc[1]] & 0x3FF) != (w & 0x3FF) or
                 ((w & 0x3FF) != G.SPACE and a_words[rc[0] * 32 + rc[1]] != w)]
        check(f"string {name!r} ({len(mine)} cells) is on screen word for word", not wrong, str(wrong[:5]))
    foot = set(orig_cells) | set(new_cells)
    diff = [(k // 32, k % 32, a_words[k], o_words[k]) for k in range(1024)
            if (k // 32, k % 32) not in foot and a_words[k] != o_words[k]]
    check("every cell outside the strings is identical to the original screen", not diff, str(diff[:6]))
    left_over = [rc for rc in orig_cells if rc not in new_cells and (a_words[rc[0] * 32 + rc[1]] & 0x3FF) != G.SPACE]
    check("no English word is left behind where the old strings were", not left_over, str(left_over[:6]))
    p = ar.read(pc(*M.LOADER), 8)
    size = p[6] | (p[7] << 8)
    blob = ar.read(pc(p[5], p[3] | (p[4] << 8)), size)
    check("VRAM tiles == relocated blob", a_vram[:size] == blob)


if __name__ == "__main__":
    sys.exit(main())
