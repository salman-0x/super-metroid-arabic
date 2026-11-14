import sys, struct
rom = open(sys.argv[1], 'rb').read()
def pc(bank, addr):  # LoROM
    return ((bank & 0x7F) * 0x8000) + (addr - 0x8000)
def w(bank, addr):
    return struct.unpack_from('<H', rom, pc(bank, addr))[0]

# hexdump around the suspected message-definition table
start = 0x8690
for a in range(start, start + 0xC0, 16):
    o = pc(0x85, a)
    print(f"$85:{a:04X}  " + ' '.join(f"{b:02X}" for b in rom[o:o+16]))

print("\nCandidate table @ $85:869B (6-byte entries):")
a = 0x869B
entries = []
for i in range(40):
    p1, p2, p3 = w(0x85, a), w(0x85, a + 2), w(0x85, a + 4)
    if not (0x8000 <= p1 < 0x9643 and 0x8000 <= p2 < 0x9643 and 0x8000 <= p3 < 0x9643):
        print(f"  stop at entry {i:#04x} ($85:{a:04X}): {p1:04X} {p2:04X} {p3:04X}")
        break
    entries.append((i, p1, p2, p3))
    print(f"  msg {i+1:#04x}: setup=${p1:04X} modify=${p2:04X} tilemap=${p3:04X}")
    a += 6
