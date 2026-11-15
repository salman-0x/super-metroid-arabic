-- Mesen 2 --testRunner. ROM = stub build (tools/make_save_full.py): slot A holds an all-items save.
-- Boots, taps Start to the file select, presses A until gameplay ($7E:0998 == 8) is stable, logs the item RAM, then opens the pause
-- screens (Start, L/R) and takes screenshots. Frame numbers after gameplay are relative (g0).
local OUT = "C:/PLACEHOLDER/"
local frames, g0, fs, stable = 0, nil, nil, 0
local fsStable, fsAt, seen4 = 0, nil, false
local log = io.open(OUT .. "full.txt", "w")
local function wr(name, data) local f = io.open(OUT .. name, "wb") f:write(data) f:close() end
local function rd16(a) return emu.read(a, emu.memType.snesMemory) + 256 * emu.read(a + 1, emu.memType.snesMemory) end
local DUMPTAGS = { equip_a = true, equip_b = true, after_450 = true, pause_a = true }
local function mem(t, n, base) local r = {} for i = 0, n - 1 do r[#r + 1] = string.char(emu.read(base + i, t)) end return table.concat(r) end
local function flat(t, p, lines, d) if d > 4 then return end for k, v in pairs(t) do local n = p .. tostring(k) if type(v) == "table" then flat(v, n .. ".", lines, d + 1) else lines[#lines + 1] = n .. "=" .. tostring(v) end end end
local function shot(tag)
  if DUMPTAGS[tag] then
    wr("vram_" .. tag .. ".bin", mem(emu.memType.snesVideoRam, 0x10000, 0))
    wr("cgram_" .. tag .. ".bin", mem(emu.memType.snesCgRam, 0x200, 0))
    wr("oam_" .. tag .. ".bin", mem(emu.memType.snesSpriteRam, 544, 0))
    local lines = {} flat(emu.getState(), "", lines, 0) wr("state_" .. tag .. ".txt", table.concat(lines, "\n"))
  end
  local ok, png = pcall(emu.takeScreenshot)
  if ok and png then wr("shot_" .. tag .. ".png", png) end
  log:write(string.format("SHOT %s frame %d state %02X\n", tag, frames, emu.read(0x7E0998, emu.memType.snesMemory))) log:flush()
end
-- relative plan after gameplay: {frame, button}
local plan = { {700, "start"} }
for f = 840, 858, 3 do plan[#plan + 1] = { f, "r" } end      -- hold R: map -> equipment screen
for f = 1000, 1005, 3 do plan[#plan + 1] = { f, "a" } end      -- toggle reserve mode AUTO <-> MANUAL

for f = 1250, 1268, 3 do plan[#plan + 1] = { f, "l" } end      -- back to the map
plan[#plan + 1] = { 1400, "start" }
local shots = { [790] = "pause_a", [960] = "equip_a", [1060] = "equip_b", [1190] = "equip_c", [1340] = "map_again", [1500] = "back_in_game" }
emu.addEventCallback(function()
  frames = frames + 1
  local st = emu.read(0x7E0998, emu.memType.snesMemory)
  if frames % 300 == 0 then log:write(string.format("frame %d state %02X\n", frames, st)) log:flush() end
  if st == 4 then fsStable = fsStable + 1 seen4 = true else fsStable = 0 end
  if fsStable == 60 and not fsAt then fsAt = frames shot("fileselect") end
  if fsAt and (frames - fsAt) % 60 == 30 and (frames - fsAt) < 1000 then shot("after_" .. (frames - fsAt)) end
  if not g0 then
    if st == 8 and frames >= 600 then stable = stable + 1 else stable = 0 end
    if stable >= 150 then
      g0 = frames
      log:write(string.format("gameplay at %d items=%04X collected=%04X beams=%04X beamsCol=%04X energy=%d/%d missiles=%d/%d supers=%d/%d pb=%d/%d reserve=%d/%d area=%d\n",
        g0, rd16(0x7E09A2), rd16(0x7E09A4), rd16(0x7E09A6), rd16(0x7E09A8), rd16(0x7E09C2), rd16(0x7E09C4), rd16(0x7E09C6), rd16(0x7E09C8),
        rd16(0x7E09CA), rd16(0x7E09CC), rd16(0x7E09CE), rd16(0x7E09D0), rd16(0x7E09D6), rd16(0x7E09D4), rd16(0x7E079F)))
      log:flush()
      shot("gameplay")
    end
    if frames > 6000 then log:write("gameplay never reached\n") log:close() emu.stop(1) end
    return
  end
  local rel = frames - g0
  if shots[rel] then shot(shots[rel]) end
  if rel >= 1560 then log:close() emu.stop(0) end
end, emu.eventType.endFrame)
emu.addEventCallback(function()
  if not g0 then
    if not seen4 and frames >= 400 and (frames - 400) % 90 < 4 then pcall(emu.setInput, { start = true }, 0) end   -- title -> file select
    if fsAt and (frames - fsAt) >= 90 and ((frames - fsAt) == 90 or (frames - fsAt) == 330 or (frames - fsAt) == 480 or (frames - fsAt) == 640) then pcall(emu.setInput, { a = true }, 0) end   -- pick slot A / confirm
    return
  end
  local rel = frames - g0
  for _, e in ipairs(plan) do if rel >= e[1] and rel < e[1] + 3 then pcall(emu.setInput, { [e[2]] = true }, 0) end end
end, emu.eventType.inputPolled)










