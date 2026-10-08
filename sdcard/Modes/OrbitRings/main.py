# Orbit Rings
# Three rings of dots, and each of the first three knobs steers one ring on its own. Every beat a ring steps
# around by a whole number of dots: the number is set by its knob (dead center = parked, left of center = steps
# backwards, right = steps forwards, up to 4 dots per beat). Set the three rings to different speeds and
# directions and play them against each other like a polyrhythm. Tap the `0` key on the beat to sync it; tap it
# a few times and the tempo follows you (on the real device it also locks to the audio kick).
#
# Knob layout (this mode's own: the first three knobs are one ring each):
#   knob1 = outer ring   (dots stepped per beat, -4 to +4; centered = parked)
#   knob2 = middle ring  (same)
#   knob3 = inner ring   (same)
#   knob4 = foreground color (hue of the rings)
#   knob5 = bonus control    (tilt: lay the rings over into ellipses, like a gyroscope)
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

DOTS = (16, 12, 8)                                             # dots on the outer, middle and inner rings
NAMES = ("Outer ring", "Middle ring", "Inner ring")

def steps_of(v):
    return int(max(-4, min(4, round((v - 0.5) * 10.0))))

def _draw(screen, eyesy):
    full_x, full_y = eyesy.xres, eyesy.yres
    rs = render_scale()
    xres, yres = int(full_x * rs), int(full_y * rs)
    dt, beats, frac, kick, energy = beat_clock(eyesy, "tap")      # tempo comes from tapping the 0 key (starts at 100 BPM)
    h0, bg = colors(eyesy)
    canvas = canvas_for(eyesy, bg, 55, (xres, yres))
    cx, cy = xres / 2.0, yres / 2.0
    maxr = min(xres, yres) * 0.46
    dot = (7 + 5 * kick) * rs
    step = ease(clamp(frac * 1.5))                                # each beat: a quick eased step
    squash = max(0.18, math.cos(eyesy.knob5 * 1.35))
    spin = beats * 0.10 if eyesy.knob5 > 0.05 else 0.0
    cs, sn = math.cos(spin), math.sin(spin)
    def place(r, a):
        dx, dy = r * math.cos(a), r * math.sin(a) * squash
        return (cx + dx * cs - dy * sn, cy + dx * sn + dy * cs)
    A = _state["aux"]
    rings = A.setdefault("rings", [[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]])    # per ring: [from, to] in dots
    bi = int(math.floor(beats))
    ks = (eyesy.knob1, eyesy.knob2, eyesy.knob3)
    if A.get("bi") != bi:                                         # a new beat: every ring starts its next step
        A["bi"] = bi
        for k in range(3):
            rings[k][0] = rings[k][1]
            rings[k][1] += steps_of(ks[k])
    layers = []
    for k in range(3):
        r = maxr * (3 - k) / 3.0
        m = DOTS[k]
        pos = rings[k][0] + (rings[k][1] - rings[k][0]) * step
        a0 = pos * 2 * math.pi / m + k * 0.3
        moving = abs(steps_of(ks[k]))
        hue = h0 + k * 0.33
        pts = [place(r, a0 + 2 * math.pi * j / m) for j in range(m)]
        layers.append((pts, hue, moving))
        pygame.draw.polygon(canvas, hsv(hue, 0.6, 0.25 + 0.08 * moving), [place(r, 2 * math.pi * j / 72) for j in range(72)], 2)
    for k in range(2):                                            # spokes linking neighbouring rings
        a, b = layers[k][0], layers[k + 1][0]
        for j, p in enumerate(a):
            q = b[(j * len(b)) // len(a)]
            pygame.draw.line(canvas, hsv(h0 + k * 0.33 + 0.1, 0.6, 0.55), p, q, 1)
    for pts, hue, moving in layers:
        for j, p in enumerate(pts):
            d = int(dot * (1.0 + 0.12 * moving)) if j else int(dot * 1.5)                 # one marker dot per ring so you can see which way it turns
            pygame.draw.circle(canvas, hsv(hue, 0.85, 1.0), (int(p[0]), int(p[1])), d)
            pygame.draw.circle(canvas, hsv(hue, 0.2, 1.0) if j else (255, 255, 255), (int(p[0]), int(p[1])), max(2, int(d * 0.4)))
    pygame.draw.circle(canvas, hsv(h0 + 0.5, 0.5, 1.0), (int(cx), int(cy)), int(dot * 1.6))
    if rs == 1.0:
        screen.blit(canvas, (0, 0))
    else:
        pygame.transform.scale(canvas, (full_x, full_y), screen)
