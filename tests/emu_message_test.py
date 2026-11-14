"""Runtime test: execute the game's own message-tilemap routine ($85:8241) inside Mesen 2 and compare
the WRAM buffer it produces for ROM A vs ROM B, for every message id.

Usage: python tests/emu_message_test.py base/original.sfc build/relocated.sfc [--control]
The reset vector of a *temporary copy* is redirected to a stub; the ROMs under test are never modified.
"""
import glob
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from smar.rom import Rom, pc  # noqa: E402
from smar import messages as M  # noqa: E402

STUB_ADDR = 0xF000  # $85:F000, free space in every build we make (data ends well before it)
LUA = os.path.join(ROOT, "tests", "wram_probe.lua")


def find_mesen():
    hits = glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\SourMesen.Mesen2*\Mesen.exe"))
    if not hits:
        raise SystemExit("Mesen.exe not found")
    return hits[0]


def stub(index: int) -> bytes:
    return bytes([
        0x78,                      # SEI
        0x18, 0xFB,                # CLC; XCE        (native mode)
        0xC2, 0x30,                # REP #$30
        0xA9, 0xFF, 0x1F, 0x1B,    # LDA #$1FFF; TCS
        0x4B, 0xAB,                # PHK; PLB        (DB = $85)
        0xA9, index & 0xFF, 0x00,  # LDA #index
        0x8D, 0x1F, 0x1C,          # STA $1C1F
        0x20, 0xC3, 0x82,          # JSR $82C3       (body of game's tilemap-copy routine $85:82B8;
                                   #                 skips its leading JSL hardware pre-ops)
        0x80, 0xFE,                # BRA *           (spin)
    ])


def make_test_rom(src: str, index: int, dst: str):
    rom = Rom.load(src)
    free = rom.read(pc(0x85, STUB_ADDR), 0x20)
    assert set(free) == {0xFF}, "stub area is not free"
    rom.write(pc(0x85, STUB_ADDR), stub(index))
    rom.write(pc(0x80, 0x841C), bytes([0x5C, STUB_ADDR & 0xFF, STUB_ADDR >> 8, 0x85]))  # JML $85:F000 at reset
    rom.save(dst)


def run_one(mesen, src, index, tmpdir, lua=LUA):
    rom_path = os.path.join(tmpdir, f"t_{os.path.basename(src)}_{index}.sfc")
    make_test_rom(src, index, rom_path)
    p = subprocess.Popen([mesen, "--testRunner", rom_path, lua])
    try:
        return p.wait(timeout=60)
    except subprocess.TimeoutExpired:
        p.kill()
        return -1


# Entries the vanilla game can never display: tools/callers.py finds no call site with these ids, and the game
# computes a copy length from the *next* table word -> $93BF-$957F = $FE40 (id $1B) and $012A-$94BF = $6C6B
# (id $1D, the word after the table is not a pointer). Their output is undefined garbage, so it is
# expected to differ when the data moves.
NOT_DISPLAYABLE = {0x1B: "end marker; vanilla size wraps to $FE40", 0x1D: "last entry; size read past table"}


def compare(mesen, a, b, td, ids):
    results = {}
    for idx in ids:
        results[idx] = (run_one(mesen, a, idx, td), run_one(mesen, b, idx, td))
    return results


def make_control(src, dst, kind):
    rom = Rom.load(src)
    if kind == "zeroed-data":                      # new tilemap data wiped
        rom.write(pc(0x85, M.FREE_START), bytes(0x400))
    elif kind == "bad-pointer":                    # msg $05's tilemap pointer off by one row
        a = M.TABLE + 4 * 6 + 4
        rom.set_word(0x85, a, rom.word(0x85, a) + 0x40)
    rom.save(dst)


def main():
    a, b = sys.argv[1], sys.argv[2]
    mesen = find_mesen()
    bad = 0
    ids = [i for i in range(1, M.ENTRY_COUNT + 1) if i not in NOT_DISPLAYABLE]
    with tempfile.TemporaryDirectory() as td:
        res = compare(mesen, a, b, td, ids)
        for idx, (ra, rb) in res.items():
            ok = ra == rb and ra >= 1000
            bad += not ok
            print(f"msg {idx:#04x}: A={ra:>11} B={rb:>11}  {'OK' if ok else '*** MISMATCH/ERROR ***'}")
        for idx, why in NOT_DISPLAYABLE.items():
            print(f"msg {idx:#04x}: SKIPPED ({why})")
        print("RESULT:", "ALL DISPLAYABLE MESSAGES MATCH" if not bad else f"{bad} problem(s)")

        if "--control" in sys.argv:                # negative controls: the test must FAIL on broken ROMs
            for kind in ("zeroed-data", "bad-pointer"):
                broken = os.path.join(td, f"control_{kind}.sfc")
                make_control(b, broken, kind)
                cres = compare(mesen, a, broken, td, ids)
                diff = [i for i, (x, y) in cres.items() if x != y]
                print(f"control '{kind}': detected {len(diff)} mismatching message(s): "
                      f"{[hex(i) for i in diff]}  -> {'DETECTED' if diff else '*** NOT DETECTED ***'}")
                bad += not diff
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
