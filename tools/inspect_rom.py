import sys, hashlib, zlib, struct

path = sys.argv[1]
rom = open(path, 'rb').read()
print("size:", len(rom), hex(len(rom)), "copier header:", len(rom) % 0x8000 == 0x200)

def show_header(base):
    h = rom[base:base+0x40]
    title = h[0:21].decode('ascii', 'replace')
    mapmode, romtype, romsize, sramsize, region, dev, ver = h[21:28]
    comp, chk = struct.unpack_from('<HH', h, 28)
    print(f"header @ {base:#x}: title={title!r} map={mapmode:#04x} type={romtype:#04x} "
          f"romsize={romsize:#x} ({1<<romsize} KB) sram={sramsize:#x} region={region:#x} dev={dev:#x} ver={ver}")
    print(f"  stored complement={comp:#06x} checksum={chk:#06x} sum={comp+chk:#06x}")
    reset = struct.unpack_from('<H', rom, base + 0x3C)[0]
    print(f"  emulation RESET vector = {reset:#06x}")
    return chk, comp

chk, comp = show_header(0x7FC0)

def snes_checksum(data):
    # standard algorithm: for non-power-of-two sizes mirror the remainder up to the next power of two
    size = len(data)
    p = 1
    while p * 2 <= size:
        p *= 2
    s = sum(data[:p])
    if size > p:
        rest = data[p:]
        rem = size - p
        s += sum(rest) * (p // rem)
    return s & 0xFFFF

# checksum computed with the header's checksum field as stored (it self-cancels: chk+comp=0xFFFF contributes 0x1FE)
calc = snes_checksum(rom)
print(f"computed checksum = {calc:#06x}  matches stored: {calc == chk}")

print("CRC32 :", f"{zlib.crc32(rom) & 0xFFFFFFFF:08X}")
print("MD5   :", hashlib.md5(rom).hexdigest())
print("SHA1  :", hashlib.sha1(rom).hexdigest())

# free space: trailing run of 0xFF (or 0x00) at the end of each 32KB LoROM bank
print("\nTrailing free runs per bank (LoROM bank = $80 + index):")
for b in range(len(rom) // 0x8000):
    chunk = rom[b*0x8000:(b+1)*0x8000]
    for fill in (0xFF, 0x00):
        n = len(chunk) - len(chunk.rstrip(bytes([fill])))
        if n >= 0x40:
            start = 0x8000 + 0x8000 - n
            print(f"  ${0x80+b:02X}:{start:04X}-$FFFF  {n:#7x} bytes ({n:6d})  fill={fill:#04x}  pc={b*0x8000 + 0x8000 - n:#08x}")
