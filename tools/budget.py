"""Tile budget for the menu translation: count the distinct glyph forms (small 1 tile, big 2 tiles) a set of texts needs.
Usage: python tools/budget.py"""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smar import arabic as AR

SMALL = ["لا بيانات", "نسخ ملف", "مسح ملف", "خروج", "نسخ أي ملف؟", "موافق؟", "اكتمل النسخ.", "مسح أي ملف؟", "تم مسح الملف..."]
BIG = ["ملف ساموس", "ساموس أ", "ساموس ب", "ساموس ج", "وضع نسخ الملف", "وضع مسح الملف", "نعم", "لا"]
small_keys, big_keys = set(), set()
for t in SMALL:
    small_keys |= AR.glyph_keys(t, AR.MENU)
for t in BIG:
    big_keys |= AR.glyph_keys(t, AR.MENU)
print(f"small forms: {len(small_keys)}  -> {len(small_keys)} tiles")
print(f"big forms:   {len(big_keys)}  -> {2 * len(big_keys)} tiles")
print(f"total: {len(small_keys) + 2 * len(big_keys)} tiles (free: 80, ids $2B0-$2FF)")
print("big forms:", " ".join(f"{k[0]}{k[1]}" for k in sorted(big_keys)))
