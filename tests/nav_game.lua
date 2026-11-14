-- Mesen 2 --testRunner. New game from the title: Start taps, then A/Start every 250 frames through the intro; when the game state
-- ($7E:0998) is 8 (gameplay) for 150 frames, runs the in-game plan (frames relative to that moment).
local OUT = "C:/PLACEHOLDER/"
local frames, g0, stable = 0, nil, 0
local log = io.open(OUT .. "game.txt", "w")
local rel_plan = {}   -- {rel_frame, button}
local dumps = {}      -- rel_frame -> tag
local POKES = nil
local forces = {}     -- rel_frame -> game state value written to $7E:0998 (FORCE)
local function add(f, b) rel_plan[#rel_plan + 1] = { f, b } end
--@@PLAN@@
local function wr(name, data) local f = io.open(OUT .. name, "wb") f:write(data) f:close() end
local function mem(t, n, base) local r = {} for i = 0, n - 1 do r[#r + 1] = string.char(emu.read(base + i, t)) end return table.concat(r) end
local function flat(t, p, lines, d) if d > 4 then return end for k, v in pairs(t) do local n = p .. tostring(k) if type(v) == "table" then flat(v, n .. ".", lines, d + 1) else lines[#lines + 1] = n .. "=" .. tostring(v) end end end
local function dump(tag, st)
  local ok, png = pcall(emu.takeScreenshot)
  if ok and png then wr("shot_" .. tag .. ".png", png) end
  wr("vram_" .. tag .. ".bin", mem(emu.memType.snesVideoRam, 0x10000, 0))
  wr("oam_" .. tag .. ".bin", mem(emu.memType.snesSpriteRam, 544, 0))
  wr("cgram_" .. tag .. ".bin", mem(emu.memType.snesCgRam, 0x200, 0))
  local lines = {} flat(emu.getState(), "", lines, 0)
  wr("state_" .. tag .. ".txt", table.concat(lines, "\n"))
  log:write(string.format("DUMP %s frame %d state %02X\n", tag, frames, st)) log:flush()
end
emu.addEventCallback(function()
  frames = frames + 1
  local st = emu.read(0x7E0998, emu.memType.snesMemory)
  if frames % 200 == 0 then log:write(string.format("frame %d state %02X\n", frames, st)) log:flush() end
  if not g0 then
    if st == 8 and frames >= 9000 then stable = stable + 1 else stable = 0 end
    if stable >= 150 then g0 = frames log:write("gameplay at " .. g0 .. "\n") log:flush() end
    if frames > LASTWAIT then log:write("gameplay never reached\n") log:close() emu.stop(1) end
    return
  end
  local rel = frames - g0
  if POKES and rel >= 50 and rel < 120 then POKES() end
  if forces[rel] then emu.write(0x7E0998, forces[rel], emu.memType.snesMemory) end
  if dumps[rel] then dump(dumps[rel], st) end
  if rel >= REL_LAST then log:close() emu.stop(0) end
end, emu.eventType.endFrame)
emu.addEventCallback(function()
  if not g0 then
    if frames >= 400 and frames < 600 and (frames - 400) % 90 < 4 then pcall(emu.setInput, { start = true }, 0) end
    if frames >= 800 and (frames - 800) % 250 < 4 then pcall(emu.setInput, { a = true }, 0) end
    return
  end
  local rel = frames - g0
  for _, e in ipairs(rel_plan) do if rel >= e[1] and rel < e[1] + 3 then pcall(emu.setInput, { [e[2]] = true }, 0) end end
end, emu.eventType.inputPolled)





