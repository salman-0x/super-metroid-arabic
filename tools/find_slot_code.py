"""Find code in bank $81 that adds a letter base to a slot index (ADC #$006A / ADC #$000A etc.) and print context."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar.rom import Rom, pc

rom = Rom.load(sys.argv[1])
bank = rom.read(pc(0x81, 0x8000), 0x8000)
for name, pat in (("ADC #$006A", bytes([0x69, 0x6A, 0x00])), ("ADC #$000A", bytes([0x69, 0x0A, 0x00])),
                  ("ORA #$206A", bytes([0x09, 0x6A, 0x20])), ("ADC #$206A", bytes([0x69, 0x6A, 0x20])),
                  ("ADC #$200A", bytes([0x69, 0x0A, 0x20])), ("ORA #$200A", bytes([0x09, 0x0A, 0x20])),
                  ("ADC #$001A", bytes([0x69, 0x1A, 0x00])), ("ADC #$201A", bytes([0x69, 0x1A, 0x20]))):
    i, hits = bank.find(pat), []
    while i != -1:
        hits.append(i)
        i = bank.find(pat, i + 1)
    print(f"{name}: {len(hits)} hits")
    for h in hits[:8]:
        print(f"   $81:{0x8000 + h:04X}  " + " ".join(f"{b:02X}" for b in bank[max(0, h - 14):h + 12]))
