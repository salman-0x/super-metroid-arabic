"""How much of a VRAM region equals ROM data starting at a given address; and which VRAM tile ids are used by the BG
tilemaps of a dump. Usage: python tools/match_extent.py <rom> <dump_dir> <tag> <bank_hex> <addr_hex> [vram_word_hex=0]"""
import os
import struct
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import Rom, pc, snes

rom = Rom.load(sys.argv[1])
dump, tag = sys.argv[2], sys.argv[3]
bank, addr = int(sys.argv[4], 16), int(sys.argv[5], 16)
vword = int(sys.argv[6], 16) if len(sys.argv) > 6 else 0
vram = open(os.path.join(dump, f"vram_{tag}.bin"), "rb").read()
src = rom.data[pc(bank, addr):pc(bank, addr) + 0x10000]
vb = vword * 2
n = 0
while vb + n < 0x10000 and n < len(src) and vram[vb + n] == src[n]:
    n += 1
print(f"VRAM word ${vword:04X} equals ROM ${bank:02X}:{addr:04X} for {n:#x} bytes ({n / 32:.1f} 4bpp tiles)")
# resume matching after small mismatches, report matching spans of >= 0x100 bytes
spans, i = [], 0
while i < min(len(src), 0x10000 - vb):
    if vram[vb + i] == src[i]:
        j = i
        while j < min(len(src), 0x10000 - vb) and vram[vb + j] == src[j]:
            j += 1
        if j - i >= 0x100:
            spans.append((i, j))
        i = j
    else:
        i += 1
print("spans >= 0x100 bytes (offset ranges):", [(hex(a), hex(b)) for a, b in spans[:12]])

st = {}
for line in open(os.path.join(dump, f"state_{tag}.txt"), encoding="utf-8", errors="replace"):
    if "=" in line:
        k, v = line.rstrip("\n").split("=", 1)
        st[k] = v
for layer, w, h in ((0, 64, 32), (1, 32, 32), (2, 32, 32)):
    mw = int(st[f"ppu.layers[{layer}].tilemapAddress"])
    ids = set()
    for blk in range(w // 32):
        for k in range(32 * 32):
            ids.add(struct.unpack_from("<H", vram, ((mw + blk * 0x400 + k) * 2) % 0x10000)[0] & 0x3FF)
    ids = sorted(ids)
    print(f"BG{layer + 1} tilemap uses {len(ids)} tile ids; max {max(ids):#x}; ids >= 0x100: {[hex(t) for t in ids if t >= 0x100][:20]}")
