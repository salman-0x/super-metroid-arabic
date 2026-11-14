"""Print the non-empty rows of a BG layer's tilemap from a Mesen dump, as hex tile ids with letters decoded
(tile $6A+n = letter, $0F = space). Usage: python tools/tilemap_rows.py <dump_dir> <tag> [layer=1]"""
import os
import struct
import sys

d, tag = sys.argv[1], sys.argv[2]
layer = int(sys.argv[3]) if len(sys.argv) > 3 else 1
vram = open(os.path.join(d, f"vram_{tag}.bin"), "rb").read()
st = {}
for line in open(os.path.join(d, f"state_{tag}.txt"), encoding="utf-8", errors="replace"):
    if "=" in line:
        k, v = line.rstrip("\n").split("=", 1)
        st[k] = v
mw = int(st[f"ppu.layers[{layer - 1}].tilemapAddress"])
for r in range(32):
    words = [struct.unpack_from("<H", vram, ((mw + r * 32 + c) * 2) % 0x10000)[0] for c in range(32)]
    if all((w & 0x3FF) in (0x00F, 0x00E, 0, 0x0A) for w in words):
        continue
    ids = " ".join(f"{w & 0x3FF:03X}" if (w & 0x3FF) not in (0x00F, 0) else " . " for w in words)
    txt = "".join(chr(65 + (w & 0x3FF) - 0x6A) if 0x6A <= (w & 0x3FF) < 0x6A + 26 else (" " if (w & 0x3FF) in (0x0F, 0) else "#") for w in words)
    attrs = sorted({w >> 10 for w in words if (w & 0x3FF) not in (0x0F, 0)})
    print(f"row {r:2d} attr={attrs}  |{txt}|")
    print(f"        {ids}")
