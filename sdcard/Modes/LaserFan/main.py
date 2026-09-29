# Laser Fan: neon laser beams fan out from the floor and the ceiling, sweep to the tempo and flash on every beat.
# Add beams for a wall of light, or drop to a few for clean, sharp fans.
# Turn any knob and the picture reacts at once. Tap the `0` key on the beat to sync it by hand (on the real device it locks to the audio kick).
#
# Knob convention (same in every mode):
#   knob1 = size            (beam thickness)
#   knob2 = main motion     (tempo, 30 to 120 BPM; the fans sweep faster too)
#   knob3 = extra detail    (number of beams, 3 to 24; past the middle, extra fans join from the corners)
#   knob4 = foreground color (hue of the beams)
#   knob5 = background color (also the haze the beams fade into)
import colorsys
import math
import time
import pygame

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))

def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, clamp(s), clamp(v))
    return (int(r * 255), int(g * 255), int(b * 255))

_state = {"beats": 0.0, "last": None, "canvas": None, "fade": None, "size": None}

def beat_clock(eyesy):
    now = time.time()
    if _state["last"] is None:
        _state["last"] = now
    dt = min(now - _state["last"], 0.1)
    _state["last"] = now
    bpm = 30 + eyesy.knob2 * 90                               # a slower, more relaxed tempo range
    ks = (eyesy.knob1, eyesy.knob2, eyesy.knob3, eyesy.knob4, eyesy.knob5)
    prev = _state.get("prev")
    move = 0.0 if prev is None else sum(abs(a - b) for a, b in zip(ks, prev))
    _state["prev"] = ks
    # turning ANY knob throws energy into the picture, and it fades away over about a second
    _state["energy"] = max(_state.get("energy", 0.0) * math.exp(-dt * 2.5), min(1.0, move * 30.0))
    energy = _state["energy"]
    _state["beats"] += dt * bpm / 60.0
    if getattr(eyesy, "trig", False):
        _state["beats"] = math.floor(_state["beats"]) + 1.0
    beats = _state["beats"]
    frac = beats % 1.0
    kick = (1.0 - frac) ** 3
    try:
        level = clamp(max(abs(v) for v in eyesy.audio_in[:100]) / 30000.0)
    except Exception:
        level = 0.0
    return dt, beats, frac, max(kick, level, energy * 0.9), energy

def setup(screen, eyesy):
    pass

def draw(screen, eyesy):
    xres, yres = eyesy.xres, eyesy.yres
    dt, beats, frac, kick, energy = beat_clock(eyesy)
    bg = tuple(int(c) for c in eyesy.color_picker_bg(eyesy.knob5))
    if _state["size"] != (xres, yres):
        _state["size"] = (xres, yres)
        _state["canvas"] = pygame.Surface((xres, yres))
        _state["fade"] = pygame.Surface((xres, yres))
    canvas, fade = _state["canvas"], _state["fade"]
    fade.fill(bg)
    fade.set_alpha(60)
    canvas.blit(fade, (0, 0))

    fg = eyesy.color_picker(eyesy.knob4)
    h0 = colorsys.rgb_to_hsv(fg[0] / 255.0, fg[1] / 255.0, fg[2] / 255.0)[0]
    n = 3 + int(eyesy.knob3 * 21.99)
    thick = 1 + int(eyesy.knob1 * 9) + int(energy * 6)        # turning a knob makes the beams swell
    amp = 0.30 + 0.45 * eyesy.knob2                            # faster tempos swing wider
    L = math.hypot(xres, yres) * 1.2

    # each fan: (origin x, origin y, direction it points, base hue shift)
    fans = [(xres / 2, yres + 10, -math.pi / 2, 0.0), (xres / 2, -10, math.pi / 2, 0.5)]
    if eyesy.knob3 > 0.55:
        fans += [(0, -10, math.pi * 0.25, 0.25), (xres, -10, math.pi * 0.75, 0.75)]
    step = math.pi / 4.0
    for fi, (ox, oy, direction, hs) in enumerate(fans):
        spread = math.pi * (0.30 + 0.28 * (0.5 + 0.5 * math.sin(beats * step * 0.5 + fi)))       # the fan breathes open and shut
        sweep = amp * math.sin(beats * step + fi * 1.7) + 0.10 * kick * (1 if int(beats) % 2 == 0 else -1)   # and swings, with a kick on the beat
        for i in range(n):
            u = (i + 0.5) / n - 0.5
            a = direction + sweep + u * spread * (1.0 if fi % 2 == 0 else -1.0)
            ex, ey = ox + L * math.cos(a), oy + L * math.sin(a)
            hue = h0 + hs * 0.4 + (i / n) * 0.35
            pygame.draw.line(canvas, hsv(hue, 0.9, 0.5 + 0.3 * kick), (ox, oy), (ex, ey), thick + 6)      # glow
            pygame.draw.line(canvas, hsv(hue, 0.35, 1.0), (ox, oy), (ex, ey), thick)                      # hot core
        pygame.draw.circle(canvas, hsv(h0 + hs * 0.4, 0.3, 1.0), (int(ox), int(oy)), int(20 + 40 * kick))   # the source flares on the beat
    screen.blit(canvas, (0, 0))
    if kick > 0.6:                                            # a quick strobe on the hit
        flash = pygame.Surface((xres, yres))
        flash.fill((255, 255, 255))
        flash.set_alpha(int(45 * (kick - 0.6) / 0.4))
        screen.blit(flash, (0, 0))
