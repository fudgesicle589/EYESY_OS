# Ridge Lines
# Stacked scan lines that rise into a glowing ridge, like a pulsar plot. A wave wanders across the lines
# and every beat pushes a big bump up the middle.
# Turn any knob and the picture reacts at once. Tap the `0` key on the beat to sync it by hand
# (on the real device it also locks to the audio kick).
#
# Knob convention (same in every mode):
#   knob1 = size            (how tall the ridges rise)
#   knob2 = main motion     (tempo, 30 to 120 BPM)
#   knob3 = extra detail    (number of lines, 8 to 40)
#   knob4 = foreground color (hue of the lines)
#   knob5 = bonus control    (roughness: smooth rolling hills up to jagged, stormy peaks)
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
    L = 8 + int(eyesy.knob3 * 32.99)
    A = yres * (0.05 + 0.24 * eyesy.knob1) * (1.0 + 0.5 * energy)
    P = 160
    rough = eyesy.knob5 * 1.2
    x_l, x_r = xres * 0.08, xres * 0.92
    for i in range(L):                                        # top (far) to bottom (near)
        base = yres * (0.18 + 0.76 * i / max(L - 1, 1))
        cen = 0.5 + 0.28 * math.sin(beats * 0.35 + i * 0.16)
        pts = []
        for p in range(P):
            u = p / (P - 1.0)
            edge = math.sin(math.pi * u) ** 0.8                # keep the ends flat
            bump = 0.65 * math.exp(-((u - cen) / 0.11) ** 2) + 0.55 * kick * math.exp(-((u - 0.5) / 0.13) ** 2) * (1.0 - i / (L * 1.4))
            ripple = 0.22 * math.sin(u * 26 + i * 0.8 + beats * 1.6) * math.sin(u * 7 - beats * 0.5)
            jag = 0.5 * rough * (math.sin(u * 47 + i * 1.7 + beats * 2.0) + math.sin(u * 83 - i * 0.9 - beats * 1.3))
            pts.append((x_l + (x_r - x_l) * u, base - A * edge * (bump + max(0.0, ripple) * (0.5 + energy) + jag)))
        poly = [(x_l, base + yres * 0.5)] + pts + [(x_r, base + yres * 0.5)]
        pygame.draw.polygon(screen, bg, poly)                  # hides the lines behind this one
        pygame.draw.lines(screen, hsv(h0 + i / L * 0.5, 0.75, 0.45 + 0.55 * i / L), False, pts, 2)
