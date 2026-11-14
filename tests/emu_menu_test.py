"""Runs the REAL game in Mesen 2 (needs Debug.ScriptWindow.AllowIoOsAccess) on the original and on the Arabic ROM,
dumps VRAM at the file-select screen (frame 620) and the option-mode screen (frame 745), and checks:
  1. VRAM word $0000.. equals the tile set the loader is supposed to send (original: $8E:8000 x 0x5600; Arabic: the
     relocated blob at $B8:8000, including the appended Arabic tiles)
  2. every BG1 file-select row that held an English string now holds exactly the Arabic words stored in the ROM
  3. rows that were not translated (the 16-px titles, SAMUS labels, TIME) are word-for-word identical to the original
  4. the OPTION MODE screen (other loaders) is identical in both runs: BG1 tilemap and VRAM tiles $000-$1FF
Usage: python tests/emu_menu_test.py <original.sfc> <arabic.sfc>"""
import glob
import os
import struct
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from smar import menu_ar as M  # noqa: E402
from smar.rom import Rom, pc  # noqa: E402

LUA_SRC = os.path.join(ROOT, "tests", "dump_screens.lua")


def run_game(rom_path, outdir):
    mesen = glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\SourMesen.Mesen2*\Mesen.exe"))[0]
    out = outdir.replace("\\", "/") + "/"
    lua = os.path.join(outdir, "_run.lua")
    with open(LUA_SRC, encoding="utf-8") as f:
        src = f.read().replace("C:/PLACEHOLDER/", out)
    with open(lua, "w", encoding="ascii") as f:
        f.write(src)
    p = subprocess.Popen([mesen, "--testRunner", rom_path, lua])
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


def bg1_rows(vram, st):
    mw = int(st["ppu.layers[0].tilemapAddress"])
    return [[struct.unpack_from("<H", vram, ((mw + r * 32 + c) * 2) % 0x10000)[0] for c in range(32)] for r in range(32)]


def find_seq(row, seq):
    n = len(seq)
    return [i for i in range(32 - n + 1) if row[i:i + n] == seq]


