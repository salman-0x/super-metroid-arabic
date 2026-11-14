-- Mesen 2 --testRunner: after the stub ran the game's message routine, count the tilemap words in WRAM
-- $7E:3200-$7E:34FF whose tile id (low 10 bits) is in 0x100-0x1FF (= Arabic glyph tiles).
-- Exit code = 1000 + count   (250 = script error)
local FRAMES = 5
local START, WORDS = 0x7E3200, 0x180
local frames = 0

local function run()
  frames = frames + 1
  if frames < FRAMES then return end
  local n = 0
  for i = 0, WORDS - 1 do
    local lo = emu.read(START + 2 * i, emu.memType.snesMemory)
    local hi = emu.read(START + 2 * i + 1, emu.memType.snesMemory)
    local tile = lo + (hi % 4) * 256
    if tile >= 0x100 and tile < 0x200 then n = n + 1 end
  end
  emu.stop(1000 + n)
end

emu.addEventCallback(function()
  if not pcall(run) then emu.stop(250) end
end, emu.eventType.endFrame)
