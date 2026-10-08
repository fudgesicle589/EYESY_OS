# Wire Orb
# A glowing wireframe globe that you can throw around. Every knob you turn whips the globe: turn knobs one way and
# it spins up that way, turn them back and it reverses (the tempo knob tips it over); it keeps spinning on its
# own momentum and slowly settles. On top of that it snaps an eighth-turn on every beat, swells on the kick, and the
# wobble knob turns it into a big lumpy, breathing blob. Tap the `0` key on the beat to sync it
# (on the real device it also locks to the audio kick).
#
# Knob convention (same in every mode):
#   knob1 = size             (size of the globe; also spins it left / right as you turn it)
#   knob2 = main motion      (tempo, 30 to 120 BPM; tips the globe over as you turn it)
#   knob3 = extra detail     (number of rings, 4 to 16; also spins it)
#   knob4 = foreground color (hue of the globe; the color also rolls on while you turn it)
#   knob5 = bonus control    (wobble: from a perfect ball to a big lumpy, breathing blob)
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



_ring_cols = {"h0": None, "d": {}}
_trig_tab = {}
def _trig(n):
    t = _trig_tab.get(n)
    if t is None:
        t = _trig_tab[n] = ([math.cos(2 * math.pi * s / n) for s in range(n + 1)], [math.sin(2 * math.pi * s / n) for s in range(n + 1)])
    return t

def _ring_color(h0, hue, cls):
    """the colour of a ring at one of four depth levels; kept until the colour moves"""
    key = round(h0, 2)
    if _ring_cols["h0"] != key:
        _ring_cols["h0"], _ring_cols["d"] = key, {}
    ck = (round(hue, 3), cls)
    c = _ring_cols["d"].get(ck)
    if c is None:
        if len(_ring_cols["d"]) > 400:
            _ring_cols["d"].clear()
        depth = (cls + 0.5) / 4.0
        c = _ring_cols["d"][ck] = hsv(hue, 0.85 - 0.3 * depth, 0.25 + 0.75 * depth)
    return c

def _draw(screen, eyesy):
    full_x, full_y = eyesy.xres, eyesy.yres
    rs = render_scale()
    xres, yres = int(full_x * rs), int(full_y * rs)
    dt, beats, frac, kick, energy = beat_clock(eyesy)
    h0, bg = colors(eyesy)
    A = _state["aux"]
    ks = (eyesy.knob1, eyesy.knob2, eyesy.knob3, eyesy.knob4, eyesy.knob5)
    prev = A.get("ks")
    A["ks"] = ks
    d = [0.0] * 5 if prev is None else [ks[i] - prev[i] for i in range(5)]
    # every knob you turn whips the globe, and the direction you turn it is the direction it spins
    A["wy"] = (A.get("wy", 0.0) + (d[0] + d[2] + d[4]) * 40.0) * math.exp(-dt * 0.9)      # spin about the vertical axis (rad/s)
    A["wx"] = (A.get("wx", 0.0) + d[1] * 40.0) * math.exp(-dt * 0.9)                        # tip it over
    A["ay"] = A.get("ay", 0.0) + A["wy"] * dt
    A["ax"] = A.get("ax", 0.0) + A["wx"] * dt
    A["hue"] = A.get("hue", 0.0) + d[3] * 1.5                                              # the colour rolls on while you turn the knob
    h0 = h0 + A["hue"]
    A["hue"] *= math.exp(-dt * 0.3)
    canvas = canvas_for(eyesy, bg, 75, (xres, yres))
    q = _lod["q"]
    n = 4 + int(eyesy.knob3 * 12.99)
    n = max(4, int(n * (0.6 + 0.4 * q)))
    segs = 40 if q > 0.7 else 24
    R = min(xres, yres) * 0.42 * (0.25 + eyesy.knob1 * 1.0) * (1.0 + 0.16 * kick)
    ay = (math.floor(beats) + ease(clamp(frac * 1.5))) * math.pi / 4 + A["ay"]
    ax = 0.45 + 0.25 * math.sin(beats * 0.2) + A["ax"]
    ca, sa, cx_, sx_ = math.cos(ay), math.sin(ay), math.cos(ax), math.sin(ax)
    cx, cy = xres / 2.0, yres / 2.0
    F, D = 3.2, 4.0
    kk = R * F * 0.75
    lump = 0.9 * eyesy.knob5 * (1.0 + 0.5 * kick)
    b1, b2 = beats * 1.5, beats * 0.7                            # the lumps drift over time
    cb1, sb1, cb2, sb2 = math.cos(b1), math.sin(b1), math.cos(b2), math.sin(b2)
    ct, st = _trig(segs)
    lines = pygame.draw.lines
    sqrt = math.sqrt
    def project(x, y, z):
        if lump > 0.005:                                         # a lumpy, breathing surface (worked out without any trig calls)
            rho2 = x * x + z * z
            if rho2 > 1e-8:
                rho = sqrt(rho2)
                cl, sl = x / rho, z / rho
                s3 = 3 * sl - 4 * sl * sl * sl                  # sin(3 * longitude)
                c3 = 4 * cl * cl * cl - 3 * cl                  # cos(3 * longitude)
                c2l = 1 - 2 * y * y                             # cos(2 * latitude)
                s2l = 2 * y * rho                               # sin(2 * latitude)
                fr = 1.0 + lump * (s3 * cb1 + c3 * sb1) * (c2l * cb2 - s2l * sb2)
                x, y, z = x * fr, y * fr, z * fr
        x2, z2 = x * ca + z * sa, -x * sa + z * ca
        y2, z3 = y * cx_ - z2 * sx_, y * sx_ + z2 * cx_
        k = kk / (D + z3)
        return cx + x2 * k, cy + y2 * k, z3
    for kind in (0, 1):                                          # 0: rings of latitude, 1: rings of longitude
        for r in range(n):
            u = (r + 0.5) / n
            hue = h0 + u * 0.4 + kind * 0.5
            pts, zs = [], []
            if kind == 0:
                phi = math.pi * u
                sp, cp = math.sin(phi), math.cos(phi)
                for s in range(segs + 1):
                    px, py, pz = project(sp * ct[s], cp, sp * st[s])
                    pts.append((px, py)); zs.append(pz)
            else:
                th = math.pi * u
                cth, sth = math.cos(th), math.sin(th)
                for s in range(segs + 1):
                    px, py, pz = project(ct[s] * cth, st[s], ct[s] * sth)
                    pts.append((px, py)); zs.append(pz)
            run, cls_run = [pts[0]], None                        # a few long runs of one shade (dim at the back, bright at the front)
            for s in range(segs):
                z = (zs[s] + zs[s + 1]) * 0.5
                cls = int((z + 1.0) * 2.0)
                cls = 0 if cls < 0 else (3 if cls > 3 else cls)
                if cls_run is None:
                    cls_run = cls
                if cls != cls_run:
                    if len(run) > 1:
                        lines(canvas, _ring_color(h0, hue, cls_run), False, run, 2 if cls_run >= 2 else 1)
                    run, cls_run = [pts[s]], cls
                run.append(pts[s + 1])
            if len(run) > 1:
                lines(canvas, _ring_color(h0, hue, cls_run), False, run, 2 if cls_run >= 2 else 1)
    pygame.draw.circle(canvas, hsv(h0 + 0.5, 0.4, 1.0), (int(cx), int(cy)), max(2, int((6 + 10 * kick) * rs)))
    if rs == 1.0:
        screen.blit(canvas, (0, 0))
    else:
        pygame.transform.scale(canvas, (full_x, full_y), screen)
