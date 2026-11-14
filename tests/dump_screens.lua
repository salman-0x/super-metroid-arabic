-- Mesen 2 --testRunner script (needs Debug.ScriptWindow.AllowIoOsAccess = true).
-- Boots the game, taps Start to get past the title, and dumps VRAM / CGRAM / PPU state at chosen frames.
-- OUT is replaced by the runner (placeholder line below).
local OUT = "C:/PLACEHOLDER/"
local DUMP_AT = { [620] = "t", [745] = "f", [1500] = "i" }
local LAST = 1600
local PRESS_FROM, PRESS_EVERY = 400, 90      -- tap Start every 90 frames from frame 400

local frames = 0
local log = io.open(OUT .. "log.txt", "w")

local function wr(name, data)
  local f = io.open(OUT .. name, "wb")
  f:write(data)
  f:close()
end

local function dump_mem(memType, size, base)
  local t = {}
  for i = 0, size - 1 do t[#t + 1] = string.char(emu.read(base + i, memType)) end
  return table.concat(t)
end

local function flat(t, prefix, out, depth)
  if depth > 4 then return end
  local keys = {}
  for k in pairs(t) do keys[#keys + 1] = k end
  table.sort(keys, function(a, b) return tostring(a) < tostring(b) end)
  for _, k in ipairs(keys) do
    local v = t[k]
    local name = prefix .. tostring(k)
    if type(v) == "table" then flat(v, name .. ".", out, depth + 1)
    else out[#out + 1] = name .. "=" .. tostring(v) end
  end
end

local function onFrame()
  frames = frames + 1
  local gs = emu.read(0x7E0998, emu.memType.snesMemory)
  if frames % 100 == 0 then log:write(string.format("frame %d gameState %02X\n", frames, gs)) log:flush() end
  local tag = DUMP_AT[frames]
  if tag then
    wr("vram_" .. tag .. ".bin", dump_mem(emu.memType.snesVideoRam, 0x10000, 0))
    wr("cgram_" .. tag .. ".bin", dump_mem(emu.memType.snesCgRam, 0x200, 0))
    wr("wram_" .. tag .. ".bin", dump_mem(emu.memType.snesMemory, 0x2000, 0x7E0000))
    if tag == "f" then      -- option-mode frame: also the whole 128 KB of WRAM, to find staged tilemaps
      wr("wramfull_" .. tag .. ".bin", dump_mem(emu.memType.snesMemory, 0x20000, 0x7E0000))
    end
    local ok, st = pcall(emu.getState)
    if ok and type(st) == "table" then
      local lines = {}
      flat(st, "", lines, 0)
      wr("state_" .. tag .. ".txt", table.concat(lines, "\n"))
    end
    log:write(string.format("DUMP %s at frame %d gameState %02X\n", tag, frames, gs)) log:flush()
  end
  if frames >= LAST then log:close() emu.stop(0) end
end

local function onInput()
  if frames >= PRESS_FROM and (frames - PRESS_FROM) % PRESS_EVERY < 4 then
    emu.setInput({ start = true }, 0)
  end
end

emu.addEventCallback(function() if not pcall(onFrame) then emu.stop(250) end end, emu.eventType.endFrame)
emu.addEventCallback(function() pcall(onInput) end, emu.eventType.inputPolled)

