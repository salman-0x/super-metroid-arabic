import sys
rom = open(sys.argv[1], 'rb').read()
def pc(bank, addr): return ((bank & 0x7F) * 0x8000) + (addr - 0x8000)
def snes(off): return f"${0x80 + off // 0x8000:02X}:{0x8000 + off % 0x8000:04X}"

# region after font: is $9A:C200-$9A:D1FF really empty?
seg = rom[pc(0x9A, 0xC200):pc(0x9A, 0xD200)]
print("$9A:C200-$D1FF zero bytes:", seg.count(0), "/", len(seg))

# bytes between end of message tilemaps and start of the free run
o = pc(0x85, 0x957F)
print("$85:957F..$9642:")
for a in range(0x957F, 0x9643, 16):
    o = pc(0x85, a); n = min(16, 0x9643 - a)
    print(f"  $85:{a:04X} " + ' '.join(f"{b:02X}" for b in rom[o:o+n]))

# references to the font long address $9A:B200 and to the message table $85:869B
for name, pat in [("long $9A:B200", bytes([0x00, 0xB2, 0x9A])),
                  ("word $B200", bytes([0x00, 0xB2])),
                  ("table $869B (+4: $869F)", bytes([0x9F, 0x86])),
                  ("table $869B", bytes([0x9B, 0x86]))]:
    hits = []
    i = rom.find(pat)
    while i != -1:
        hits.append(i); i = rom.find(pat, i + 1)
    if name.startswith("word"):
        hits = [h for h in hits if h // 0x8000 in (0x00, 0x05, 0x02, 0x1A)]
    if name.startswith("table"):
        hits = [h for h in hits if h // 0x8000 == 0x05]
    print(f"{name}: {len(hits)} hits")
    for h in hits[:20]:
        ctx = rom[h-4:h+6]
        print(f"   {snes(h)} pc={h:#08x}  ctx: " + ' '.join(f"{b:02X}" for b in ctx))
