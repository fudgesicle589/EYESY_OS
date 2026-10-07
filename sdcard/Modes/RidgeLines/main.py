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
    """hue/saturation/value (0..1) to an (r, g, b) tuple; written out by hand because it is called thousands of times a frame"""
    h = (h % 1.0) * 6.0
    s = 0.0 if s < 0.0 else (1.0 if s > 1.0 else s)
    v = 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)
    i = int(h)
    f = h - i
    v255 = v * 255.0
    p = v255 * (1.0 - s)
    q = v255 * (1.0 - f * s)
    t = v255 * (1.0 - (1.0 - f) * s)
    if i == 0: r, g, b = v255, t, p
    elif i == 1: r, g, b = q, v255, p
    elif i == 2: r, g, b = p, v255, t
    elif i == 3: r, g, b = p, q, v255
    elif i == 4: r, g, b = t, p, v255
    else: r, g, b = v255, p, q
    return (int(r), int(g), int(b))

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

# ---- adaptive quality: if this pattern runs slowly (say, on a Raspberry Pi) it quietly draws less detail ----
_lod = {"q": 1.0, "avg": 0.0, "t0": 0.0, "rs": 1.0, "calm": 0}
LOD_BUDGET = 0.016                                             # seconds of drawing per frame to stay under

def lod_start():
    _lod["t0"] = time.perf_counter()

def lod_end():
    dt = time.perf_counter() - _lod["t0"]
    _lod["avg"] = _lod["avg"] * 0.9 + dt * 0.1 if _lod["avg"] else dt
    if _lod["avg"] > LOD_BUDGET:
        _lod["q"] = max(0.2, _lod["q"] - 0.04)
    elif _lod["avg"] < LOD_BUDGET * 0.55:
        _lod["q"] = min(1.0, _lod["q"] + 0.01)
    _lod["calm"] = _lod["calm"] + 1 if _lod["avg"] < LOD_BUDGET * 0.4 else 0

def render_scale():
    """1.0 normally; 0.5 (a quarter of the pixels) if the machine is really struggling, until it has coped easily for ~10 seconds"""
    if _lod["rs"] == 1.0 and _lod["q"] < 0.4:
        _lod["rs"], _lod["calm"] = 0.5, 0
    elif _lod["rs"] == 0.5 and _lod["calm"] > 300:
        _lod["rs"], _lod["calm"] = 1.0, 0
    return _lod["rs"]

def draw(screen, eyesy):
    lod_start()
    _draw(screen, eyesy)
    lod_end()

_tab = {}

def _tables(P, x_l, x_r):
    """everything that depends only on the point index, worked out once and reused every frame"""
    key = (P, round(x_l), round(x_r))
    t = _tab.get(key)
    if t is None:
        u = [p / (P - 1.0) for p in range(P)]
        t = _tab[key] = {
            "xs": [x_l + (x_r - x_l) * v for v in u],
            "u": u,
            "edge": [math.sin(math.pi * v) ** 0.8 for v in u],           # keeps the ends flat
            "g2": [math.exp(-((v - 0.5) / 0.13) ** 2) for v in u],
            "s26": [math.sin(v * 26) for v in u], "c26": [math.cos(v * 26) for v in u],
            "s47": [math.sin(v * 47) for v in u], "c47": [math.cos(v * 47) for v in u],
            "s83": [math.sin(v * 83) for v in u], "c83": [math.cos(v * 83) for v in u],
        }
    if len(_tab) > 12:                                     # the screen size rarely changes, but never let this grow
        for k in list(_tab)[:-4]:
            del _tab[k]
    return t

def _draw(screen, eyesy):
    xres, yres = eyesy.xres, eyesy.yres
    dt, beats, frac, kick, energy = beat_clock(eyesy)
    h0, bg = colors(eyesy)
    screen.fill(bg)
    q = _lod["q"]
    L = 8 + int(eyesy.knob3 * 32.99)
    L = max(6, int(L * (0.55 + 0.45 * q)))                    # fewer lines when the machine is struggling
    P = int(56 + 104 * q)                                      # and fewer points along each line
    A = yres * (0.05 + 0.24 * eyesy.knob1) * (1.0 + 0.5 * energy)
    rough = eyesy.knob5 * 1.2
    x_l, x_r = xres * 0.08, xres * 0.92
    T = _tables(P, x_l, x_r)
    xs, u_, edge, g2 = T["xs"], T["u"], T["edge"], T["g2"]
    s26, c26, s47, c47, s83, c83 = T["s26"], T["c26"], T["s47"], T["c47"], T["s83"], T["c83"]
    t7 = [math.sin(v * 7 - beats * 0.5) for v in u_]           # the same for every line, so once per frame
    exp, sin, cos = math.exp, math.sin, math.cos
    rp_gain = 0.5 + energy
    jr = 0.5 * rough
    fill, lines = pygame.draw.polygon, pygame.draw.lines
    for i in range(L):                                         # top (far) to bottom (near)
        base = yres * (0.18 + 0.76 * i / max(L - 1, 1))
        cen = 0.5 + 0.28 * sin(beats * 0.35 + i * 0.16)
        ph1 = i * 0.8 + beats * 1.6
        ph2 = i * 1.7 + beats * 2.0
        ph3 = -(i * 0.9 + beats * 1.3)
        c1, s1 = cos(ph1), sin(ph1)
        c2, s2 = cos(ph2), sin(ph2)
        c3, s3 = cos(ph3), sin(ph3)
        kf = 0.55 * kick * (1.0 - i / (L * 1.4))
        pts = []
        add = pts.append
        for p in range(P):
            z = (u_[p] - cen) * 9.0909
            bump = 0.65 * exp(-z * z) if -3.6 < z < 3.6 else 0.0
            bump += kf * g2[p]
            rip = 0.22 * (s26[p] * c1 + c26[p] * s1) * t7[p]
            if rip < 0.0:
                rip = 0.0
            jag = jr * ((s47[p] * c2 + c47[p] * s2) + (s83[p] * c3 + c83[p] * s3)) if jr else 0.0
            add((xs[p], base - A * edge[p] * (bump + rip * rp_gain + jag)))
        fill(screen, bg, [(x_l, base + 3)] + pts + [(x_r, base + 3)])       # hides the lines behind this one
        lines(screen, hsv(h0 + i / L * 0.5, 0.75, 0.45 + 0.55 * i / L), False, pts, 2)
