"""Summarise a trace.txt from tests/trace_writes.lua: distinct writer PCs with counts and frames, and the writes that put
specific tilemap bytes at given buffer addresses. Usage: python tools/analyze_trace.py <trace.txt> [addr_hex ...]"""
import re
import sys
from collections import Counter, defaultdict

rx = re.compile(r"(\d+) ([0-9A-F]{6}) a=([0-9A-F]{4}) x=([0-9A-F]{4}) y=([0-9A-F]{4}) d=([0-9A-F]{4}) dbr=([0-9A-F]{2}) "
                r"addr=([0-9A-F]{6}) val=([0-9A-F]{2})")
rows = []
for line in open(sys.argv[1]):
    m = rx.match(line)
    if m:
        f, pc, a, x, y, d, dbr, addr, val = m.groups()
        rows.append((int(f), pc, int(a, 16), int(x, 16), int(y, 16), int(d, 16), int(dbr, 16), int(addr, 16), int(val, 16)))
print(len(rows), "writes")
byp = defaultdict(list)
for r in rows:
    byp[r[1]].append(r)
print("writer PCs (count, frames, addr range):")
for pc, rs in sorted(byp.items(), key=lambda kv: -len(kv[1])):
    fr = sorted({r[0] for r in rs})
    ad = [r[7] for r in rs]
    print(f"  {pc}: {len(rs):5d} writes  frames {fr[0]}..{fr[-1]} ({len(fr)} distinct)  addr {min(ad):06X}-{max(ad):06X}")
for want in sys.argv[2:]:
    w = int(want, 16)
    print(f"writes to {w:06X}/{w + 1:06X}:")
    for r in rows:
        if r[7] in (w, w + 1):
            print(f"  frame {r[0]} pc {r[1]} a={r[2]:04X} x={r[3]:04X} y={r[4]:04X} d={r[5]:04X} dbr={r[6]:02X} addr={r[7]:06X} val={r[8]:02X}")
