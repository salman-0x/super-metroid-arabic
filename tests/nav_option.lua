-- Mesen 2 --testRunner (needs AllowIoOsAccess). Boot -> file select (Start taps until frame 690) -> option mode, then press
-- the buttons listed in SEQ (frame, button) and dump the screen at DUMP_AT frames.   OUT/DOWNS are patched by the runner.
local OUT = "C:/PLACEHOLDER/"
local DOWNS = 3                      -- how many Down presses before A (3 = CONTROLLER SETTING MODE, 4 = SPECIAL SETTING MODE)
local LAST = 1000
local frames = 0
local seq, dumps = {}, { [940] = "n" }
if DOWNS >= 0 then                    -- DOWNS < 0 = stay on the main option screen (no input)
  for i = 1, DOWNS do seq[#seq + 1] = { 730 + 20 * (i - 1), "down" } end
  seq[#seq + 1] = { 730 + 20 * DOWNS + 10, "a" }
end
local log = io.open(OUT .. "nav.txt", "w")

local function wr(name, data) local f = io.open(OUT .. name, "wb") f:write(data) f:close() end
local function mem(t, n, base) local r = {} for i = 0, n - 1 do r[#r + 1] = string.char(emu.read(base + i, t)) end return table.concat(r) end
local function flat(t, p, lines, d) if d > 4 then return end for k, v in pairs(t) do local n = p .. tostring(k) if type(v) == "table" then flat(v, n .. ".", lines, d + 1) else lines[#lines + 1] = n .. "=" .. tostring(v) end end end

emu.addEventCallback(function()
  frames = frames + 1
  if frames % 100 == 0 then log:write(string.format("frame %d state %02X\n", frames, emu.read(0x7E0998, emu.memType.snesMemory))) log:flush() end
  local tag = dumps[frames]
  if tag then
    wr("vram_" .. tag .. ".bin", mem(emu.memType.snesVideoRam, 0x10000, 0))
    wr("cgram_" .. tag .. ".bin", mem(emu.memType.snesCgRam, 0x200, 0))
    local lines = {}
    flat(emu.getState(), "", lines, 0)
    wr("state_" .. tag .. ".txt", table.concat(lines, "\n"))
    wr("wram_" .. tag .. ".bin", mem(emu.memType.snesMemory, 0x2000, 0x7E3000))
    log:write(string.format("DUMP %s at %d\n", tag, frames)) log:flush()
  end
  if frames >= LAST then log:close() emu.stop(0) end
end, emu.eventType.endFrame)

emu.addEventCallback(function()
  if frames >= 400 and frames < 690 and (frames - 400) % 90 < 4 then
    pcall(emu.setInput, { start = true }, 0)
  end
  for _, e in ipairs(seq) do
    if frames >= e[1] and frames < e[1] + 3 then pcall(emu.setInput, { [e[2]] = true }, 0) end
  end
end, emu.eventType.inputPolled)
