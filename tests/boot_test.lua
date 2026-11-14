-- Headless Mesen 2 test (--testRunner). No file I/O (Mesen disables io by default).
-- Result is returned as the process exit code:
--   31-bit hash of the screen at frame TARGET_FRAME (same ROM behaviour => same code)
--   250 = script error, 251 = screen buffer empty / all one colour (nothing rendered)
-- TARGET_FRAME is patched in by the runner (the line below is rewritten per run).
local TARGET_FRAME = 600

local frames = 0

local function run()
  frames = frames + 1
  if frames < TARGET_FRAME then return end
  local buf = emu.getScreenBuffer()
  local h, first, distinct, seen = 5381, nil, 0, {}
  for i = 1, #buf do
    local px = buf[i]
    h = (h * 33 + px) % 2147483647
    first = first or px
    if not seen[px] then seen[px] = true distinct = distinct + 1 end
  end
  if #buf == 0 or distinct < 4 then emu.stop(251) return end
  if h < 1000 then h = h + 1000 end   -- keep clear of the reserved codes
  emu.stop(h)
end

local function guarded()
  local ok = pcall(run)
  if not ok then emu.stop(250) end
end

emu.addEventCallback(guarded, emu.eventType.endFrame)
