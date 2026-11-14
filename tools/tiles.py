import sys, struct, zlib
rom = open(sys.argv[1], 'rb').read()
def pc(bank, addr): return ((bank & 0x7F) * 0x8000) + (addr - 0x8000)

# 1) decode message tilemaps (word = vhopppcc cccccccc)
tbl = pc(0x85, 0x869B)
ptrs = [struct.unpack_from('<H', rom, tbl + 6*i + 4)[0] for i in range(0x1D)]
used = set()
for i in range(0x1C):
    a, b = ptrs[i], ptrs[i+1]
    if b <= a:
        print(f"msg {i+1:#04x} ${a:04X} -> next ptr ${b:04X} (<= own): sentinel / end-of-data marker, skipped")
        continue
    words = struct.unpack_from(f'<{(b-a)//2}H', rom, pc(0x85, a))
    print(f"msg {i+1:#04x} ${a:04X} len={b-a:#x} ({(b-a)//64} rows)")
    for r in range(0, len(words), 32):
        row = words[r:r+32]
        print('   ' + ' '.join(f"{x & 0x3FF:03X}" for x in row))
        for x in row: used.add(x & 0x3FF)
    attrs = sorted({x & 0xFC00 for x in words})
    print('   attrs:', [f"{x:04X}" for x in attrs])
print("distinct tile ids used:", len(used), sorted(f"{t:03X}" for t in used))

# 2) render 2bpp tiles from a given PC offset to PNG (16 tiles/row, x4, grid labels in filename only)
def render(off, count, out, scale=4):
    cols = 16; rows = (count + cols - 1) // cols
    W, H = cols * 8 * scale, rows * 8 * scale
    pal = [(0, 0, 0), (90, 90, 90), (170, 170, 170), (255, 255, 255)]
    img = [[(40, 0, 40)] * W for _ in range(H)]
    for t in range(count):
        base = off + t * 16
        if base + 16 > len(rom): break
        tx, ty = (t % cols) * 8, (t // cols) * 8
        for y in range(8):
            p0, p1 = rom[base + 2*y], rom[base + 2*y + 1]
            for x in range(8):
                c = ((p0 >> (7-x)) & 1) | (((p1 >> (7-x)) & 1) << 1)
                for sy in range(scale):
                    for sx in range(scale):
                        # leave 1px grid gap
                        if sx == scale-1 or sy == scale-1:
                            pass
                        img[(ty+y)*scale+sy][(tx+x)*scale+sx] = pal[c]
    raw = b''.join(b'\x00' + bytes(v for px in row for v in px) for row in img)
    def chunk(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xFFFFFFFF)
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0)) \
        + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')
    open(out, 'wb').write(png)
    print("wrote", out, f"{count} tiles from pc {off:#x}")

if len(sys.argv) > 2:
    render(int(sys.argv[2], 16), int(sys.argv[3], 16), sys.argv[4])
