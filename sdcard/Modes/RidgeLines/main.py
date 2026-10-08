# Ridge Lines
# Stacked scan lines like a pulsar plot: the front line is the live sound spectrum (bass in the middle, treble
# toward the edges) and every few beats it is pushed back into the pile, so you see the music's recent history
# as rolling mountains. On the real device it listens to the audio input; with nothing plugged in it plays its
# own house beat. Tap the `0` key on the beat to sync the demo beat.
#
# Knob convention (same in every mode):
#   knob1 = size             (how tall the ridges rise)
#   knob2 = main motion      (tempo of the demo beat; also how fast the lines scroll back)
#   knob3 = extra detail     (number of lines, 8 to 40: how much history you see)
#   knob4 = foreground color (hue of the lines)
#   knob5 = bonus control    (roughness: smooth rolling hills up to jagged, stormy peaks)
import colorsys
import math
import random
import time
from operator import mul
import pygame

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))
def ease(t): return t * t * (3 - 2 * t)
def lerp(a, b, t): return a + (b - a) * t

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

_state = {"beats": 0.0, "last": None, "prev": None, "energy": 0.0, "canvas": None, "fade": None, "size": None, "aux": {},
          "kick": 0.0, "bpm": 100.0, "tap": None}
_au = {"gain": 1500.0, "level": 0.0, "avg": 0.0, "pulse": 0.0, "live": False, "loud_t": -99.0, "ref": 5000.0, "tabs": {}}

# ---------------------------------------------------------------- audio
def audio_update(eyesy, dt, now):
    """peak level of the incoming audio (auto-gained to 0..1), an onset 'pulse' on every hit, and whether any real audio is arriving"""
    try:
        pk = max(abs(v) for v in eyesy.audio_in[:100])
    except Exception:
        pk = 0
    if pk > 40:
        _au["loud_t"] = now
    _au["live"] = now - _au["loud_t"] < 1.5
    _au["gain"] = max(_au["gain"] * 0.999, pk, 400.0)
    level = pk / _au["gain"] if _au["live"] else 0.0
    _au["level"] = max(level, _au["level"] * 0.85)
    onset = clamp((level - _au["avg"] * 1.25) * 3.0)
    _au["avg"] = _au["avg"] * 0.95 + level * 0.05
    _au["pulse"] = max(onset, _au["pulse"] * math.exp(-dt * 6.0))

def spectrum(eyesy, n):
    """n bands from low to high pitch, each 0..1. Real audio: a small DFT of the 100 input samples, auto-gained.
    With no audio plugged in (like on a laptop) it plays a house-style demo beat driven by the beat clock instead."""
    if _au["live"]:
        a = eyesy.audio_in[:100]
        tab = _au["tabs"].get(n)
        if tab is None:
            if len(_au["tabs"]) > 6:
                _au["tabs"].clear()
            tab = []
            for i in range(n):
                k = 38.0 ** (i / float(max(n - 1, 1)))                  # 1 to 38 cycles across the buffer, spaced like pitch
                tab.append(([(0.5 - 0.5 * math.cos(2 * math.pi * j / 99.0)) * math.cos(2 * math.pi * k * j / 100.0) for j in range(100)],
                            [(0.5 - 0.5 * math.cos(2 * math.pi * j / 99.0)) * math.sin(2 * math.pi * k * j / 100.0) for j in range(100)]))
            _au["tabs"][n] = tab
        mags = []
        for i, (ct, st) in enumerate(tab):
            re, im = sum(map(mul, a, ct)), sum(map(mul, a, st))
            mags.append(math.sqrt(re * re + im * im) * (0.5 + 1.8 * i / float(max(n - 1, 1))))      # tilted up so the highs show too
        _au["ref"] = max(_au["ref"] * 0.995, max(mags), 5000.0)
        ref = _au["ref"]
        out = [min(1.0, (m / ref) ** 0.6) for m in mags]
        e = _state["energy"]
        if e > 0.02:                                             # turning a knob still shakes the bars even over music
            for i in range(n):
                out[i] = max(out[i], e * 0.7 * (0.5 + 0.5 * math.sin(i * 12.9898 + _state["beats"] * 5.0)))
        return out
    b, kick, e = _state["beats"], _state["kick"], _state["energy"]
    hat = (1.0 - ((b * 2.0) % 1.0)) ** 2
    out = []
    for i in range(n):
        x = i / float(max(n - 1, 1))
        bass = kick * (1.0 - x) ** 1.5
        wave = 0.5 + 0.5 * math.sin(x * 9.0 - b * 2.4) * math.sin(x * 3.0 + b * 0.7)
        jit = 0.5 + 0.5 * math.sin(i * 12.9898 + b * 5.0)
        out.append(clamp(0.10 + 0.85 * bass + 0.5 * hat * x * 0.8 + 0.35 * wave + e * 0.6 * jit))
    return out

# ---------------------------------------------------------------- the beat
def beat_clock(eyesy, bpm=None):
    """a beat counter at the knob's tempo. An audio hit (or the 0 key) snaps it to the next beat and, tapped a few times,
    also sets the tempo. Turning any knob adds a burst of 'energy' that fades over about a second.
    Returns dt, beats, frac (0..1 through the beat), kick (1 on the beat, fading), energy."""
    now = time.time()
    if _state["last"] is None:
        _state["last"] = now
    dt = min(now - _state["last"], 0.1)
    _state["last"] = now
    audio_update(eyesy, dt, now)
    if bpm is None:
        bpm = 30 + eyesy.knob2 * 90
    elif bpm == "tap":
        bpm = _state["bpm"]
    _state["beats"] += dt * bpm / 60.0
    if getattr(eyesy, "trig", False):
        tp = _state["tap"]
        if tp is not None and 0.25 < now - tp < 2.0:
            _state["bpm"] = clamp(lerp(_state["bpm"], 60.0 / (now - tp), 0.5), 40.0, 180.0)
        _state["tap"] = now
        _state["beats"] = math.floor(_state["beats"]) + 1.0
    ks = (eyesy.knob1, eyesy.knob2, eyesy.knob3, eyesy.knob4, eyesy.knob5)
    prev = _state["prev"]
    move = 0.0 if prev is None else sum(abs(a - b) for a, b in zip(ks, prev))
    _state["prev"] = ks
    _state["energy"] = max(_state["energy"] * math.exp(-dt * 2.5), min(1.0, move * 30.0))
    beats = _state["beats"]
    frac = beats % 1.0
    kick = max((1.0 - frac) ** 3, _au["pulse"], _state["energy"] * 0.9)
    _state["kick"] = kick
    return dt, beats, frac, kick, _state["energy"]

