"""Tile census of the menu tile set ($8E:8000, 4bpp, 0x5600 bytes = 688 tiles):
which tile ids are all-zero in the ROM, and which ids the BG tilemaps of the given Mesen dumps reference.
Usage: python tools/census.py <rom> <dump_dir>:<tag> [<dump_dir>:<tag> ...]"""
import os
import struct
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import Rom, pc

rom = Rom.load(sys.argv[1])
base = pc(0x8E, 0x8000)
NT = 0x5600 // 32
tiles = [rom.data[base + i * 32: base + (i + 1) * 32] for i in range(NT)]
zero = [i for i, t in enumerate(tiles) if not any(t)]


def spans(ids):
    out, s, p = [], None, None
    for i in ids:
        if s is None:
            s = p = i
        elif i == p + 1:
            p = i
        else:
            out.append((s, p)); s = p = i
    if s is not None:
        out.append((s, p))
    return out


print(f"{NT} tiles; {len(zero)} all-zero tiles")
print("zero spans:", " ".join(f"{a:03X}-{b:03X}" if a != b else f"{a:03X}" for a, b in spans(zero)))

used = {}
for arg in sys.argv[2:]:
    d, tag = arg.rsplit(":", 1)
    vram = open(os.path.join(d, f"vram_{tag}.bin"), "rb").read()
    st = {}
    for line in open(os.path.join(d, f"state_{tag}.txt"), encoding="utf-8", errors="replace"):
        if "=" in line:
            k, v = line.rstrip("\n").split("=", 1)
            st[k] = v
    for layer in (0, 1, 2):
        wide = st[f"ppu.layers[{layer}].doubleWidth"] == "true"
        tall = st[f"ppu.layers[{layer}].doubleHeight"] == "true"
        mw = int(st[f"ppu.layers[{layer}].tilemapAddress"])
        blocks = (2 if wide else 1) * (2 if tall else 1)
        for blk in range(blocks):
            for k in range(1024):
                w = struct.unpack_from("<H", vram, ((mw + blk * 0x400 + k) * 2) % 0x10000)[0]
                if layer < 2:                          # BG1/BG2 use the 4bpp set
                    used.setdefault(w & 0x3FF, set()).add(tag)
used_ids = sorted(used)
print(f"tile ids referenced by BG1/BG2 tilemaps in the dumps: {len(used_ids)}")
print("  referenced spans:", " ".join(f"{a:03X}-{b:03X}" if a != b else f"{a:03X}" for a, b in spans(used_ids)))
free_zero = [i for i in zero if i not in used]
print(f"all-zero AND not referenced in the sampled screens: {len(free_zero)}")
print("  spans:", " ".join(f"{a:03X}-{b:03X}" if a != b else f"{a:03X}" for a, b in spans(free_zero)))
