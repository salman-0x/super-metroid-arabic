-- Mesen 2 --testRunner script (needs AllowIoOsAccess): trace writes into the BG1 tilemap staging buffer $7E:3000-$37FF
-- while the game goes title -> file select -> option mode. Log line per non-zero write: frame pc a x y d dbr addr value
local OUT = "C:/PLACEHOLDER/"
local LAST = 760
local PRESS_FROM, PRESS_EVERY = 400, 90
local frames = 0
local log = io.open(OUT .. "trace.txt", "w")
local count = 0

local function onWrite(addr, value)
  if count > 6000 then return end
  if value == 0 then return end
  local st = emu.getState()
  count = count + 1
  log:write(string.format("%d %02X%04X a=%04X x=%04X y=%04X d=%04X dbr=%02X addr=%06X val=%02X\n",
    frames, st["cpu.k"], st["cpu.pc"], st["cpu.a"], st["cpu.x"], st["cpu.y"], st["cpu.d"], st["cpu.dbr"], addr, value))
end

local ok, err = pcall(function()
  emu.addMemoryCallback(onWrite, emu.callbackType.write, 0x7E3000, 0x7E37FF)
end)
if not ok then log:write("addMemoryCallback failed: " .. tostring(err) .. "\n") end

emu.addEventCallback(function()
  frames = frames + 1
  if frames >= LAST then log:close() emu.stop(0) end
end, emu.eventType.endFrame)

emu.addEventCallback(function()
  if frames >= PRESS_FROM and (frames - PRESS_FROM) % PRESS_EVERY < 4 then
    pcall(emu.setInput, { start = true }, 0)
  end
end, emu.eventType.inputPolled)
