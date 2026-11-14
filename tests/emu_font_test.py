"""Runtime test: run the game's own BG3-font loader ($82:82E3, which DMAs $9A:B200 x $2000 bytes to VRAM $4000)
in Mesen 2 and check that VRAM really holds the font from the ROM, including the Arabic upper half.

Usage: python tests/emu_font_test.py <rom> [<rom> ...]
Exit code of the Lua probe: 2 = verified with Arabic data present, 1 = match but upper half empty (vanilla),
101..200 = mismatching bytes, 250 = script error, -1 = timeout.
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
from smar.rom import Rom, pc  # noqa: E402
from emu_message_test import find_mesen, STUB_ADDR  # noqa: E402

LUA = os.path.join(ROOT, "tests", "vram_probe.lua")
STUB = bytes([0x78, 0x18, 0xFB, 0xC2, 0x30, 0xA9, 0xFF, 0x1F, 0x1B, 0x4B, 0xAB,
              0x22, 0xE3, 0x82, 0x82,          # JSL $82:82E3  (game's font loader)
              0x80, 0xFE])                     # spin


def probe(mesen, src, tmpdir):
    rom = Rom.load(src)
    assert set(rom.read(pc(0x85, STUB_ADDR), len(STUB))) == {0xFF}
    rom.write(pc(0x85, STUB_ADDR), STUB)
    rom.write(pc(0x80, 0x841C), bytes([0x5C, STUB_ADDR & 0xFF, STUB_ADDR >> 8, 0x85]))
    path = os.path.join(tmpdir, "font_probe.sfc")
    rom.save(path)
    p = subprocess.Popen([mesen, "--testRunner", path, LUA])
    try:
        return p.wait(timeout=60)
    except subprocess.TimeoutExpired:
        p.kill()
        return -1


def main():
    mesen = find_mesen()
    bad = 0
    with tempfile.TemporaryDirectory() as td:
        for src in sys.argv[1:]:
            code = probe(mesen, src, td)
            meaning = {2: "VRAM == ROM font, Arabic tiles present", 1: "VRAM == ROM font (upper half empty)",
                       250: "script error", -1: "timeout"}.get(code, "VRAM differs from ROM" if code > 100 else "?")
            print(f"{os.path.basename(src):<16} exit={code:>4}  {meaning}")
            bad += code not in (1, 2)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