def main():
    orig_path, ar_path = (os.path.abspath(p) for p in sys.argv[1:3])
    ar = Rom.load(ar_path)
    orig = Rom.load(orig_path)
    bad = 0

    def check(name, ok, detail=""):
        nonlocal bad
        bad += not ok
        print(f"  {'OK  ' if ok else 'FAIL'} {name}{(' - ' + detail) if detail and not ok else ''}")

    with tempfile.TemporaryDirectory() as td:
        d_o, d_a = os.path.join(td, "o"), os.path.join(td, "a")
        os.makedirs(d_o), os.makedirs(d_a)
        # run fresh copies: Mesen keeps a battery file per ROM file name, and a slot created by earlier runs would change the screen
        import shutil
        fresh_o, fresh_a = os.path.join(td, "menu_orig.sfc"), os.path.join(td, "menu_ar.sfc")
        shutil.copyfile(orig_path, fresh_o)
        shutil.copyfile(ar_path, fresh_a)
        run_game(fresh_o, d_o)
        run_game(fresh_a, d_a)
        vo, so = load(d_o, "t")
        va, sa = load(d_a, "t")

        print("file-select screen")
        p = ar.read(pc(*M.LOADER), 8)
        size = p[6] | (p[7] << 8)
        blob = ar.read(pc(p[5], p[3] | (p[4] << 8)), size)
        check("Arabic ROM: VRAM tiles == relocated blob (incl. appended Arabic tiles)", va[:size] == blob,
              f"first diff at {next((i for i in range(size) if va[i] != blob[i]), None)}")
        check("original ROM (control): VRAM tiles == $8E:8000 x 0x5600", vo[:M.SRC_SIZE] == orig.read(pc(0x8E, 0x8000), M.SRC_SIZE))
        check("Arabic tiles are really non-empty in VRAM", any(va[M.SRC_SIZE:size]))

        ro, ra = bg1_rows(vo, so), bg1_rows(va, sa)
        # the strings as the game draws them: words from the ROM (leading/trailing padding words are matched too)
        screen = {6: 0xB4AC, 11: 0xB4AC, 16: 0xB4AC, 26: 0xB4EE}
        for row, addr in screen.items():
            eng = M.read_string(orig, addr)
            arb = M.read_string(ar, addr)
            core_e = [w for w in eng if (w & 0x3FF) != 0x0F]
            core_a = [w for w in arb if (w & 0x3FF) != 0x0F]
            check(f"row {row:2d}: original screen shows the English words of ${addr:04X}",
                  bool(find_seq(ro[row], core_e[:2])), f"{[hex(w) for w in ro[row]]}")
            # core Arabic words are contiguous-or-with-spaces; require each Arabic word to be present in order
            # tile ids only: the game recolours the highlighted slot row (palette bits change from run to run)
            pos, ok, ids = 0, True, [w & 0x3FF for w in ra[row]]
            for w in core_a:
                try:
                    pos = ids.index(w & 0x3FF, pos) + 1
                except ValueError:
                    ok = False
                    break
            check(f"row {row:2d}: Arabic screen shows the Arabic words of ${addr:04X} in order", ok, f"{[hex(w) for w in ra[row]]}")
            check(f"row {row:2d}: no English letters left on the row", not any(0x6A <= (w & 0x3FF) < 0x84 for w in ra[row]))

        # big (16-px) strings: (top row, bottom row) of the screen for each stored string
        big = {0xB40A: (1, 2), 0xB436: (5, 6), 0xB456: (10, 11), 0xB476: (15, 16)}
        def in_order(row, words):
            """words appear in `row` as a subsequence (duplicates allowed: the title uses the same glyph twice)."""
            pos = 0
            for w in words:
                try:
                    pos = row.index(w, pos) + 1
                except ValueError:
                    return False
            return True

        for addr, (rt, rb) in big.items():
            ow, aw = M.read_string(orig, addr), M.read_string(ar, addr)
            cut = ow.index(0xFFFE)
            o_top = [w for w in ow[:cut] if (w & 0x3FF) != 0x0F]
            a_top = [w for w in aw[:cut] if (w & 0x3FF) != 0x0F]
            a_bot = [w for w in aw[cut + 1:] if (w & 0x3FF) != 0x0F]
            check(f"big ${addr:04X} rows {rt}/{rb}: original screen shows the English big words",
                  bool(find_seq(ro[rt], o_top[:3])))
            check(f"big ${addr:04X} rows {rt}/{rb}: Arabic screen shows the Arabic top and bottom words in order",
                  in_order(ra[rt], a_top) and in_order(ra[rb], a_bot))
            english_tiles = {w & 0x3FF for w in ow if (w & 0x3FF) not in (0x0F, 0x3FE)}
            check(f"big ${addr:04X}: no English big-font tile left on those two rows",
                  not any((w & 0x3FF) in english_tiles for w in ra[rt] + ra[rb]))
        for r in (5, 10, 15):
            check(f"row {r:2d}: the TIME icon tiles are still there",
                  all(any((w & 0x3FF) == t for w in ra[r]) for t in (0xAD, 0xAE, 0xAF)))
        touched = set(screen) | {r for pair in big.values() for r in pair}
        untouched = [r for r in range(32) if r not in touched]
        same = all([w & 0x3FF for w in ro[r]] == [w & 0x3FF for w in ra[r]] for r in untouched)   # tile ids: palette bits are recoloured live
        check("all remaining BG1 rows identical to the original", same)

        vo2, so2 = load(d_o, "f")
        va2, sa2 = load(d_a, "f")
        print("option-mode screen (translated since the option maps were added: tests/emu_option_test.py checks its content)")
        check("original tiles $000-$2AF still identical in VRAM (only tiles from $2B0 on were added)",
              vo2[:0x5600] == va2[:0x5600])
        o_rows, a_rows = bg1_rows(vo2, so2), bg1_rows(va2, sa2)
        check("the option screen's icon/button/kanji tiles (ids < $0100 outside text rows) are untouched",
              all(o_rows[r] == a_rows[r] for r in (0, 3, 4, 5, 8, 9, 12, 15, 16, 19, 20, 23, 24, 27, 28, 29, 30, 31)))
    print("RESULT:", "ALL OK" if not bad else f"{bad} failing check(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
