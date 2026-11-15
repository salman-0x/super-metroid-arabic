"""Test helper: copy a ROM and redirect its reset vector to a stub that fills RAM with an "all items" Samus (every beam,
every suit/boot/ball upgrade, grapple, x-ray, full tanks and ammo), starts her at the first Crateria save station and saves it
into slot A with the game's own save routine ($81:8000), then jumps to the original reset code.
The resulting SRAM (.srm) is a normal save file: it contains game data only, no ROM bytes.
Usage: python tools/make_save_full.py <in.sfc> <out.sfc>"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import pc  # noqa: E402

STUB_AT = 0xCD8E            # free run in bank $80 (12850 bytes of $FF in the original)

# RAM (bank $7E) -> 16-bit value
VALUES = {
    0x09A2: 0xF32F,   # equipped items: varia, spring ball, morph, screw, gravity, hi-jump, space jump, bombs, speed, grapple, x-ray
    0x09A4: 0xF32F,   # collected items (same set)
    0x09A6: 0x100F,   # equipped beams: wave, ice, spazer, plasma, charge
    0x09A8: 0x100F,   # collected beams
    0x09C0: 0x0001,   # reserve tank mode: auto
    0x09C2: 0x05DB,   # energy 1499
    0x09C4: 0x05DB,   # max energy 1499 (14 tanks + 99)
    0x09C6: 230, 0x09C8: 230,     # missiles
    0x09CA: 50, 0x09CC: 50,       # super missiles
    0x09CE: 50, 0x09D0: 50,       # power bombs
    0x09D2: 0x0001,   # selected item: missiles
    0x09D4: 400, 0x09D6: 400,     # reserve tanks
    0x079F: 0x0000,   # area: Crateria
    0x078B: 0x0000,   # load station: first one
    0xD914: 0x0005,   # story progress: past the Ceres intro (0 would restart the intro)
}


def make(src, dst):
    rom = bytearray(open(src, "rb").read())
    reset = rom[0x7FFC] | (rom[0x7FFD] << 8)
    if set(rom[pc(0x80, STUB_AT):pc(0x80, STUB_AT) + 200]) != {0xFF}:
        raise SystemExit("stub area is not free")
    code = bytearray([0x78, 0x18, 0xFB, 0xC2, 0x30, 0xA2, 0xFF, 0x1F, 0x9A])          # SEI CLC XCE REP #$30 LDX #$1FFF TXS
    for addr, val in VALUES.items():
        code += bytes([0xA9, val & 255, val >> 8, 0x8F, addr & 255, addr >> 8, 0x7E])   # LDA #val ; STA $7E:addr
    code += bytes([0xA9, 0x00, 0x00, 0x22, 0x00, 0x80, 0x81])                           # LDA #0 ; JSL $818000 (save slot A)
    code += bytes([0x5C, reset & 255, reset >> 8, 0x80])                                # JML original reset
    rom[pc(0x80, STUB_AT):pc(0x80, STUB_AT) + len(code)] = code
    rom[0x7FFC], rom[0x7FFD] = STUB_AT & 255, STUB_AT >> 8
    open(dst, "wb").write(rom)


if __name__ == "__main__":
    make(sys.argv[1], sys.argv[2])
    print("stub ROM written:", sys.argv[2])

