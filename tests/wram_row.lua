-- Mesen 2 --testRunner: hash the 64 bytes at WRAM $7E:3300 (where the game's YES/NO toggle routine
-- $85:8510 copies the selected prompt row). Same hash function as tests/emu_yesno_test.py:
--   h = 5381; for each byte: h = (h*33 + byte) % 2147483647 ; exit code = h (+1000 if h < 1000), 250 = error
local FRAMES = 5
local START, LEN = 0x7E3300, 0x40
local frames = 0

local function run()
  frames = frames + 1
  if frames < FRAMES then return end
  local h = 5381
  for i = 0, LEN - 1 do
    h = (h * 33 + emu.read(START + i, emu.memType.snesMemory)) % 2147483647
  end
  if h < 1000 then h = h + 1000 end
  emu.stop(h)
end

emu.addEventCallback(function()
  if not pcall(run) then emu.stop(250) end
end, emu.eventType.endFrame)
