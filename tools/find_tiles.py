"""Find where VRAM tiles of a Mesen dump come from in the ROM.
1. take N 4bpp tiles starting at <first_tile> from the dump's VRAM (chr word 0)
2. search (a) every constant-source blob the game decompresses, (b) the raw ROM bytes
Usage: python tools/find_tiles.py <rom> <dump_dir> <tag> <first_tile_hex> [count=26] [chr_word_hex=0] [bytes_per_tile=32]"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import Rom, pc, snes
from smar import sm_lz

rom = Rom.load(sys.argv[1])
dump, tag = sys.argv[2], sys.argv[3]
first = int(sys.argv[4], 16)
count = int(sys.argv[5]) if len(sys.argv) > 5 else 26
chr_word = int(sys.argv[6], 16) if len(sys.argv) > 6 else 0
tsz = int(sys.argv[7]) if len(sys.argv) > 7 else 32
vram = open(os.path.join(dump, f"vram_{tag}.bin"), "rb").read()
start = (chr_word + first * (tsz // 2)) * 2
want = vram[start:start + count * tsz]
needle = want[:tsz]
print(f"needle = tile ${first:03X} at VRAM byte {start:#06x}; first 32 bytes: {needle.hex()}")

# (b) raw ROM
raw = rom.data.find(needle)
print("raw ROM hit:", snes(raw) if raw >= 0 else None)

# (a) decompressed constant-source blobs
d = rom.data
pat = bytes([0x22, 0xFF, 0xB0, 0x80])
i, seen = d.find(pat), set()
found = False
while i != -1:
    w = d[i - 10:i]
    if w[0] == 0xA9 and w[1] == 0 and w[3] == 0x85 and w[4] == 0x48 and w[5] == 0xA9 and w[8] == 0x85 and w[9] == 0x47:
        key = (w[2], w[6] | (w[7] << 8))
        if key not in seen:
            seen.add(key)
            blob, _ = sm_lz.decompress(d, pc(*key))
            k = blob.find(needle)
            if k >= 0:
                full = blob[k:k + count * tsz] == want
                print(f"  blob ${key[0]:02X}:{key[1]:04X} (size {len(blob):#x}) contains tile at offset {k:#x}; all {count} tiles match: {full}")
                found = True
    i = d.find(pat, i + 1)
print("found in a constant-source blob:", found)
