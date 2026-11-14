"""Runtime test of the Arabic build, using the game's own message routine inside Mesen 2.

For every displayable message id it checks:
  1. in-place build and relocated build give identical WRAM output  (pointer table + lookup are right)
  2. the output differs from the original ROM                        (the translation really is what the game copies)
  3. the number of Arabic-tile words the game copied == the number the build put into that message's tilemap

Usage: python tests/emu_arabic_test.py <original.sfc> <ar_inplace.sfc> <ar_relocated.sfc> <messages.json> <translations.json>
"""
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
from smar import messages as M  # noqa: E402
from smar import translate as T  # noqa: E402
from emu_message_test import find_mesen, run_one, NOT_DISPLAYABLE  # noqa: E402

COUNT_LUA = os.path.join(ROOT, "tests", "wram_count.lua")


def expected_counts(doc, tr):
    tdoc = T.apply_translations(doc, tr)
    blocks = {b["id"]: b for b in tdoc["blocks"]}
    out = {}
    for e in tdoc["entries"]:
        b = blocks.get(e["block"])
        if not b:
            continue
        n = sum(1 for row in b["rows"] for w in row.split() if 0x100 <= (int(w, 16) & 0x3FF) < 0x200)
        out[e["msg"]] = n
    return out


def main():
    orig, inplace, reloc, jpath, tpath = sys.argv[1:6]
    doc = json.load(open(jpath, encoding="utf-8"))
    tr = json.load(open(tpath, encoding="utf-8"))
    want = expected_counts(doc, tr)
    mesen = find_mesen()
    bad = 0
    with tempfile.TemporaryDirectory() as td:
        for idx in range(1, M.ENTRY_COUNT + 1):
            if idx in NOT_DISPLAYABLE:
                continue
            h_o, h_i, h_r = (run_one(mesen, p, idx, td) for p in (orig, inplace, reloc))
            c_i = run_one(mesen, inplace, idx, td, COUNT_LUA)
            c_r = run_one(mesen, reloc, idx, td, COUNT_LUA)
            got_i, got_r = c_i - 1000, c_r - 1000
            checks = {
                "inplace==reloc": h_i == h_r and h_i >= 1000,
                "differs-from-original": h_i != h_o,
                f"arabic-words {got_i}/{got_r} == expected {want.get(idx)}": got_i == got_r == want.get(idx),
            }
            ok = all(checks.values())
            bad += not ok
            print(f"msg {idx:#04x}: {'OK ' if ok else 'FAIL'} " + "; ".join(f"{k}={'y' if v else 'N'}" for k, v in checks.items()))
    print("RESULT:", "ALL OK" if not bad else f"{bad} failing message(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
