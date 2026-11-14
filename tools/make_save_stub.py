"""Test helper: copy a ROM and redirect its reset vector to a tiny stub that first writes three valid (all-zero state) save
slots to SRAM with the game's own save routine ($81:8000, A = slot) and then jumps to the original reset code.  The game then
boots with slots A, B and C present, so the file-select COPY/CLEAR dialogs that name a slot can be reached in the emulator.
Usage: python tools/make_save_stub.py <in.sfc> <out.sfc>"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import pc  # noqa: E402

STUB_AT = 0xCD8E                                   # free run in bank $80 (12850 bytes of $FF in the original)


def make(src, dst):
    rom = bytearray(open(src, "rb").read())
    reset = rom[0x7FFC] | (rom[0x7FFD] << 8)
    if set(rom[pc(0x80, STUB_AT):pc(0x80, STUB_AT) + 40]) != {0xFF}:
        raise SystemExit("stub area is not free")
    code = bytearray([0x78, 0x18, 0xFB, 0xC2, 0x30, 0xA2, 0xFF, 0x1F, 0x9A])          # SEI CLC XCE REP #$30 LDX #$1FFF TXS
    for slot in (0, 1, 2):
        code += bytes([0xA9, slot, 0x00, 0x22, 0x00, 0x80, 0x81])                       # LDA #slot ; JSL $818000
    code += bytes([0x5C, reset & 255, reset >> 8, 0x80])                                # JML original reset
    rom[pc(0x80, STUB_AT):pc(0x80, STUB_AT) + len(code)] = code
    rom[0x7FFC], rom[0x7FFD] = STUB_AT & 255, STUB_AT >> 8
    open(dst, "wb").write(rom)


if __name__ == "__main__":
    make(sys.argv[1], sys.argv[2])
    print("stub ROM written:", sys.argv[2])
