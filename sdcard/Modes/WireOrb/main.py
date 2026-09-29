# Wire Orb
# A glowing wireframe globe that snaps an eighth-turn on every beat and swells on the kick.
# Add rings until it is a solid ball of light.
# Turn any knob and the picture reacts at once. Tap the `0` key on the beat to sync it by hand
# (on the real device it also locks to the audio kick).
#
# Knob convention (same in every mode):
#   knob1 = size            (size of the globe)
#   knob2 = main motion     (tempo, 30 to 120 BPM)
#   knob3 = extra detail    (number of rings, 4 to 16)
#   knob4 = foreground color (hue of the globe)
#   knob5 = bonus control    (wobble: turn the sphere into a lumpy, breathing blob)
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
    canvas = canvas_for(eyesy, bg, 75)
    n = 4 + int(eyesy.knob3 * 12.99)
    R = min(xres, yres) * 0.42 * (0.35 + eyesy.knob1 * 0.85) * (1.0 + 0.12 * kick)
    ay = (math.floor(beats) + ease(clamp(frac * 1.5))) * math.pi / 4 + beats * 0.05 + energy * 0.6 * math.sin(beats * 6)
    ax = 0.45 + 0.25 * math.sin(beats * 0.2)
    ca, sa, cx_, sx_ = math.cos(ay), math.sin(ay), math.cos(ax), math.sin(ax)
    cx, cy = xres / 2.0, yres / 2.0
    F = 3.2
    D = 4.0
    lump = 0.5 * eyesy.knob5
    def project(x, y, z):
        lon, lat = math.atan2(z, x), math.asin(clamp(y, -1.0, 1.0))
        fr = 1.0 + lump * math.sin(3 * lon + beats * 1.5) * math.cos(2 * lat + beats * 0.7)      # a lumpy, breathing surface
        x, y, z = x * fr, y * fr, z * fr
        x2, z2 = x * ca + z * sa, -x * sa + z * ca
        y2, z3 = y * cx_ - z2 * sx_, y * sx_ + z2 * cx_
        d = D + z3
        return cx + R * x2 * F / d * 0.75, cy + R * y2 * F / d * 0.75, z3
    segs = 40
    for kind in (0, 1):                                       # 0: rings of latitude, 1: rings of longitude
        for r in range(n):
            u = (r + 0.5) / n
            pts = []
            for s in range(segs + 1):
                t = 2 * math.pi * s / segs
                if kind == 0:
                    phi = math.pi * u
                    p = project(math.sin(phi) * math.cos(t), math.cos(phi), math.sin(phi) * math.sin(t))
                else:
                    th = math.pi * u
                    p = project(math.cos(t) * math.cos(th), math.sin(t), math.cos(t) * math.sin(th))
                pts.append(p)
            for s in range(segs):
                z = (pts[s][2] + pts[s + 1][2]) / 2.0
                depth = 0.5 + 0.5 * z                       # brighter toward the viewer
                col = hsv(h0 + u * 0.4 + kind * 0.5, 0.85 - 0.3 * depth, 0.25 + 0.75 * depth)
                pygame.draw.line(canvas, col, pts[s][:2], pts[s + 1][:2], 2 if depth > 0.5 else 1)
    pygame.draw.circle(canvas, hsv(h0 + 0.5, 0.4, 1.0), (int(cx), int(cy)), int(6 + 10 * kick))
    screen.blit(canvas, (0, 0))
