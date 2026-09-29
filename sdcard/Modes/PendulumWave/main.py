# Pendulum Wave
# A row of pendulums, each a hair faster than the last. They drift out of step into snakes and waves,
# and the drift knob changes how quickly they scatter.
# Turn any knob and the picture reacts at once. Tap the `0` key on the beat to sync it by hand
# (on the real device it also locks to the audio kick).
#
# Knob convention (same in every mode):
#   knob1 = size            (swing width and bob size)
#   knob2 = main motion     (tempo, 30 to 120 BPM)
#   knob3 = extra detail    (number of pendulums, 8 to 40)
#   knob4 = foreground color (hue of the bobs)
#   knob5 = bonus control    (drift: how fast neighbouring pendulums fall out of step)
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
    canvas = canvas_for(eyesy, bg, 38)
    n = 8 + int(eyesy.knob3 * 32.99)
    pivot_y = yres * 0.06
    L = yres * 0.60
    theta_max = (0.25 + eyesy.knob1 * 0.65) * (1.0 + 0.5 * energy)
    drift = 0.05 + 0.75 * eyesy.knob5                        # tiny drift = slow, wide waves; big drift = a tight, busy ripple
    pygame.draw.line(canvas, hsv(h0 + 0.5, 0.4, 0.6), (xres * 0.03, pivot_y), (xres * 0.97, pivot_y), 3)
    for i in range(n):
        x0 = xres * (0.06 + 0.88 * i / max(n - 1, 1))
        phase = 2 * math.pi * (3.0 + i * drift) * beats / 16.0
        th = theta_max * math.sin(phase)
        bx, by = x0 + L * math.sin(th), pivot_y + L * math.cos(th)
        col = hsv(h0 + i / n * 0.6, 0.85, 1.0)
        pygame.draw.line(canvas, hsv(h0 + i / n * 0.6, 0.5, 0.45), (x0, pivot_y), (bx, by), 1)
        pygame.draw.circle(canvas, col, (int(bx), int(by)), int((6 + 10 * eyesy.knob1) * (1.0 + 0.45 * kick)))
        pygame.draw.circle(canvas, hsv(h0 + i / n * 0.6, 0.25, 1.0), (int(bx), int(by)), max(2, int(3 + 4 * eyesy.knob1)))
        pygame.draw.circle(canvas, hsv(h0 + 0.5, 0.4, 0.5), (int(x0), int(pivot_y + L)), 2)              # the resting line
    screen.blit(canvas, (0, 0))
