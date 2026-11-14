"""Find the option-mode BG1 tilemap rows inside a full WRAM dump (wramfull_<tag>.bin): the 32-word rows of the VRAM tilemap
are searched in WRAM as contiguous 16-bit words. Usage: python tools/find_in_wram.py <dump_dir> <tag>"""
import os
import struct
import sys

dump, tag = sys.argv[1], sys.argv[2]
vram = open(os.path.join(dump, f"vram_{tag}.bin"), "rb").read()
wram = open(os.path.join(dump, f"wramfull_{tag}.bin"), "rb").read()
st = {}
for line in open(os.path.join(dump, f"state_{tag}.txt"), encoding="utf-8", errors="replace"):
    if "=" in line:
        k, v = line.rstrip("\n").split("=", 1)
        st[k] = v
mw = int(st["ppu.layers[0].tilemapAddress"])
print("BG1 tilemap at VRAM word", hex(mw))
for r in range(32):
    words = [struct.unpack_from("<H", vram, ((mw + r * 32 + c) * 2) % 0x10000)[0] for c in range(32)]
    nb = [c for c, w in enumerate(words) if (w & 0x3FF) not in (0x00F, 0x00E, 0)]
    if not nb:
        continue
    span = words[nb[0]:nb[-1] + 1]
    pat = struct.pack(f"<{len(span)}H", *span)
    hits, i = [], wram.find(pat)
    while i != -1:
        hits.append(f"${0x7E + i // 0x10000:02X}:{i % 0x10000:04X}")
        i = wram.find(pat, i + 1)
    print(f"row {r:2d} cols {nb[0]:2d}-{nb[-1]:2d}: {hits[:6] if hits else 'not in WRAM as a contiguous run'}")
# whole-tilemap match: is the 64-word 2-row structure copied as one buffer?
full = b"".join(struct.pack("<32H", *[struct.unpack_from("<H", vram, ((mw + r * 32 + c) * 2) % 0x10000)[0] for c in range(32)]) for r in range(8))
i = wram.find(full)
print("first 8 tilemap rows as one buffer:", f"${0x7E + i // 0x10000:02X}:{i % 0x10000:04X}" if i >= 0 else "not found")
