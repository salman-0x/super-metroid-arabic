"""Survey: find runs of 16-bit tilemap words that look like text: >= MINLEN consecutive words with the same
attribute (high) byte, tile (low) bytes inside a 0x30-wide window, with several distinct values.
Linear-time: first split into maximal same-high-byte segments, then walk each segment once.
Usage: python tools/scan_text.py <rom> [minlen]"""
import os
import sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import Rom, snes

rom = Rom.load(sys.argv[1])
MINLEN = int(sys.argv[2]) if len(sys.argv) > 2 else 8
d = rom.data
N = len(d)


def runs_for(parity):
    out = []
    i = parity
    while i + 1 < N:
        hi = d[i + 1]
        j = i
        while j + 1 < N and d[j + 1] == hi:
            j += 2
        seg_len = (j - i) // 2
        if hi not in (0x00, 0xFF) and seg_len >= MINLEN:
            # inside the segment, cut into windows of low bytes spanning <= 0x30
            k = i
            while k < j:
                lo_min = lo_max = d[k]
                vals = {d[k]}
                m = k + 2
                while m < j:
                    lo = d[m]
                    if max(lo_max, lo) - min(lo_min, lo) > 0x30:
                        break
                    lo_min, lo_max = min(lo_min, lo), max(lo_max, lo)
                    vals.add(lo)
                    m += 2
                length = (m - k) // 2
                if length >= MINLEN and len(vals) >= 5:
                    out.append((k, length, hi, lo_min, lo_max, len(vals)))
                k = m if m > k else k + 2
        i = j + 2 if j > i else i + 2
    return out


runs = sorted(runs_for(0) + runs_for(1))
bank_count = Counter(r[0] // 0x8000 for r in runs)
print("candidate runs per LoROM bank:")
print("  " + "  ".join(f"${0x80 + b:02X}:{c}" for b, c in sorted(bank_count.items())))
print()
shown = 0
for off, length, hi, lo_min, lo_max, nv in runs:
    a = 0x8000 + off % 0x8000
    if off // 0x8000 == 5 and 0x877F <= a < 0x9643:
        continue            # known message-box tilemaps
    words = [d[off + 2 * k] for k in range(length)]
    print(f"{snes(off)} len={length:3d} attr={hi:02X} tiles {lo_min:02X}-{lo_max:02X} distinct={nv:2d}  "
          + " ".join(f"{w:02X}" for w in words[:18]))
    shown += 1
print("\nshown:", shown)
