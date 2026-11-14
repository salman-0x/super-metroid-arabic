"""A plain-text maker's mark inside the patched ROM (free space at $B7:FD00, never read by the game): visible in any hex editor."""
from .rom import RomError, pc

AT = (0xB7, 0xFD00)
TEXT = b"Super Metroid Arabic translation by Mr S - v1.0.0\x00"


def build(rom):
    if rom.read(pc(*AT), len(TEXT)) != b"\xFF" * len(TEXT):
        raise RomError("$B7:FD00 is not free for the credit text")
    rom.write(pc(*AT), TEXT)
    return {"at": AT, "length": len(TEXT)}


def changed_regions(info):
    return [(pc(*info["at"]), pc(*info["at"]) + info["length"])]
