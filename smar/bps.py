"""BPS patches (byuu's format): a patch refers to the SOURCE ROM for everything that is unchanged or merely moved (SourceRead/SourceCopy)
instead of embedding copies of it, so it carries only the new data.  make(source, target) -> bytes;  apply(source, patch) -> target."""
import zlib

MIN_COPY = 24          # shortest SourceCopy worth emitting
KEY = 16               # bytes hashed to find candidate copies


def _enc(n):
    out = bytearray()
    while True:
        x = n & 0x7F
        n >>= 7
        if n == 0:
            out.append(0x80 | x)
            return bytes(out)
        out.append(x)
        n -= 1


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


def make(src, tgt):
    index = {}
    for p in range(0, len(src) - KEY, 8):
        index.setdefault(src[p:p + KEY], p)
    out = bytearray(b"BPS1") + _enc(len(src)) + _enc(len(tgt)) + _enc(0)
    lit, o, rel = bytearray(), 0, 0

    def flush():
        if lit:
            out.extend(_enc(((len(lit) - 1) << 2) | 1))
            out.extend(lit)
            lit.clear()

    while o < len(tgt):
        n = 0
        while o + n < len(tgt) and o + n < len(src) and src[o + n] == tgt[o + n]:
            n += 1
        if n >= 8:
            flush()
            out.extend(_enc(((n - 1) << 2) | 0))
            o += n
            continue
        p = index.get(tgt[o:o + KEY]) if o + KEY <= len(tgt) else None
        if p is not None:
            m = KEY
            while o + m < len(tgt) and p + m < len(src) and src[p + m] == tgt[o + m]:
                m += 1
            if m >= MIN_COPY:
                flush()
                delta = p - rel
                out.extend(_enc(((m - 1) << 2) | 2))
                out.extend(_enc((abs(delta) << 1) | (1 if delta < 0 else 0)))
                rel = p + m
                o += m
                continue
        lit.append(tgt[o])
        o += 1
    flush()
    out += zlib.crc32(src).to_bytes(4, "little") + zlib.crc32(tgt).to_bytes(4, "little")
    out += zlib.crc32(bytes(out)).to_bytes(4, "little")
    return bytes(out)


def apply(src, patch):
    if patch[:4] != b"BPS1":
        raise ValueError("not a BPS patch")
    if zlib.crc32(patch[:-4]).to_bytes(4, "little") != patch[-4:]:
        raise ValueError("the patch file is damaged (CRC mismatch)")
    i = 4
    ssize, i = _dec(patch, i)
    tsize, i = _dec(patch, i)
    msize, i = _dec(patch, i)
    i += msize
    if len(src) != ssize or zlib.crc32(src).to_bytes(4, "little") != patch[-12:-8]:
        raise ValueError("this patch is for a different source ROM")
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
        raise ValueError("the result does not match the expected ROM")
    return bytes(out)


if __name__ == "__main__":
    import sys
    a, b = open(sys.argv[1], "rb").read(), open(sys.argv[2], "rb").read()
    patch = make(a, b)
    assert apply(a, patch) == b
    open(sys.argv[3], "wb").write(patch)
    print(f"{sys.argv[3]}: {len(patch)} bytes")
