"""Message-box tilemaps in bank $85.

Table $85:869B: 6-byte entries (setup routine, modify routine, tilemap pointer), indexed by message id - 1.
The game computes a message's tilemap size as  [entry(id+1).tilemap] - [entry(id).tilemap]
($85:82F2: LDA $869F,X ... LDA $86A5,X), so tilemap blocks must be laid out so that every
displayable entry is immediately followed (in the table) by the entry whose pointer marks its end.

Vanilla layout: entries 1..$1A are real messages laid out back-to-back from $85:877F; entry $1B is the
end marker ($957F); entries $1C/$1D re-use the tilemaps of $17/$18 (so $18 must directly follow $17).
"""
import struct
from .rom import Rom, RomError, pc

BANK = 0x85
TABLE = 0x869B
ENTRY_COUNT = 0x1D
ROW_WORDS = 32
ROW_BYTES = ROW_WORDS * 2
FREE_START = 0x9643          # first byte of the trailing $FF run in bank $85 (verified on the original)
FREE_END = 0x10000
END_ID = "END"

# Readable view of tile numbers (low 10 bits). Display only: the build never uses this table.
CHARMAP = {0x04E: " ", 0x00E: "|", 0x0CF: "-", 0x0FA: ".", 0x0FB: ",", 0x0FC: "'", 0x0FD: "'",
           0x0FE: "?", 0x0FF: "!"}
CHARMAP.update({0x0E0 + i: chr(ord("A") + i) for i in range(26)})


def read_table(rom: Rom):
    out = []
    for i in range(ENTRY_COUNT):
        a = TABLE + i * 6
        out.append((rom.word(BANK, a), rom.word(BANK, a + 2), rom.word(BANK, a + 4)))
    return out


def row_text(words):
    return "".join(CHARMAP.get(w & 0x3FF, "·") for w in words)


def extract(rom: Rom) -> dict:
    table = read_table(rom)
    addrs = sorted({t for _, _, t in table})
    end_addr = addrs[-1]                   # highest pointer = end marker of the data block
    names = {}
    blocks = []
    for n, a in enumerate(addrs[:-1]):
        size = addrs[n + 1] - a
        if size % ROW_BYTES:
            raise RomError(f"tilemap ${a:04X} size {size:#x} is not a whole number of rows")
        raw = rom.read(rom_pc(a), size)
        words = struct.unpack(f"<{size // 2}H", raw)
        rows = [words[r:r + ROW_WORDS] for r in range(0, len(words), ROW_WORDS)]
        first = next(i + 1 for i, (_, _, t) in enumerate(table) if t == a)
        name = f"msg{first:02X}"
        names[a] = name
        blocks.append({
            "id": name,
            "orig_addr": f"{a:04X}",
            "text": [row_text(r) for r in rows],
            "rows": [" ".join(f"{w:04X}" for w in r) for r in rows],
        })
    names[end_addr] = END_ID
    entries = [{"msg": i + 1, "setup": f"{s:04X}", "modify": f"{m:04X}", "block": names[t]}
               for i, (s, m, t) in enumerate(table)]
    return {"bank": f"{BANK:02X}", "table": f"{TABLE:04X}", "data_start": f"{addrs[0]:04X}",
            "data_end": f"{end_addr:04X}", "blocks": blocks, "entries": entries}


def rom_pc(addr):
    return pc(BANK, addr)


def block_bytes(block) -> bytes:
    words = []
    for r, line in enumerate(block["rows"]):
        ws = [int(x, 16) for x in line.split()]
        if len(ws) != ROW_WORDS:
            raise RomError(f"{block['id']} row {r}: {len(ws)} words, expected {ROW_WORDS}")
        words.extend(ws)
    if not words:
        raise RomError(f"{block['id']} is empty")
    return struct.pack(f"<{len(words)}H", *words)


def layout(doc: dict, start: int, limit: int):
    """Assign addresses to blocks placed back-to-back from `start`. Returns ({id: addr}, end, {id: bytes})."""
    addr, where, payload = start, {}, {}
    for b in doc["blocks"]:
        data = block_bytes(b)
        where[b["id"]] = addr
        payload[b["id"]] = data
        addr += len(data)
    if addr > limit:
        raise RomError(f"message data needs ${start:04X}-${addr:04X}, exceeds limit ${limit:04X}")
    where[END_ID] = addr
    return where, addr, payload


def check_size_chain(doc, where, payload):
    """Every entry except the last must be followed by the pointer that ends its block (game's size rule)."""
    ents = doc["entries"]
    for i in range(len(ents) - 1):
        bid = ents[i]["block"]
        if bid == END_ID:
            continue
        size = where[ents[i + 1]["block"]] - where[bid]
        if size != len(payload[bid]):
            raise RomError(f"message {ents[i]['msg']:#04x}: game would compute size {size:#x}, "
                           f"block {bid} is {len(payload[bid]):#x}")


def build(rom: Rom, doc: dict, start: int = None, limit: int = None) -> dict:
    """Write tilemaps and table pointers. start=None -> original location (in-place)."""
    if start is None:
        start = int(doc["data_start"], 16)
        limit = int(doc["data_end"], 16) if limit is None else limit
    if limit is None:
        limit = FREE_END
    if len(doc["entries"]) != ENTRY_COUNT:
        raise RomError(f"expected {ENTRY_COUNT} table entries")
    where, end, payload = layout(doc, start, limit)
    check_size_chain(doc, where, payload)
    for b in doc["blocks"]:
        rom.write_in_bank(BANK, where[b["id"]], payload[b["id"]])
    for i, e in enumerate(doc["entries"]):
        a = TABLE + i * 6
        rom.set_word(BANK, a, int(e["setup"], 16))
        rom.set_word(BANK, a + 2, int(e["modify"], 16))
        rom.set_word(BANK, a + 4, where[e["block"]])
    return {"start": start, "end": end, "where": where}
