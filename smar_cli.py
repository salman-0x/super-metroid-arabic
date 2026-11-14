"""Super Metroid Arabic toolkit CLI.

  python smar_cli.py extract  base/original.sfc data/messages.json
  python smar_cli.py build    base/original.sfc data/messages.json build/out.sfc [--relocate]
  python smar_cli.py verify   build/out.sfc [--against base/original.sfc]
  python smar_cli.py audit    base/original.sfc
"""
import argparse
import json
import struct
import sys

from smar.rom import Rom, diff_ranges, snes, pc, ORIGINAL_SHA1
from smar import messages as M


def cmd_extract(a):
    rom = Rom.load(a.rom)
    if rom.sha1() != ORIGINAL_SHA1:
        print(f"WARNING: input SHA1 {rom.sha1()} is not the known original")
    doc = M.extract(rom)
    with open(a.json, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"extracted {len(doc['blocks'])} tilemap blocks, {len(doc['entries'])} table entries -> {a.json}")
    for b in doc["blocks"]:
        print(f"  {b['id']} ${b['orig_addr']} rows={len(b['rows'])}  {b['text'][0].strip('|').strip()!r}")


def cmd_build(a):
    rom = Rom.load(a.rom)
    with open(a.json, encoding="utf-8") as f:
        doc = json.load(f)
    if a.relocate:
        info = M.build(rom, doc, start=M.FREE_START, limit=M.FREE_END)
    else:
        info = M.build(rom, doc)
    chk = rom.fix_checksum()
    rom.save(a.out)
    used = info["end"] - info["start"]
    print(f"tilemaps at $85:{info['start']:04X}-${info['end'] - 1:04X} ({used:#x} bytes), "
          f"end marker ${info['end']:04X}")
    print(f"checksum ${chk:04X} complement ${chk ^ 0xFFFF:04X}  sha1 {rom.sha1()}  -> {a.out}")


def cmd_build_ar(a):
    from smar import translate as T
    rom = Rom.load(a.rom)
    if rom.sha1() != ORIGINAL_SHA1:
        print("ERROR: build-ar must start from the untouched original ROM"); return 2
    if not T.check_font_region_pristine(rom):
        print("ERROR: font region $9A:C200 is not zero in the input"); return 2
    with open(a.json, encoding="utf-8") as f:
        doc = json.load(f)
    with open(a.translations, encoding="utf-8") as f:
        tr = json.load(f)
    res = T.build_arabic(rom, doc, tr, relocate=a.relocate)
    rom.save(a.out)
    print(f"font tiles injected: {res['font_tiles']} (tiles $100-${0xFF + res['font_tiles']:03X})")
    print(f"tilemaps ${res['info']['start']:04X}-${res['info']['end'] - 1:04X}  checksum ${res['checksum']:04X}  "
          f"sha1 {rom.sha1()} -> {a.out}")


def cmd_verify(a):
    rom = Rom.load(a.rom)
    chk, comp = rom.stored_checksum()
    ok = rom.checksum_ok()
    print(f"title={rom.title()!r} size={len(rom.data):#x}")
    print(f"stored checksum ${chk:04X} complement ${comp:04X} computed ${rom.compute_checksum():04X} -> "
          f"{'OK' if ok else 'BAD'}")
    tbl = M.read_table(rom)
    for i in range(len(tbl) - 1):
        size = tbl[i + 1][2] - tbl[i][2]
        flag = "" if size > 0 and size % M.ROW_BYTES == 0 else "  (end marker / not displayable)"
        print(f"  msg {i + 1:#04x} ptr ${tbl[i][2]:04X} size {size if size > 0 else 0:#05x}{flag}")
    if a.against:
        base = Rom.load(a.against)
        rs = diff_ranges(base.data, rom.data)
        print(f"{len(rs)} differing ranges vs {a.against}:")
        for s, e in rs:
            print(f"  {snes(s)}-{snes(e - 1)}  pc {s:#08x}-{e - 1:#08x}  {e - s} bytes")
    return 0 if ok else 1


def cmd_audit(a):
    """Look for 16-bit copies of tilemap addresses in bank $85 outside the table (hardcoded references)."""
    rom = Rom.load(a.rom)
    tbl = M.read_table(rom)
    bank = rom.read(pc(0x85, 0x8000), 0x8000)
    t0, t1 = M.TABLE - 0x8000, M.TABLE - 0x8000 + M.ENTRY_COUNT * 6
    for addr in sorted({t for _, _, t in tbl}):
        pat = struct.pack("<H", addr)
        hits, i = [], bank.find(pat)
        while i != -1:
            if not t0 <= i < t1:
                hits.append(f"$85:{0x8000 + i:04X}")
            i = bank.find(pat, i + 1)
        print(f"  ${addr:04X}: {len(hits)} hit(s) outside table {hits}")


def main():
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("extract"); s.add_argument("rom"); s.add_argument("json"); s.set_defaults(f=cmd_extract)
    s = sp.add_parser("build"); s.add_argument("rom"); s.add_argument("json"); s.add_argument("out")
    s.add_argument("--relocate", action="store_true"); s.set_defaults(f=cmd_build)
    s = sp.add_parser("build-ar"); s.add_argument("rom"); s.add_argument("json"); s.add_argument("translations")
    s.add_argument("out"); s.add_argument("--relocate", action="store_true"); s.set_defaults(f=cmd_build_ar)
    s = sp.add_parser("verify"); s.add_argument("rom"); s.add_argument("--against"); s.set_defaults(f=cmd_verify)
    s = sp.add_parser("audit"); s.add_argument("rom"); s.set_defaults(f=cmd_audit)
    a = p.parse_args()
    sys.exit(a.f(a) or 0)


if __name__ == "__main__":
    main()
