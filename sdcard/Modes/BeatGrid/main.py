# Beat Grid: a wall of LED dots. Every beat a shockwave rolls out from the middle and the dots swell as it passes.
# Turn any knob and the picture reacts at once. Tap the `0` key on the beat to sync it by hand (on the real device it locks to the audio kick).
#
# Knob convention (same in every mode):
#   knob1 = size            (how fat the dots get, and how wide the shockwave is)
#   knob2 = main motion     (tempo, 30 to 120 BPM)
#   knob3 = extra detail    (grid density, 6 to 40 columns, and the wave shape: circle -> diamond -> square)
#   knob4 = foreground color (hue of the dots)
#   knob5 = background color
import colorsys
import math
import time
import pygame

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))

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

_state = {"beats": 0.0, "last": None}

def beat_clock(eyesy):
    """advance a beat counter at the knob's tempo; an audio hit (or the 0 key) snaps it to the next beat"""
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

def _draw(screen, eyesy):
    xres, yres = eyesy.xres, eyesy.yres
    dt, beats, frac, kick, energy = beat_clock(eyesy)

    fg = eyesy.color_picker(eyesy.knob4)
    h0 = colorsys.rgb_to_hsv(fg[0] / 255.0, fg[1] / 255.0, fg[2] / 255.0)[0]
    bg = tuple(int(c) for c in eyesy.color_picker_bg(eyesy.knob5))
    screen.fill(bg)

    cols = 6 + int(eyesy.knob3 * 34.99 * (0.55 + 0.45 * _lod["q"]))          # fewer, bigger dots when the machine is struggling
    cell = xres / float(cols)
    rows = int(math.ceil(yres / cell))
    grow = 0.25 + eyesy.knob1 * 0.95                          # the biggest a dot can get, as a share of its cell
    ring_r = frac * 1.7                                       # the wave front this beat, in screen half-widths
    k3 = eyesy.knob3
    q = 2.0 - 2.0 * k3 if k3 < 0.5 else 1.0 + (k3 - 0.5) * 10.0     # wave shape: circle (2) -> diamond (1) -> square (6)
    width = 0.10 + eyesy.knob1 * 0.28
    cx, cy = xres / 2.0, yres / 2.0
    half = xres / 2.0
    for j in range(rows):
        y = (j + 0.5) * cell + (yres - rows * cell) / 2.0
        for i in range(cols):
            x = (i + 0.5) * cell
            ddx, ddy = abs(x - cx) / half, abs(y - cy) / half
            d = (ddx ** q + ddy ** q) ** (1.0 / q) if (ddx > 0 or ddy > 0) else 0.0
            w = math.exp(-((d - ring_r) / width) ** 2)                 # this beat's wave
            w2 = math.exp(-((d - ring_r - 1.7) / width) ** 2)          # the last beat's wave, still travelling
            swell = clamp(w + w2 * 0.6 + energy * 0.5 * (0.5 + 0.5 * math.sin(d * 9.0 - beats * 3.0)))     # touching a knob sets the whole wall rippling
            r = cell * 0.5 * (0.12 + grow * (0.15 + 0.85 * swell)) * (1.0 + 0.25 * kick)
            hue = h0 + d * 0.35 + ((i + j) % 2) * 0.06 + beats * 0.01
            pygame.draw.circle(screen, hsv(hue, 0.85 - 0.5 * swell, 0.35 + 0.65 * (swell * 0.8 + 0.2 * kick)), (int(x), int(y)), max(1, int(r)))
