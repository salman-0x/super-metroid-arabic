# Technical notes

Everything is derived from measurements in a running game (Mesen 2) and is checked by `tests/`. Addresses are SNES LoROM (`$bank:addr`).
Each module refuses to patch if the bytes it expects are not the original ones, so a wrong ROM fails loudly instead of corrupting it.

| Area | Module | What is changed |
|---|---|---|
| Message boxes | `smar/messages.py`, `smar/translate.py` | the $85 message-tilemap table is rebuilt and relocated to `$85:9643-$A442`; 119 Arabic glyph tiles (2bpp, tiles `$100-$176`) are added to the upper half of the message font block at `$9A:C200` |
| YES/NO | `smar/translate.py` | the three YES/NO tilemap rows (mirrored arrow with H-flip) |
| Menus (file select) | `smar/menu_ar.py` | tile set `$8E:8000` (0x5600 bytes) is copied to `$B8:8000` and Arabic tiles are appended from tile `$2B0`; the loader's inline DMA parameters at `$81:8DF1` are repointed; the unused second DMA at `$81:8DFE` is neutralised when more than 80 tiles are needed; strings are rewritten in place |
| OPTION MODE | `smar/option_ar.py` | the five compressed tilemaps (`$97:8DF4…`) are decompressed, edited, recompressed to `$83:AD66+`, and their call sites in `$82:EC66…ECAA` repointed |
| GAME OVER | `smar/gameover_ar.py` | five strings are written to `$81:EF1A+` and the `LDY/LDX` operands at `$81:9206-$922D` are changed |
| File dialogs | `smar/slot_ar.py` | three strings at `$81:F31A+`; operands of the code at `$81:97A8`, `$98BB`, `$9C0F`; the file letter is written by code (`ADC #$206A`), so its base tile is repointed to three consecutive Arabic letter tiles and each placeholder cell address is moved |
| Intro story | `smar/intro_ar.py` | typed text = 6-byte records in bank `$8C`; glyph objects (`4D 88 01 02 …`, two tiles tall) at `$8C:F3E9`; the font block `$95:D089` is recompressed to `$89:AEFD` and enlarged from 0x900 to 0x1000 bytes (loader `$8B:A401/A405`, DMA size `$8B:A48F`); the first white page is a compressed tilemap at `$97:8D12` |
| Pause screens | `smar/pause_ar.py`, `smar/area_ar.py` | raw 4bpp tile set at `$B6:8000`: label, button and item-name tiles are redrawn in place; the area-name word table at `$82:9670` points at Arabic tiles in the (otherwise unused) tiles `$30-$49`, `$0E`, `$0F`, `$4E` |
| HUD | `smar/hud_ar.py` | tiles `$0B,$0C,$0D,$32` (ENERGY) and `$47,$48` (AUTO) of the 2bpp block `$9A:B200` |

## Arabic text engine
- `smar/arabic.py`: normalisation, contextual shaping (isolated/initial/medial/final, lam-alef ligature), simplified bidi (Latin runs stay LTR).
- Fonts: `smar/font_ar.py` (hand-made 8x8), `smar/font_big.py` (16 px, rasterised from DejaVu Sans with dot re-placement), `smar/font_micro.py` (6-row condensed font derived from the 8x8 art), `smar/pack_ar.py` (packs a word to a given pixel width).
- `smar/sm_lz.py`: the game's LZ-style compression (decompressor `$80:B0FF`).

## Pitfalls found
- Mesen writes a battery file (`.srm`) per ROM *file name*; a slot created by an earlier run changes the file-select screen. Run tests on fresh copies.
- Tile `$1F` of the pause set is the blank filler of the pause tilemaps; the area-name pool avoids it.
- `emu.takeScreenshot()` in Mesen's Lua gives a real framebuffer; a tilemap composite (`tools/screen_composite.py`) ignores sprites and mode 7.
