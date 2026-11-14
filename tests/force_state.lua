-- Mesen 2 --testRunner (needs AllowIoOsAccess). Boot to the file-select screen, then force the game-state variable $7E:0998
-- to FORCED at frame FORCE_AT and log whether the menu-family code runs afterwards:
--   exec hooks on $81:8D55 (JSR to the tile loader, file-select init) and $81:9475 (second caller), $81:8DDB (the loader).
-- Output: OUT/force.txt with one line per hook hit (frame, hook, current game state).
local OUT = "C:/PLACEHOLDER/"
local FORCED = 0x19
local FORCE_AT, DUMP_AT, LAST = 700, 790, 800
local PRESS_FROM, PRESS_EVERY = 400, 90
local frames = 0
local log = io.open(OUT .. "force.txt", "w")

local function hook(name)
  return function()
    log:write(string.format("%d %s state=%02X\n", frames, name, emu.read(0x7E0998, emu.memType.snesMemory)))
    log:flush()
  end
end
pcall(function()
  emu.addMemoryCallback(hook("8D55"), emu.callbackType.exec, 0x818D55, 0x818D55)
  emu.addMemoryCallback(hook("9475"), emu.callbackType.exec, 0x819475, 0x819475)
  emu.addMemoryCallback(hook("8DDB"), emu.callbackType.exec, 0x818DDB, 0x818DDB)
end)

emu.addEventCallback(function()
  frames = frames + 1
  if frames == FORCE_AT then
    emu.write(0x7E0998, FORCED, emu.memType.snesMemory)
    log:write(string.format("%d FORCED state=%02X\n", frames, FORCED)) log:flush()
  end
  if frames == DUMP_AT then            -- dump the screen the forced state produced
    local function wr(name, data) local f = io.open(OUT .. name, "wb") f:write(data) f:close() end
    local function mem(t, n, base) local r = {} for i = 0, n - 1 do r[#r + 1] = string.char(emu.read(base + i, t)) end return table.concat(r) end
    wr("vram_s.bin", mem(emu.memType.snesVideoRam, 0x10000, 0))
    wr("cgram_s.bin", mem(emu.memType.snesCgRam, 0x200, 0))
    local st = emu.getState()
    local lines = {}
    local function flat(t, p, d) if d > 4 then return end for k, v in pairs(t) do local n = p .. tostring(k) if type(v) == "table" then flat(v, n .. ".", d + 1) else lines[#lines + 1] = n .. "=" .. tostring(v) end end end
    flat(st, "", 0)
    wr("state_s.txt", table.concat(lines, "\n"))
    log:write(string.format("%d DUMPED state=%02X\n", frames, emu.read(0x7E0998, emu.memType.snesMemory))) log:flush()
  end
  if frames >= LAST then log:close() emu.stop(0) end
end, emu.eventType.endFrame)

emu.addEventCallback(function()
  if frames >= PRESS_FROM and frames < FORCE_AT and (frames - PRESS_FROM) % PRESS_EVERY < 4 then
    pcall(emu.setInput, { start = true }, 0)
  end
end, emu.eventType.inputPolled)
