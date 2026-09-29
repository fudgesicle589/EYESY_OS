# Sunburst
# A retro sunburst of bold rays that step round on the beat, with a counter-rotating inner burst
# and a thumping core.
# Turn any knob and the picture reacts at once. Tap the `0` key on the beat to sync it by hand
# (on the real device it also locks to the audio kick).
#
# Knob convention (same in every mode):
#   knob1 = size            (size of the core and inner burst)
#   knob2 = main motion     (tempo, 30 to 120 BPM)
#   knob3 = extra detail    (number of rays, 6 to 48)
#   knob4 = foreground color (hue of the rays)
#   knob5 = bonus control    (curl: bend the rays into a pinwheel spiral)
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
    cx, cy = xres / 2.0, yres / 2.0
    far = math.hypot(xres, yres)
    rays = 2 * (3 + int(eyesy.knob3 * 21.99))                 # an even number, 6..48
    wedge = 2 * math.pi / rays
    step = ease(clamp(frac * 1.4))
    rot = (math.floor(beats) + step) * wedge + energy * 0.5 * math.sin(beats * 4)
    light = hsv(h0, 0.85, 0.95)
    curl = eyesy.knob5 * 3.2                                  # how far the rays bend by the time they reach the edge
    for i in range(0, rays, 2):                               # the big rays: every other wedge
        a = rot + i * wedge
        left, right = [], []
        for j in range(1, 11):
            fr = j / 10.0
            off = curl * fr * fr
            left.append((cx + far * fr * math.cos(a + off), cy + far * fr * math.sin(a + off)))
            right.append((cx + far * fr * math.cos(a + wedge + off), cy + far * fr * math.sin(a + wedge + off)))
        pygame.draw.polygon(screen, light, [(cx, cy)] + left + right[::-1])
    r1 = min(xres, yres) * (0.16 + 0.22 * eyesy.knob1) * (1.0 + 0.10 * kick)
    pygame.draw.circle(screen, bg, (int(cx), int(cy)), int(r1 * 1.08))                 # a clean disc for the inner burst
    rot2 = -rot * 1.5
    alt = hsv(h0 + 0.5, 0.75, 0.95)
    for i in range(0, rays, 2):                               # the inner burst turns the other way
        a = rot2 + i * wedge
        pts = [(cx, cy)] + [(cx + r1 * math.cos(a + wedge * j / 6), cy + r1 * math.sin(a + wedge * j / 6)) for j in range(7)]
        pygame.draw.polygon(screen, alt, pts)
    pygame.draw.circle(screen, hsv(h0, 0.2, 1.0), (int(cx), int(cy)), int(r1 * (0.32 + 0.16 * kick)))
    pygame.draw.circle(screen, hsv(h0 + 0.5, 0.9, 1.0), (int(cx), int(cy)), int(r1 * 0.12))
