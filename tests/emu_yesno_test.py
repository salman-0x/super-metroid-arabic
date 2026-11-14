"""Runtime test of the YES/NO prompt: run the game's own cursor-toggle copy loop ($85:8510) in Mesen 2 and compare the
64 bytes it puts into WRAM $7E:3300 with the row we intended (B = YES selected, C = NO selected).

The game picks the row from the value in A:  A == 2 -> row C ($85:9601), otherwise row B ($85:95C1).
Usage: python tests/emu_yesno_test.py <original.sfc> <arabic.sfc> <messages.json> <translations.json>
Controls: on the ORIGINAL rom the expected bytes are the original rows (proves the harness reads the right place).
"""
import json
import os
import struct
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
from smar.rom import Rom, pc  # noqa: E402
from smar import translate as T  # noqa: E402
from emu_message_test import find_mesen, STUB_ADDR  # noqa: E402

LUA = os.path.join(ROOT, "tests", "wram_row.lua")


def stub(a_value):
    return bytes([0x78, 0x18, 0xFB, 0xC2, 0x30, 0xA9, 0xFF, 0x1F, 0x1B,
                  0x4B, 0xAB,                                   # PHK; PLB  -> DB = $85
                  0xA9, a_value & 0xFF, a_value >> 8,           # LDA #a_value
                  0x20, 0x10, 0x85,                             # JSR $8510 (choose row, copy 0x20 words to $7E3300)
                  0x80, 0xFE])


def lua_hash(data: bytes) -> int:
    h = 5381
    for b in data:
        h = (h * 33 + b) % 2147483647
    return h + 1000 if h < 1000 else h


def run(mesen, src, a_value, td):
    rom = Rom.load(src)
    assert set(rom.read(pc(0x85, STUB_ADDR), 32)) == {0xFF}
    rom.write(pc(0x85, STUB_ADDR), stub(a_value))
    rom.write(pc(0x80, 0x841C), bytes([0x5C, STUB_ADDR & 0xFF, STUB_ADDR >> 8, 0x85]))
    path = os.path.join(td, "yn.sfc")
    rom.save(path)
    p = subprocess.Popen([mesen, "--testRunner", path, LUA])
    try:
        return p.wait(timeout=60)
    except subprocess.TimeoutExpired:
        p.kill()
        return -1


def rows_from_rom(path):
    rom = Rom.load(path)
    return {k: rom.read(pc(0x85, a), 64) for k, a in T.YESNO_ROWS.items()}


def main():
    orig, arabic, jpath, tpath = sys.argv[1:5]
    doc = json.load(open(jpath, encoding="utf-8"))
    tr = json.load(open(tpath, encoding="utf-8"))
    yn = T.apply_translations(doc, tr)["yes_no_rows"]
    want_ar = {k: struct.pack("<32H", *v) for k, v in yn.items()}
    want_en = rows_from_rom(orig)
    mesen = find_mesen()
    bad = 0
    with tempfile.TemporaryDirectory() as td:
        for label, path, want in (("original", orig, want_en), ("arabic", arabic, want_ar)):
            for a_value, key in ((0, "B"), (2, "C")):
                got = run(mesen, path, a_value, td)
                exp = lua_hash(want[key])
                ok = got == exp
                bad += not ok
                print(f"{label:<9} A={a_value} -> row {key}: got {got:>11} expected {exp:>11}  {'OK' if ok else '*** MISMATCH ***'}")
        # the two rows must differ from each other (otherwise the test could not tell them apart)
        assert want_ar["B"] != want_ar["C"] and want_en["B"] != want_en["C"]
        assert want_ar["B"] != want_en["B"] and want_ar["C"] != want_en["C"]
    print("RESULT:", "ALL OK" if not bad else f"{bad} mismatch(es)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
