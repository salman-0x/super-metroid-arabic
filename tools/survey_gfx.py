"""Decompress every graphics blob whose source address appears as constants before a JSL $80:B0FF, validate it, and
report size / where the stream ends. Pattern before the call:  A9 00 bb 85 48 | A9 ll hh 85 47 | 22 FF B0 80 .
Usage: python tools/survey_gfx.py <rom>"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import Rom, snes, pc
from smar import sm_lz

rom = Rom.load(sys.argv[1])
d = rom.data
pat = bytes([0x22, 0xFF, 0xB0, 0x80])
seen, bad = {}, 0
i = d.find(pat)
while i != -1:
    w = d[i - 10:i]
    if w[0] == 0xA9 and w[1] == 0x00 and w[3] == 0x85 and w[4] == 0x48 and w[5] == 0xA9 and w[8] == 0x85 and w[9] == 0x47:
        bank = w[2]
        addr = w[6] | (w[7] << 8)
        dest = d[i + 4:i + 7]
        try:
            out, end = sm_lz.decompress(d, pc(bank, addr))
            seen.setdefault((bank, addr), (len(out), end - pc(bank, addr), dest.hex(), snes(i)))
        except Exception as e:           # noqa: BLE001
            bad += 1
            print("FAIL", f"${bank:02X}:{addr:04X}", e)
    i = d.find(pat, i + 1)
print(f"{len(seen)} distinct constant-source blobs decompressed OK, {bad} failures")
for (bank, addr), (osz, csz, dest, site) in sorted(seen.items()):
    print(f"  src ${bank:02X}:{addr:04X}  compressed {csz:5d} B -> {osz:5d} B  dest(inline) {dest[4:6]}{dest[2:4]}{dest[0:2]}  from {site}")
