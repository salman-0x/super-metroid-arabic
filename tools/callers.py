"""Find JSL $85:8080 (display message box) call sites and the immediate loaded into A just before,
and any 16-bit references to the YES/NO rows after the end marker ($85:957F-$9642)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import Rom, snes, pc

rom = Rom.load(sys.argv[1])
d = rom.data
pat = bytes([0x22, 0x80, 0x80, 0x85])
i, ids, unknown = d.find(pat), {}, []
while i != -1:
    # typical: A9 xx 00 (LDA #imm16) immediately before; sometimes via other instructions
    if i >= 3 and d[i - 3] == 0xA9 and d[i - 1] == 0x00:
        ids.setdefault(d[i - 2], []).append(snes(i))
    else:
        unknown.append((snes(i), d[max(0, i - 8):i].hex(" ")))
    i = d.find(pat, i + 1)
print("JSL $858080 callers with constant A:")
for k in sorted(ids):
    print(f"  msg {k:#04x}: {ids[k]}")
print("callers where A is not a plain immediate:")
for a, ctx in unknown:
    print(f"  {a}  preceding bytes: {ctx}")

print("\nsame-bank/other references to the YES/NO rows (addresses $9581,$95C1,$9601 and $957F..$9642 range):")
bank = d[pc(0x85, 0x8000):pc(0x85, 0x8000) + 0x8000]
for target in range(0x957F, 0x9643):
    lo, hi = target & 0xFF, target >> 8
    j = bank.find(bytes([lo, hi]))
    while j != -1:
        a = 0x8000 + j
        if not (0x869B <= a < 0x8749) and a < 0x957F:   # skip the table and the data itself
            print(f"  ${target:04X} found at $85:{a:04X}  ctx: {bank[max(0, j - 3):j + 4].hex(' ')}")
        j = bank.find(bytes([lo, hi]), j + 1)
