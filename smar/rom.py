"""LoROM image access, header and internal checksum handling for Super Metroid (headerless .sfc)."""
import hashlib
import struct

# Known-good dump: Super Metroid (Japan, USA) (En,Ja), headerless, 3 MB
ORIGINAL_SHA1 = "da957f0d63d14cb441d215462904c4fa8519c613"

HEADER = 0x7FC0          # LoROM internal header (PC offset)
CHK_COMPLEMENT = 0x7FDC  # 16-bit checksum complement
CHK_VALUE = 0x7FDE       # 16-bit checksum
BANK_SIZE = 0x8000


class RomError(Exception):
    pass


def pc(bank: int, addr: int) -> int:
    """SNES LoROM address -> file offset. Accepts $00-$7D / $80-$FF mirrors, addr $8000-$FFFF."""
    if not 0x8000 <= addr <= 0xFFFF:
        raise RomError(f"address ${bank:02X}:{addr:04X} is not in the ROM half of a LoROM bank")
    return (bank & 0x7F) * BANK_SIZE + (addr - 0x8000)


def snes(offset: int) -> str:
    return f"${0x80 + offset // BANK_SIZE:02X}:{0x8000 + offset % BANK_SIZE:04X}"


def snes_checksum(data: bytes) -> int:
    """Standard SNES checksum: sum of all bytes; a non power-of-two tail is mirrored up to the next power of two."""
    size = len(data)
    p = 1
    while p * 2 <= size:
        p *= 2
    total = sum(data[:p])
    if size > p:
        rem = size - p
        if p % rem:
            raise RomError(f"unsupported ROM size {size:#x}")
        total += sum(data[p:]) * (p // rem)
    return total & 0xFFFF


class Rom:
    def __init__(self, data: bytes):
        if len(data) % BANK_SIZE == 0x200:
            raise RomError("ROM has a 512-byte copier header; strip it first")
        if len(data) % BANK_SIZE:
            raise RomError(f"ROM size {len(data):#x} is not a multiple of a LoROM bank")
        self.data = bytearray(data)
        self.writes = []  # (offset, length) of every write, for audit/diff reports

    @classmethod
    def load(cls, path):
        with open(path, "rb") as f:
            return cls(f.read())

    def save(self, path):
        with open(path, "wb") as f:
            f.write(self.data)

    def sha1(self) -> str:
        return hashlib.sha1(self.data).hexdigest()

    # ---- raw access -------------------------------------------------
    def read(self, offset, length) -> bytes:
        if offset < 0 or offset + length > len(self.data):
            raise RomError(f"read out of range {offset:#x}+{length:#x}")
        return bytes(self.data[offset:offset + length])

    def write(self, offset, payload: bytes):
        if offset < 0 or offset + len(payload) > len(self.data):
            raise RomError(f"write out of range {offset:#x}+{len(payload):#x}")
        self.data[offset:offset + len(payload)] = payload
        self.writes.append((offset, len(payload)))

    def word(self, bank, addr) -> int:
        return struct.unpack_from("<H", self.data, pc(bank, addr))[0]

    def set_word(self, bank, addr, value):
        if not 0 <= value <= 0xFFFF:
            raise RomError(f"word value {value:#x} out of range")
        self.write(pc(bank, addr), struct.pack("<H", value))

    def write_in_bank(self, bank, addr, payload: bytes):
        """Write that must not cross the end of the LoROM bank (16-bit pointers can't follow it)."""
        if addr + len(payload) > 0x10000:
            raise RomError(f"write ${bank:02X}:{addr:04X}+{len(payload):#x} crosses the bank boundary")
        self.write(pc(bank, addr), payload)

    # ---- header / checksum ------------------------------------------
    def title(self) -> str:
        return self.read(HEADER, 21).decode("ascii", "replace")

    def stored_checksum(self):
        comp, chk = struct.unpack_from("<HH", self.data, CHK_COMPLEMENT)
        return chk, comp

    def compute_checksum(self) -> int:
        """Checksum as it should be once the header fields are consistent (chk + comp == 0xFFFF)."""
        tmp = bytearray(self.data)
        struct.pack_into("<HH", tmp, CHK_COMPLEMENT, 0xFFFF, 0x0000)
        return snes_checksum(tmp)

    def fix_checksum(self):
        chk = self.compute_checksum()
        struct.pack_into("<HH", self.data, CHK_COMPLEMENT, chk ^ 0xFFFF, chk)
        self.writes.append((CHK_COMPLEMENT, 4))
        return chk

    def checksum_ok(self) -> bool:
        chk, comp = self.stored_checksum()
        return chk ^ comp == 0xFFFF and snes_checksum(self.data) == chk


def diff_ranges(a: bytes, b: bytes):
    """Contiguous ranges [start, end) where two equal-size images differ."""
    if len(a) != len(b):
        raise RomError("size mismatch")
    out, start = [], None
    for i in range(len(a)):
        if a[i] != b[i]:
            if start is None:
                start = i
        elif start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(a)))
    return out
