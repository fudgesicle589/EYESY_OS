# Prism Spin: nested wireframe cubes that snap a quarter-turn on every beat, joined by glowing edges into a
# spinning hypercube. Add cubes for depth, change the tempo, blow them up. Tap `0` to snap one by hand.
#
# Knob convention (same in every mode):
#   knob1 = size            (how big the cubes are)
#   knob2 = main motion     (tempo, 30 to 120 BPM; the turns get snappier too)
#   knob3 = extra detail    (number of nested cubes, 1 to 8)
#   knob4 = foreground color (hue that steps from cube to cube)
#   knob5 = background color (also the color the trails fade into)
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

VERTS = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
EDGES = [(a, b) for a in range(8) for b in range(a + 1, 8) if sum(1 for k in range(3) if VERTS[a][k] != VERTS[b][k]) == 1]

def ease(t): return t * t * (3 - 2 * t)

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
    fade.set_alpha(95)
    canvas.blit(fade, (0, 0))

    fg = eyesy.color_picker(eyesy.knob4)
    h0 = colorsys.rgb_to_hsv(fg[0] / 255.0, fg[1] / 255.0, fg[2] / 255.0)[0]
    n = 1 + int(eyesy.knob3 * 7.99)
    size = min(xres, yres) * (0.10 + eyesy.knob1 * 0.28)
    snap = ease(clamp(frac * 1.6))                            # the turn happens in the first part of each beat
    turn = (math.floor(beats) + snap) * math.pi / 2 + beats * 0.10      # a snap on every beat, plus a slow drift in between
    wob = energy * 0.8 * math.sin(beats * 9.0)                          # touching a knob wobbles the whole cube
    cx, cy = xres / 2.0, yres / 2.0
    D = 5.0
    f = 3.6

    levels = []
    for k in range(n):
        s = size * (1.0 - 0.75 * k / max(n, 1)) * (1.0 + 0.16 * kick)
        sgn = 1 if k % 2 == 0 else -1
        ay = turn * sgn + k * 0.32 + wob
        ax = turn * 0.5 * sgn + 0.5 + k * 0.21 + wob * 0.6
        cy_, sy_, cx_, sx_ = math.cos(ay), math.sin(ay), math.cos(ax), math.sin(ax)
        pts = []
        for (x, y, z) in VERTS:
            x2, z2 = x * cy_ + z * sy_, -x * sy_ + z * cy_
            y2, z3 = y * cx_ - z2 * sx_, y * sx_ + z2 * cx_
            d = D + z3
            pts.append((cx + s * x2 * f / d * 1.6, cy + s * y2 * f / d * 1.6))
        levels.append(pts)

    thick = 2 + int(eyesy.knob1 * 4)
    for k, pts in enumerate(levels):
        hue = h0 + k * 0.09
        for a, b in EDGES:
            pygame.draw.line(canvas, hsv(hue, 0.9, 0.55), pts[a], pts[b], thick + 5)      # glow
            pygame.draw.line(canvas, hsv(hue, 0.5, 1.0), pts[a], pts[b], thick)           # bright edge
        for p in pts:
            pygame.draw.circle(canvas, hsv(hue + 0.5, 0.4, 1.0), (int(p[0]), int(p[1])), thick + 2)
        if k + 1 < len(levels):                               # join each cube to the next: a hypercube
            for a in range(8):
                pygame.draw.line(canvas, hsv(hue + 0.05, 0.7, 0.7), pts[a], levels[k + 1][a], max(1, thick - 1))
    screen.blit(canvas, (0, 0))
