-- Mesen 2 --testRunner script: after the game's own font-loading routine ($82:82E3) has run, compare VRAM
-- $4000-$4FFF (word addresses; 0x8000-0x9FFF as bytes) with the font block in ROM ($9A:B200, 0x2000 bytes).
-- Exit code:  0 = never reached / script error path is 250
--   1   = all 8192 bytes match, but the upper half (tiles 0x100-0x1FF) is all zero  (vacuous for the Arabic font)
--   2   = all 8192 bytes match AND the upper half contains data (the Arabic tiles really are in VRAM)
--   101..200 = number of mismatching bytes (+100, capped)
--   250 = script error
local FRAMES = 10
local PRG_FONT = 0x1A * 0x8000 + 0x3200      -- file offset of $9A:B200
local VRAM_FONT = 0x8000                     -- VRAM word $4000 -> byte address
local frames = 0

local function run()
  frames = frames + 1
  if frames < FRAMES then return end
  local bad, upper_nonzero = 0, 0
  for i = 0, 0x1FFF do
    local v = emu.read(VRAM_FONT + i, emu.memType.snesVideoRam)
    local r = emu.read(PRG_FONT + i, emu.memType.snesPrgRom)
    if v ~= r then bad = bad + 1 end
    if i >= 0x1000 and v ~= 0 then upper_nonzero = upper_nonzero + 1 end
  end
  if bad > 0 then emu.stop(100 + math.min(bad, 100)) return end
  emu.stop(upper_nonzero > 0 and 2 or 1)
end

emu.addEventCallback(function()
  if not pcall(run) then emu.stop(250) end
end, emu.eventType.endFrame)