def colors(eyesy):
    fg = eyesy.color_picker(eyesy.knob4)
    h0 = colorsys.rgb_to_hsv(fg[0] / 255.0, fg[1] / 255.0, fg[2] / 255.0)[0]
    bg = hsv(h0 + 0.55, 0.65, 0.10)
    return h0, bg

def canvas_for(eyesy, bg, alpha, size=None):
    """a persistent surface that fades toward the background each frame, for glowing trails"""
    xres, yres = size if size else (eyesy.xres, eyesy.yres)
    if _state["size"] != (xres, yres):
        _state["size"] = (xres, yres)
        _state["canvas"] = pygame.Surface((xres, yres))
        _state["canvas"].fill(bg)
        _state["fade"] = pygame.Surface((xres, yres))
    _state["fade"].fill(bg)
    _state["fade"].set_alpha(alpha)
    _state["canvas"].blit(_state["fade"], (0, 0))
    return _state["canvas"]

# ---------------------------------------------------------------- adaptive quality (Raspberry Pi)
_lod = {"q": 1.0, "avg": 0.0, "t0": 0.0, "rs": 1.0, "calm": 0}
LOD_BUDGET = 0.016

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

def setup(screen, eyesy):
    pass

def draw(screen, eyesy):
    lod_start()
    _draw(screen, eyesy)
    lod_end()

NB = 40                                                        # spectrum bands across half of the width


_tab = {}
def _tables(P, x_l, x_r):
    key = (P, round(x_l), round(x_r))
    t = _tab.get(key)
    if t is None:
        u = [p / (P - 1.0) for p in range(P)]
        idx = [abs(2 * v - 1.0) * (NB - 1) for v in u]            # centre = bass, edges = treble
        t = _tab[key] = {"xs": [x_l + (x_r - x_l) * v for v in u], "u": u, "edge": [math.sin(math.pi * v) ** 0.7 for v in u],
                         "i0": [int(v) for v in idx], "fr": [v - int(v) for v in idx],
                         "s47": [math.sin(v * 47) for v in u], "c47": [math.cos(v * 47) for v in u],
                         "s83": [math.sin(v * 83) for v in u], "c83": [math.cos(v * 83) for v in u]}
    if len(_tab) > 12:
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
    L = max(6, int(L * (0.55 + 0.45 * q)))
    P = int(60 + 100 * q)
    A = yres * (0.05 + 0.30 * eyesy.knob1) * (1.0 + 0.3 * energy)
    rough = eyesy.knob5 * 0.25
    x_l, x_r = xres * 0.06, xres * 0.94
    T = _tables(P, x_l, x_r)
    xs, edge, i0, fr = T["xs"], T["edge"], T["i0"], T["fr"]
    s47, c47, s83, c83 = T["s47"], T["c47"], T["s83"], T["c83"]
    sp = spectrum(eyesy, NB)
    live = _state["aux"].setdefault("live", [0.0] * NB)
    for i in range(NB):                                         # the front line follows the sound, rising fast and falling smoothly
        live[i] = max(sp[i], live[i] - dt * 2.5)
    hist = _state["aux"].setdefault("hist", [])
    acc = _state["aux"].get("acc", 0.0) + dt * (30 + eyesy.knob2 * 90) / 60.0 * 3.0        # about 3 lines pushed back per beat
    if acc >= 1.0:
        acc = 0.0
        hist.insert(0, list(live))
        del hist[48:]
    _state["aux"]["acc"] = acc
    rows = [live] + hist                                        # newest first
    fill, lines = pygame.draw.polygon, pygame.draw.lines
    sin, cos = math.sin, math.cos
    for i in range(L - 1, -1, -1):                              # oldest (top, far) to newest (bottom, near)
        row = rows[i] if i < len(rows) else rows[-1]
        base = yres * (0.22 + 0.74 * (L - 1 - i) / max(L - 1, 1))
        ph2, ph3 = i * 1.7 + beats * 2.0, -(i * 0.9 + beats * 1.3)
        c2, s2, c3, s3 = cos(ph2), sin(ph2), cos(ph3), sin(ph3)
        pts = []
        add = pts.append
        for p in range(P):
            k0 = i0[p]
            v = row[k0] + (row[k0 + 1 if k0 + 1 < NB else k0] - row[k0]) * fr[p]
            jag = rough * ((s47[p] * c2 + c47[p] * s2) + (s83[p] * c3 + c83[p] * s3)) * (0.3 + v)
            add((xs[p], base - A * edge[p] * (v * 1.6 + jag)))
        fill(screen, bg, [(x_l, base + 3)] + pts + [(x_r, base + 3)])       # hides the lines behind this one
        age = 1.0 - i / float(max(L - 1, 1))
        lines(screen, hsv(h0 + age * 0.5, 0.75 - 0.2 * (1.0 - age), 0.40 + 0.60 * age), False, pts, 2)
