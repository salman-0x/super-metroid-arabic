"""Super Metroid's graphics compression (the format read by $80:B0FF / $80:B271), clean-room from its documented layout.

Stream = sequence of commands, terminated by a byte 0xFF.
  header byte b:  cmd = b >> 5, len = (b & 0x1F) + 1
  if cmd == 7 (b >= 0xE0, extended): cmd = (b >> 2) & 7, len = (((b & 3) << 8) | next_byte) + 1
  cmd 0  direct copy: `len` literal bytes follow
  cmd 1  byte fill: one byte follows, written `len` times
  cmd 2  word fill: two bytes (lo, hi) follow, written alternately for `len` bytes
  cmd 3  incrementing fill: one byte follows; writes b, b+1, ... for `len` bytes
  cmd 4  absolute copy: 16-bit little-endian address into the OUTPUT buffer follows; copy `len` bytes from there
  cmd 5  same as 4 but every copied byte is XOR 0xFF
  cmd 6  relative copy: one byte follows; source = (current output position - that byte); copy `len` bytes
  cmd 7  same as 6 but XOR 0xFF
The compressor below only needs to be *correct* (decompress(compress(x)) == x), not optimal; it uses direct copies,
byte fills and word fills.
"""


class LzError(Exception):
    pass


def decompress(data, offset, max_out=0x10000):
    """-> (output bytes, offset just past the 0xFF terminator)."""
    out = bytearray()
    i = offset
    n = len(data)
    while True:
        if i >= n:
            raise LzError("ran off the end of the data")
        b = data[i]
        i += 1
        if b == 0xFF:
            return bytes(out), i
        cmd, ln = b >> 5, (b & 0x1F) + 1
        if cmd == 7:
            if i >= n:
                raise LzError("truncated extended header")
            cmd = (b >> 2) & 7
            ln = (((b & 3) << 8) | data[i]) + 1
            i += 1
        if cmd == 0:
            out += data[i:i + ln]
            i += ln
        elif cmd == 1:
            out += bytes([data[i]]) * ln
            i += 1
        elif cmd == 2:
            lo, hi = data[i], data[i + 1]
            i += 2
            out += bytes((lo, hi)[k & 1] for k in range(ln))
        elif cmd == 3:
            v = data[i]
            i += 1
            out += bytes((v + k) & 0xFF for k in range(ln))
        elif cmd in (4, 5):
            addr = data[i] | (data[i + 1] << 8)
            i += 2
            if addr + ln > len(out) and addr >= len(out):
                raise LzError("absolute copy from beyond the output")
            for k in range(ln):
                v = out[addr + k]
                out.append(v ^ 0xFF if cmd == 5 else v)
        else:  # 6, 7
            off = data[i]
            i += 1
            src = len(out) - off
            if src < 0:
                raise LzError("relative copy before start of output")
            for k in range(ln):
                v = out[src + k]
                out.append(v ^ 0xFF if cmd == 7 else v)
        if len(out) > max_out:
            raise LzError("output too large")


def _emit_direct(buf, chunk):
    for k in range(0, len(chunk), 1024):
        part = chunk[k:k + 1024]
        ln = len(part) - 1
        buf += bytes([0xE0 | (0 << 2) | (ln >> 8), ln & 0xFF]) if ln >= 32 else bytes([ln])
        buf += part


def compress(data: bytes) -> bytes:
    """Simple, always-correct compressor: runs become fills, everything else direct copies."""
    out = bytearray()
    lit = bytearray()
    i, n = 0, len(data)

    def flush():
        if lit:
            _emit_direct(out, bytes(lit))
            lit.clear()

    def header(cmd, ln):
        ln -= 1
        return bytes([(cmd << 5) | ln]) if ln < 32 else bytes([0xE0 | (cmd << 2) | (ln >> 8), ln & 0xFF])

    while i < n:
        # byte run
        j = i
        while j < n and data[j] == data[i] and j - i < 1024:
            j += 1
        if j - i >= 3:
            flush()
            out += header(1, j - i) + bytes([data[i]])
            i = j
            continue
        # word run (a b a b a b ...)
        if i + 5 < n and data[i] != data[i + 1]:
            j = i
            while j + 1 < n and data[j] == data[i + (j - i) % 2] and j - i < 1024:
                j += 1
            if j - i >= 6:
                flush()
                out += header(2, j - i) + bytes([data[i], data[i + 1]])
                i = j
                continue
        lit.append(data[i])
        i += 1
    flush()
    out.append(0xFF)
    return bytes(out)
