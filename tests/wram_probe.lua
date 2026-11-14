-- Mesen 2 --testRunner script. The test ROM's reset stub runs the game's own message routine
-- ($85:8241) and spins. After a few frames we hash WRAM $7E:3200-$7E:34FF and return it as the exit code.
--   250 = script error, 252 = buffer still all zero (routine never wrote anything)
local FRAMES = 5
local START, LEN = 0x7E3200, 0x300
local frames = 0

local function run()
  frames = frames + 1
  if frames < FRAMES then return end
  local h, nonzero = 5381, 0
  for i = 0, LEN - 1 do
    local b = emu.read(START + i, emu.memType.snesMemory)
    if b ~= 0 then nonzero = nonzero + 1 end
    h = (h * 33 + b) % 2147483647
  end
  if nonzero == 0 then emu.stop(252) return end
  if h < 1000 then h = h + 1000 end
  emu.stop(h)
end

emu.addEventCallback(function()
  if not pcall(run) then emu.stop(250) end
end, emu.eventType.endFrame)
