# Hex Wave
# A honeycomb wall. Waves of light roll through it from a wandering centre, and every hex breathes with the wave.
# Turn any knob and the picture reacts at once. Tap the `0` key on the beat to sync it by hand
# (on the real device it also locks to the audio kick).
#
# Knob convention (same in every mode):
#   knob1 = size            (wavelength: big slow swells to tight ripples)
#   knob2 = main motion     (tempo, 30 to 120 BPM)
#   knob3 = extra detail    (hex size: a few huge hexes up to a fine honeycomb)
#   knob4 = foreground color (hue of the honeycomb)
#   knob5 = bonus control    (swirl: the waves curl into 0 to 6 spiral arms)
import colorsys
import math
import random
import time
import pygame

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))
def ease(t): return t * t * (3 - 2 * t)

def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, clamp(s), clamp(v))
    return (int(r * 255), int(g * 255), int(b * 255))

_state = {"beats": 0.0, "last": None, "prev": None, "energy": 0.0, "canvas": None, "fade": None, "size": None, "aux": {}}

def beat_clock(eyesy):
    """a beat counter at the knob's tempo; an audio hit (or the 0 key) snaps it to the next beat,
    and turning any knob adds a burst of 'energy' that fades over about a second"""
    now = time.time()
    if _state["last"] is None:
        _state["last"] = now
    dt = min(now - _state["last"], 0.1)
    _state["last"] = now
    bpm = 30 + eyesy.knob2 * 90
    _state["beats"] += dt * bpm / 60.0
    if getattr(eyesy, "trig", False):
        _state["beats"] = math.floor(_state["beats"]) + 1.0
    ks = (eyesy.knob1, eyesy.knob2, eyesy.knob3, eyesy.knob4, eyesy.knob5)
    prev = _state["prev"]
    move = 0.0 if prev is None else sum(abs(a - b) for a, b in zip(ks, prev))
    _state["prev"] = ks
    _state["energy"] = max(_state["energy"] * math.exp(-dt * 2.5), min(1.0, move * 30.0))
    beats = _state["beats"]
    frac = beats % 1.0
    kick = (1.0 - frac) ** 3
    try:
        level = clamp(max(abs(v) for v in eyesy.audio_in[:100]) / 30000.0)
    except Exception:
        level = 0.0
    energy = _state["energy"]
    return dt, beats, frac, max(kick, level, energy * 0.9), energy

def colors(eyesy):
    fg = eyesy.color_picker(eyesy.knob4)
    h0 = colorsys.rgb_to_hsv(fg[0] / 255.0, fg[1] / 255.0, fg[2] / 255.0)[0]
    bg = hsv(h0 + 0.55, 0.65, 0.10)                            # knob 5 is used for something more fun than the background
    return h0, bg

def canvas_for(eyesy, bg, alpha):
    """a persistent surface that fades toward the background each frame, for glowing trails"""
    xres, yres = eyesy.xres, eyesy.yres
    if _state["size"] != (xres, yres):
        _state["size"] = (xres, yres)
        _state["canvas"] = pygame.Surface((xres, yres))
        _state["canvas"].fill(bg)
        _state["fade"] = pygame.Surface((xres, yres))
    _state["fade"].fill(bg)
    _state["fade"].set_alpha(alpha)
    _state["canvas"].blit(_state["fade"], (0, 0))
    return _state["canvas"]

def setup(screen, eyesy):
    pass

def draw(screen, eyesy):
    xres, yres = eyesy.xres, eyesy.yres
    dt, beats, frac, kick, energy = beat_clock(eyesy)
    h0, bg = colors(eyesy)
    screen.fill(bg)
    r = yres / (5.0 + eyesy.knob3 * 20.0)
    w, h = r * math.sqrt(3), r * 1.5
    cols, rows = int(xres / w) + 2, int(yres / h) + 2
    wl = (0.12 + eyesy.knob1 * 0.75) * xres
    arms = int(eyesy.knob5 * 6.99)                            # 0 = plain rings, up to 6 spiral arms
    cx0 = xres / 2 + 0.25 * xres * math.sin(beats * 0.30)
    cy0 = yres / 2 + 0.25 * yres * math.sin(beats * 0.21 + 1.0)
    for row in range(rows):
        for col in range(cols):
            x = col * w + (row % 2) * w / 2 - w / 2
            y = row * h
            d = math.hypot(x - cx0, y - cy0)
            ang = math.atan2(y - cy0, x - cx0)
            v = 0.5 + 0.5 * math.sin(d * 2 * math.pi / wl - beats * math.pi + arms * ang)
            v2 = 0.5 + 0.5 * math.sin((x * 0.6 + y) * 2 * math.pi / (wl * 1.7) + beats * 0.8)
            mix2 = 0.35 - 0.05 * arms                            # the more spiral arms, the less the side wave competes with them
            val = clamp((1.0 - mix2) * v + mix2 * v2 + energy * 0.35 * math.sin(d * 0.03 - beats * 6.0))
            sc = clamp(0.30 + 0.62 * val + 0.12 * kick, 0.1, 1.0)
            pts = [(x + r * sc * math.cos(math.pi / 6 + k * math.pi / 3), y + r * sc * math.sin(math.pi / 6 + k * math.pi / 3)) for k in range(6)]
            pygame.draw.polygon(screen, hsv(h0 + val * 0.35 + d / xres * 0.2, 0.8, 0.25 + 0.75 * val), pts)
