"""Apply a BPS (or IPS) patch to a ROM and verify it.  Usage: python apply_patch.py <original.sfc> <patch.bps> <output.sfc>
Checks that the source is the expected headerless dump (SHA1) and that the result has the expected SHA1 and a valid SNES checksum."""
import hashlib
import sys
import zlib

SOURCE_SHA1 = "da957f0d63d14cb441d215462904c4fa8519c613"      # Super Metroid (Japan, USA) (En,Ja), headerless
RESULT_SHA1 = "27758c9ce3075411f10c34b1bb9a72f6145dc812"


def _dec(data, i):
    value, shift = 0, 1
    while True:
        x = data[i]
        i += 1
        value += (x & 0x7F) * shift
        if x & 0x80:
            return value, i
        shift <<= 7
        value += shift


def apply_bps(src, patch):
    if zlib.crc32(patch[:-4]).to_bytes(4, "little") != patch[-4:]:
        raise SystemExit("the patch file is damaged (CRC mismatch): download it again")
    i = 4
    ssize, i = _dec(patch, i)
    tsize, i = _dec(patch, i)
    msize, i = _dec(patch, i)
    i += msize
    if len(src) != ssize or zlib.crc32(src).to_bytes(4, "little") != patch[-12:-8]:
        raise SystemExit("this patch is for a different source ROM")
    out, srel, trel, end = bytearray(), 0, 0, len(patch) - 12
    while i < end:
        v, i = _dec(patch, i)
        mode, n = v & 3, (v >> 2) + 1
        if mode == 0:
            out += src[len(out):len(out) + n]
        elif mode == 1:
            out += patch[i:i + n]
            i += n
        else:
            d, i = _dec(patch, i)
            d = -(d >> 1) if d & 1 else d >> 1
            if mode == 2:
                srel += d
                out += src[srel:srel + n]
                srel += n
            else:
                trel += d
                for _ in range(n):
                    out.append(out[trel])
                    trel += 1
    if len(out) != tsize or zlib.crc32(bytes(out)).to_bytes(4, "little") != patch[-8:-4]:
        raise SystemExit("the result does not match the expected ROM")
    return bytes(out)


def apply_ips(rom, patch):
    if patch[:5] != b"PATCH":
        raise SystemExit("not an IPS file")
    rom, i = bytearray(rom), 5
    while patch[i:i + 3] != b"EOF":
        off = int.from_bytes(patch[i:i + 3], "big")
        size = int.from_bytes(patch[i + 3:i + 5], "big")
        i += 5
        if size == 0:
            run, val = int.from_bytes(patch[i:i + 2], "big"), patch[i + 2]
            rom[off:off + run] = bytes([val]) * run
            i += 3
        else:
            rom[off:off + size] = patch[i:i + size]
            i += size
    return bytes(rom)


def snes_checksum_ok(rom):
    """Internal SNES checksum (a non power-of-two size mirrors its tail up to the next power of two)."""
    data = bytearray(rom)
    data[0x7FDC:0x7FE0] = b"\xff\xff\x00\x00"
    p = 1
    while p * 2 <= len(data):
        p *= 2
    total = sum(data[:p]) + (sum(data[p:]) * (p // (len(data) - p)) if len(data) > p else 0)
    chk = int.from_bytes(rom[0x7FDE:0x7FE0], "little")
    return total & 0xFFFF == chk and int.from_bytes(rom[0x7FDC:0x7FDE], "little") ^ chk == 0xFFFF


def main():
    print("Super Metroid Arabic translation by Mr S")
    src, pat, dst = sys.argv[1:4]
    rom = open(src, "rb").read()
    if len(rom) % 0x8000 == 0x200:
        raise SystemExit("this ROM has a 512-byte copier header: remove it first (the patch is for the headerless dump)")
    got = hashlib.sha1(rom).hexdigest()
    if got != SOURCE_SHA1:
        raise SystemExit(f"wrong source ROM: SHA1 {got}\nexpected {SOURCE_SHA1} (Super Metroid (Japan, USA) (En,Ja), headerless .sfc)")
    data = open(pat, "rb").read()
    out = apply_bps(rom, data) if data[:4] == b"BPS1" else apply_ips(rom, data)
    sha = hashlib.sha1(out).hexdigest()
    open(dst, "wb").write(out)
    print(f"written {dst}\nSHA1 {sha}  {'OK' if sha == RESULT_SHA1 else 'UNEXPECTED (the patch was not applied as built)'}")
    print("SNES checksum:", "valid" if snes_checksum_ok(out) else "invalid")


if __name__ == "__main__":
    main()
