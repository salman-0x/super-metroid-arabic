"""Make an IPS patch from an original ROM and a patched ROM (same size).  Usage: python tools/make_ips.py <original> <patched> <out.ips>
Differing ranges closer than MERGE bytes are joined; records are at most 0xFFFF bytes; runs of one repeated byte use the IPS RLE record."""
import sys

MERGE = 8


def ranges(a, b):
    out, i, n = [], 0, len(a)
    while i < n:
        if a[i] == b[i]:
            i += 1
            continue
        start, last = i, i
        while i < n and (a[i] != b[i] or i - last <= MERGE):
            if a[i] != b[i]:
                last = i
            i += 1
        out.append((start, last + 1))
    return out


def make(a, b):
    if len(a) != len(b):
        raise SystemExit("the ROMs must have the same size")
    assert len(a) < 0x454F46, "an IPS offset that spells EOF would end the patch early; use a different format for ROMs this large"
    out = bytearray(b"PATCH")
    for s, e in ranges(a, b):
        while s < e:
            n = min(e - s, 0xFFFF)
            data = b[s:s + n]
            if n >= 8 and len(set(data)) == 1:
                out += s.to_bytes(3, "big") + b"\x00\x00" + n.to_bytes(2, "big") + data[:1]
            else:
                out += s.to_bytes(3, "big") + n.to_bytes(2, "big") + data
            s += n
    return bytes(out + b"EOF")


if __name__ == "__main__":
    a, b = open(sys.argv[1], "rb").read(), open(sys.argv[2], "rb").read()
    patch = make(a, b)
    open(sys.argv[3], "wb").write(patch)
    print(f"{sys.argv[3]}: {len(patch)} bytes, {len(ranges(a, b))} ranges")
