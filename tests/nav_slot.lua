-- Mesen 2 --testRunner. Boots, taps Start on the title screen until the file-select screen ($0998 == 4) has been stable for 40
-- frames (t0), then runs the scripted plan with frame numbers RELATIVE to t0 (the boot length varies from run to run).
local OUT = "C:/PLACEHOLDER/"
local LAST = 600                       -- frames after t0
local frames, t0, stable = 0, nil, 0
local seq, dumps = {}, {}
local function add(f, b) seq[#seq + 1] = { f, b } end
--@@PLAN@@
local log = io.open(OUT .. "nav.txt", "w")
local function wr(name, data) local f = io.open(OUT .. name, "wb") f:write(data) f:close() end
local function mem(t, n, base) local r = {} for i = 0, n - 1 do r[#r + 1] = string.char(emu.read(base + i, t)) end return table.concat(r) end
local function flat(t, p, lines, d) if d > 4 then return end for k, v in pairs(t) do local n = p .. tostring(k) if type(v) == "table" then flat(v, n .. ".", lines, d + 1) else lines[#lines + 1] = n .. "=" .. tostring(v) end end end
emu.addEventCallback(function()
  frames = frames + 1
  local st = emu.read(0x7E0998, emu.memType.snesMemory)
  if not t0 then
    if st == 4 then stable = stable + 1 else stable = 0 end
    if stable >= 40 then t0 = frames log:write("t0=" .. t0 .. "\n") log:flush() end
    if frames > 3000 then log:write("never reached the file select\n") log:close() emu.stop(1) end
    return
  end
  local rel = frames - t0
  local tag = dumps[rel]
  if tag then
    wr("vram_" .. tag .. ".bin", mem(emu.memType.snesVideoRam, 0x10000, 0))
    wr("oam_" .. tag .. ".bin", mem(emu.memType.snesSpriteRam, 544, 0))
    wr("cgram_" .. tag .. ".bin", mem(emu.memType.snesCgRam, 0x200, 0))
    local lines = {}
    flat(emu.getState(), "", lines, 0)
    wr("state_" .. tag .. ".txt", table.concat(lines, "\n"))
    wr("wram_" .. tag .. ".bin", mem(emu.memType.snesMemory, 0x2000, 0x7E3000))
    log:write(string.format("DUMP %s at rel %d (state %02X)\n", tag, rel, st)) log:flush()
  end
  if rel >= LAST then log:close() emu.stop(0) end
end, emu.eventType.endFrame)
emu.addEventCallback(function()
  if not t0 then
    if frames >= 400 and (frames - 400) % 90 < 4 and frames < 700 then pcall(emu.setInput, { start = true }, 0) end
    return
  end
  local rel = frames - t0
  for _, e in ipairs(seq) do
    if rel >= e[1] and rel < e[1] + 3 then pcall(emu.setInput, { [e[2]] = true }, 0) end
  end
end, emu.eventType.inputPolled)
