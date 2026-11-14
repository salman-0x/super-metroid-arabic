-- Mesen 2 --testRunner: real framebuffer screenshots at absolute frames (SHOTS), optional scripted buttons (PRESS: {frame, button}).
local OUT = "C:/PLACEHOLDER/"
local LAST = 0
local frames = 0
local shots, press = {}, {}
--@@PLAN@@
local function wr(name, data) local f = io.open(OUT .. name, "wb") f:write(data) f:close() end
emu.addEventCallback(function()
  frames = frames + 1
  if shots[frames] then
    local ok, png = pcall(emu.takeScreenshot)
    if ok and png then wr("shot_" .. shots[frames] .. ".png", png) end
  end
  if frames >= LAST then emu.stop(0) end
end, emu.eventType.endFrame)
emu.addEventCallback(function()
  for _, e in ipairs(press) do if frames >= e[1] and frames < e[1] + 3 then pcall(emu.setInput, { [e[2]] = true }, 0) end end
end, emu.eventType.inputPolled)
