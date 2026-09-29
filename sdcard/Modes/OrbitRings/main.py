# Orbit Rings
# Concentric rings of dots. On every beat each ring steps one notch, alternating directions,
# and lines link the rings together like a machine.
# Turn any knob and the picture reacts at once. Tap the `0` key on the beat to sync it by hand
# (on the real device it also locks to the audio kick).
#
# Knob convention (same in every mode):
#   knob1 = size            (dot size)
#   knob2 = main motion     (tempo, 30 to 120 BPM)
#   knob3 = extra detail    (number of rings, 2 to 9)
#   knob4 = foreground color (hue of the rings)
#   knob5 = bonus control    (tilt: lay the rings over into ellipses, like a gyroscope)
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
    canvas = canvas_for(eyesy, bg, 55)
    cx, cy = xres / 2.0, yres / 2.0
    rings = 2 + int(eyesy.knob3 * 7.99)
    maxr = min(xres, yres) * 0.46
    dot = (4 + 12 * eyesy.knob1) * (1.0 + 0.5 * kick)
    step = ease(clamp(frac * 1.5))                            # each beat: a quick eased step
    squash = max(0.18, math.cos(eyesy.knob5 * 1.35))          # 1 = flat on, small = the rings lie almost on their side
    spin = beats * 0.10 if eyesy.knob5 > 0.05 else 0.0        # the tilted stack slowly turns
    cs, sn = math.cos(spin), math.sin(spin)
    def place(r, a):
        dx, dy = r * math.cos(a), r * math.sin(a) * squash
        return (cx + dx * cs - dy * sn, cy + dx * sn + dy * cs)
    layers = []
    for k in range(rings):
        r = maxr * (k + 1) / rings
        m = 3 + k * 2
        dirn = 1 if k % 2 == 0 else -1
        a0 = dirn * (math.floor(beats) + step) * 2 * math.pi / m + k * 0.4 + energy * 0.8 * math.sin(beats * 5 + k)
        pts = [place(r, a0 + 2 * math.pi * j / m) for j in range(m)]
        layers.append(pts)
        pygame.draw.polygon(canvas, hsv(h0 + k / rings * 0.7, 0.6, 0.30), [place(r, 2 * math.pi * j / 72) for j in range(72)], 1)
        pygame.draw.polygon(canvas, hsv(h0 + k / rings * 0.7, 0.8, 0.55), pts, 2)
    for k in range(rings - 1):                                # spokes linking neighbouring rings
        a, b = layers[k], layers[k + 1]
        for j, p in enumerate(a):
            q = b[(j * len(b)) // len(a)]
            pygame.draw.line(canvas, hsv(h0 + k / rings * 0.7 + 0.1, 0.6, 0.7), p, q, 1)
    for k, pts in enumerate(layers):
        for p in pts:
            pygame.draw.circle(canvas, hsv(h0 + k / rings * 0.7, 0.85, 1.0), (int(p[0]), int(p[1])), int(dot))
            pygame.draw.circle(canvas, hsv(h0 + k / rings * 0.7, 0.2, 1.0), (int(p[0]), int(p[1])), max(2, int(dot * 0.4)))
    pygame.draw.circle(canvas, hsv(h0 + 0.5, 0.5, 1.0), (int(cx), int(cy)), int(dot * 1.6))
    screen.blit(canvas, (0, 0))
