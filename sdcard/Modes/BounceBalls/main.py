# Bounce Balls
# Spinning shapes ricochet around the screen leaving glowing trails. Every beat they are kicked, they bounce
# off each other and the walls (each hit sends out a ripple), and the gravity knob flips the whole room:
# gravity down, floating in zero-g, or falling up to the ceiling. Tap the `0` key on the beat to sync it
# (on the real device it also locks to the audio kick); tap it a few times and the tempo follows you.
#
# Knob convention (same in every mode):
#   knob1 = size             (ball size, changes live)
#   knob2 = main motion      (tempo, 30 to 120 BPM)
#   knob3 = extra detail     (number of balls, 3 to 24; new balls pop in with a ripple)
#   knob4 = foreground color (hue of the balls)
#   knob5 = bonus control    (gravity: low = down, 0.4 = zero-g and the beat kicks them outward, high = falls up)
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


def gravity(k5): return (0.4 - k5) * 3500.0

def ripple(rings, x, y, hue, strong=1.0):
    if len(rings) < 40:
        rings.append([x, y, 6.0, hue, strong])

def _draw(screen, eyesy):
    xres, yres = eyesy.xres, eyesy.yres
    dt, beats, frac, kick, energy = beat_clock(eyesy)
    h0, bg = colors(eyesy)
    canvas = canvas_for(eyesy, bg, 40)
    A = _state["aux"]
    balls = A.setdefault("balls", [])
    rings = A.setdefault("rings", [])
    want = 3 + int(eyesy.knob3 * 21.99)
    while len(balls) < want:
        b = {"x": random.random() * xres, "y": random.random() * yres * 0.6, "vx": (random.random() - 0.5) * 300, "vy": 0.0,
             "sides": random.randint(3, 6), "rot": random.random() * 6.28, "spin": (random.random() - 0.5) * 3,
             "hue": random.random() * 0.7, "rs": 0.6 + random.random() * 0.8, "sq": 1.0}
        balls.append(b)
        ripple(rings, b["x"], b["y"], b["hue"])
    del balls[want:]

    g = gravity(eyesy.knob5)
    cx, cy = xres / 2.0, yres / 2.0
    bi = int(math.floor(beats))
    if A.get("bi") != bi:                                       # every beat: kick them
        A["bi"] = bi
        for b in balls:
            if abs(g) > 150:                                    # kick against gravity (up when it pulls down)
                b["vy"] = -math.copysign(650 + 450 * random.random(), g)
                b["vx"] += (random.random() - 0.5) * 600
            else:                                               # zero-g: burst outward from the middle
                dx, dy = b["x"] - cx, b["y"] - cy
                d = math.hypot(dx, dy) or 1.0
                sp = 700 + 400 * random.random()
                b["vx"] += dx / d * sp
                b["vy"] += dy / d * sp
            b["sq"] = 1.0
    if energy > 0.5 and time.time() - A.get("shove", 0) > 0.25:  # a big knob turn is a shove
        A["shove"] = time.time()
        for b in balls:
            b["vx"] += (random.random() - 0.5) * 900
            b["vy"] += (random.random() - 0.5) * 600

    rb = 12 + 48 * eyesy.knob1
    for b in balls:
        b["vy"] += g * dt
        b["x"] += b["vx"] * dt
        b["y"] += b["vy"] * dt
        b["rot"] += b["spin"] * dt * (1 + energy * 3)
        b["vx"] *= (1 - 0.30 * dt)
        b["vy"] *= (1 - 0.15 * dt)
        sp = math.hypot(b["vx"], b["vy"])
        if sp > 1800:
            b["vx"] *= 1800 / sp
            b["vy"] *= 1800 / sp
        b["r"] = rb * b["rs"]
        r = b["r"]
        hit = False
        if b["x"] < r: b["x"], b["vx"], hit = r, abs(b["vx"]) * 0.92, True
        if b["x"] > xres - r: b["x"], b["vx"], hit = xres - r, -abs(b["vx"]) * 0.92, True
        if b["y"] > yres - r: b["y"], b["vy"], hit = yres - r, -abs(b["vy"]) * 0.88, True
        if b["y"] < r: b["y"], b["vy"], hit = r, abs(b["vy"]) * 0.88, True
        if hit and sp > 200:
            b["sq"] = 1.0
            ripple(rings, b["x"], b["y"], b["hue"], min(1.0, sp / 900.0))
    n = len(balls)
    for i in range(n):                                          # balls bump into each other
        a = balls[i]
        for j in range(i + 1, n):
            c = balls[j]
            dx, dy = c["x"] - a["x"], c["y"] - a["y"]
            rr = a["r"] + c["r"]
            d2 = dx * dx + dy * dy
            if d2 < rr * rr and d2 > 1e-6:
                d = math.sqrt(d2)
                nx, ny = dx / d, dy / d
                rel = (a["vx"] - c["vx"]) * nx + (a["vy"] - c["vy"]) * ny
                if rel > 0:
                    a["vx"] -= rel * nx; a["vy"] -= rel * ny
                    c["vx"] += rel * nx; c["vy"] += rel * ny
                    a["sq"] = c["sq"] = 1.0
                    if rel > 250:
                        ripple(rings, (a["x"] + c["x"]) / 2, (a["y"] + c["y"]) / 2, (a["hue"] + c["hue"]) / 2, min(1.0, rel / 900.0))
                push = (rr - d) / 2.0
                a["x"] -= nx * push; a["y"] -= ny * push
                c["x"] += nx * push; c["y"] += ny * push

    for rg in rings:                                            # expanding ripples from every hit
        rg[2] += 420 * dt
        rg[4] -= dt * 1.8
    rings[:] = [rg for rg in rings if rg[4] > 0]
    for x, y, r, hue, life in rings:
        pygame.draw.circle(canvas, hsv(h0 + hue + 0.5, 0.5, clamp(life)), (int(x), int(y)), int(r), 2)
    for b in balls:
        b["sq"] = max(0.0, b["sq"] - dt * 4.0)
        r = b["r"] * (1.0 + 0.3 * b["sq"])
        pts = [(b["x"] + r * math.cos(b["rot"] + 2 * math.pi * k / b["sides"]), b["y"] + r * math.sin(b["rot"] + 2 * math.pi * k / b["sides"])) for k in range(b["sides"])]
        pygame.draw.polygon(canvas, hsv(h0 + b["hue"], 0.85, 1.0), pts)
        pygame.draw.polygon(canvas, hsv(h0 + b["hue"] + 0.5, 0.3, 1.0), pts, 3)
    screen.blit(canvas, (0, 0))
