# Laser Fan
# A laser show, steered like a real laser desk. Pick a scene: a fan of beams sweeping from the floor, two
# fans scissoring across each other, a starburst, a curtain of beams hanging from the ceiling rig, or all of
# them at once with strobes. Beams are thin and bright, sweep to the tempo and snap wide on every beat,
# and you choose the beat count, color and thickness. Tap the `0` key on the beat to sync it (on the real
# device it also locks to the audio kick).
#
# Knob convention (same in every mode):
#   knob1 = size             (beam thickness)
#   knob2 = main motion      (tempo, 30 to 120 BPM: also how fast the beams sweep)
#   knob3 = extra detail     (beams per fan, 2 to 24)
#   knob4 = foreground color (hue of the beams; each source is a different hue)
#   knob5 = bonus control    (scene: Fan, Scissors, Starburst, Curtain, Rave)
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

SCENES = ["Fan", "Scissors", "Starburst", "Curtain", "Rave"]

def scene_of(e): return int(e.knob5 * 4.99)


TAU = 2 * math.pi

def fan_beams(out, W, H, beats, n, snap, rate, up=True):
    """three sources on the floor, each throwing a fan that swings and snaps open on the beat"""
    s = beats * rate / 4.0
    for si, x in enumerate((0.2, 0.5, 0.8)):
        m = max(2, n if si == 1 else int(n * 0.7))
        sweep = 0.55 * math.sin(TAU * s + si * 1.2)
        spread = math.pi * (0.26 + 0.40 * snap)
        for j in range(m):
            u = j / float(m - 1) - 0.5
            out.append((W * x, H * 1.04, -math.pi / 2 + sweep + u * spread, si * 0.33, 1.0))

def curtain_beams(out, W, H, beats, n, snap, rate):
    """a ceiling rig: beams hang down and sway in a travelling wave"""
    s = beats * rate / 4.0
    srcs = 6
    m = max(1, n // 4)
    for si in range(srcs):
        base = math.pi / 2 + 0.75 * math.sin(TAU * s * 2 + si * 0.9) + 0.25 * snap * (1 if si % 2 else -1)
        for j in range(m):
            out.append((W * (si + 0.5) / srcs, -H * 0.04, base + (j - (m - 1) / 2.0) * 0.12, 0.15 + si * 0.11, 1.0))

def make_beams(scene, W, H, beats, n, snap):
    out = []
    s = beats / 4.0
    if scene == 0:
        fan_beams(out, W, H, beats, n, snap, 1.0)
    elif scene == 1:                                           # two fans scissoring over each other
        m = max(2, n)
        sw = 0.95 * math.sin(TAU * s)
        spread = math.pi * (0.14 + 0.16 * snap)
        for si, (x, sgn) in enumerate(((0.12, 1.0), (0.88, -1.0))):
            for j in range(m):
                u = j / float(m - 1) - 0.5
                out.append((W * x, H * 1.04, -math.pi / 2 + sgn * sw + u * spread, si * 0.5, 1.0))
    elif scene == 2:                                           # starburst from the middle
        m = min(48, max(6, n * 2))
        rot = s * math.pi + snap * 0.12
        for j in range(m):
            out.append((W * 0.5, H * 0.5, rot + TAU * j / m, (j % 3) * 0.17, (1.0 if j % 2 else 0.35 + 0.65 * snap)))
    elif scene == 3:
        curtain_beams(out, W, H, beats, n, snap, 1.0)
    else:                                                      # everything, twice as fast
        fan_beams(out, W, H, beats, max(3, n // 2), snap, 2.0)
        curtain_beams(out, W, H, beats, max(4, n // 2), snap, 2.0)
    return out

def _draw(screen, eyesy):
    full_x, full_y = eyesy.xres, eyesy.yres
    rs = render_scale()                                        # 0.5 if the machine is struggling: draw a quarter of the pixels
    xres, yres = int(full_x * rs), int(full_y * rs)
    dt, beats, frac, kick, energy = beat_clock(eyesy)
    h0, _ = colors(eyesy)
    bg = hsv(h0 + 0.6, 0.7, 0.045)
    canvas = canvas_for(eyesy, bg, 70, (xres, yres))
    q = _lod["q"]
    n = 2 + int(eyesy.knob3 * 22)
    n = max(2, int(n * (0.5 + 0.5 * q)))
    thick = max(1, int((1 + int(eyesy.knob1 * 5) + int(energy * 2)) * rs))
    snap = (1.0 - frac) ** 3                                   # 1 right on the beat, then relaxes
    scene = scene_of(eyesy)
    L = math.hypot(xres, yres) * 1.3
    beams = make_beams(scene, xres, yres, beats, n, max(snap, _au["pulse"]))
    line, circle = pygame.draw.line, pygame.draw.circle
    glow = q > 0.45
    seen = set()
    for i, (ox, oy, a, hs, lm) in enumerate(beams):
        ex, ey = ox + L * lm * math.cos(a), oy + L * lm * math.sin(a)
        hue = h0 + hs + (i % 5) * 0.015
        if glow:
            line(canvas, hsv(hue, 0.95, 0.30 + 0.25 * snap), (ox, oy), (ex, ey), thick + 5)            # soft haze around the beam
        line(canvas, hsv(hue, 0.55, 1.0), (ox, oy), (ex, ey), thick)                                  # hot core
        key = (int(ox), int(oy))
        if key not in seen:
            seen.add(key)
            circle(canvas, hsv(hue, 0.3, 1.0), key, max(3, int((8 + 22 * snap) * rs)))                  # the source flares
    if rs == 1.0:
        screen.blit(canvas, (0, 0))
    else:
        pygame.transform.scale(canvas, (full_x, full_y), screen)
    if scene == 4 and snap > 0.7 or (beats % 4.0) < 0.12 and snap > 0.6:                              # strobe on the bar line (and every hit in Rave)
        flash = _state.get("flash")
        if flash is None or flash.get_size() != (full_x, full_y):
            flash = _state["flash"] = pygame.Surface((full_x, full_y))
            flash.fill((255, 255, 255))
        flash.set_alpha(int(60 * (snap - 0.6) / 0.4))
        screen.blit(flash, (0, 0))
