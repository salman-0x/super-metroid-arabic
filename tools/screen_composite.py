"""Composite the visible 256x224 area of BG2, BG1 (4bpp) and BG3 (2bpp) from a Mesen dump into one screenshot-like PNG.
Back-to-front: BG2, BG1, BG3 (colour 0 is transparent). Approximation of the real screen: ignores priority bits and windows.
Usage: python tools/screen_composite.py <dump_dir> <tag> <out.png> [scale]"""
import os
import subprocess
import sys
from PIL import Image

d, tag, out = sys.argv[1], sys.argv[2], sys.argv[3]
SC = int(sys.argv[4]) if len(sys.argv) > 4 else 3
tmp = os.path.join(os.path.dirname(out), f"_layers_{tag}")
here = os.path.dirname(os.path.abspath(__file__))
subprocess.run([sys.executable, os.path.join(here, "vram_view.py"), d, tag, tmp, "1"], check=True, stdout=subprocess.DEVNULL)
base = Image.new("RGB", (256, 224), (0, 0, 0))
# only layers enabled on the main screen (ppu.mainScreenLayers: bit0 BG1, bit1 BG2, bit2 BG3, bit3 BG4, bit4 OBJ)
enabled = 0
for line in open(os.path.join(d, f"state_{tag}.txt"), encoding="utf-8", errors="replace"):
    if line.startswith("ppu.mainScreenLayers="):
        enabled = int(line.split("=", 1)[1])
print("main-screen layer mask:", bin(enabled), "(sprites are not drawn by this tool)")
for layer in (2, 1, 3):
    if not enabled & (1 << (layer - 1)):
        continue
    im = Image.open(f"{tmp}_bg{layer}.png").convert("RGB").crop((0, 0, 256, 224))
    mask = im.convert("L").point(lambda v: 255 if v > 0 else 0)
    base.paste(im, (0, 0), mask)
base = base.resize((256 * SC, 224 * SC), Image.NEAREST)
base.save(out)
for layer in (1, 2, 3):
    os.remove(f"{tmp}_bg{layer}.png")
print("wrote", out, base.size)
