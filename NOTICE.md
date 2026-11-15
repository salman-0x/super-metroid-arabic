# Notice

Arabic translation, tools and fonts by **Mr S**.

- **Super Metroid** is a trademark and copyright of Nintendo. This project is an unofficial fan translation, not affiliated with or
  endorsed by Nintendo. It contains **no game data**: the repository holds code, Arabic text and a BPS patch. A BPS patch stores only new bytes and *refers* to the original ROM for everything unchanged or merely moved, so no part of Nintendo's ROM (code, graphics or text) is copied into it. Short quotations of UI labels and item names appear only in the review file, for translation review; the original intro/story text is not included.
  You must own a copy of the game and apply the patch yourself. Do not upload ROM files to Issues, Pull Requests or releases.
- The Arabic bitmap fonts (8x8 and the condensed 6-row font) are original hand-made pixel art / derived from it.
- The 16-pixel-tall Arabic menu glyphs are rasterized at build time from **DejaVu Sans** (shipped with matplotlib; Bitstream Vera /
  DejaVu licence, free to use and embed). The font file is not redistributed here; the patch only contains the resulting small bitmaps.
- Tests use the **Mesen 2** emulator (GPL-3.0) through its Lua test runner; Mesen is not part of this repository.
- **Licences.** The *source code* (smar/, tools/, tests/, smar_cli.py) is MIT (see LICENSE). The *Arabic translation* (data/translations_ar.json, the review files), the *BPS patch* and the *website* are
  © 2026 Mr S under **CC BY-NC-SA 4.0** (see LICENSE-TRANSLATION.md): attribution, **non-commercial only**, share-alike. Selling the translation or a patched game, or putting it behind a paywall, is not allowed.
  Versions published before this change (up to commit `0ac0e02`) were released under MIT and stay available under that licence; the new terms apply to everything published after it.
  This notice is documentation, not legal advice.

- The screenshots show the patched game for illustration (commentary/documentation use). Nintendo's rights in them remain Nintendo's.
- Rights holders can ask for removal of anything in this repository by opening an Issue and it will be removed promptly.
- This notice is documentation, not legal advice.
- The tools were developed with the assistance of Claude (Anthropic); the translation texts were written by the assistant and need human review.
