# Dance Floor
# A glowing disco floor in perspective, and you pick how it lights up: sparkle, checkerboard flip, ripples
# rolling out from you, sweeping stripes, or an equalizer that stands up out of the floor (it listens to the
# audio input on the real device). Switching the light show flashes the floor so you can hit it on the beat.
# Tap the `0` key on the beat to sync it (on the real device it also locks to the audio kick); tap it a few
# times and the tempo follows you.
#
# Knob convention (same in every mode):
#   knob1 = size             (how big the tiles are (zoom))
#   knob2 = main motion      (tempo, 30 to 120 BPM)
#   knob3 = extra detail     (tiles across the floor, 5 to 14)
#   knob4 = foreground color (hue of the floor)
#   knob5 = bonus control    (light show: Sparkle, Checker, Ripple, Stripes, Equalizer)
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

SHOWS = ["Sparkle", "Checker", "Ripple", "Stripes", "Equalizer"]

def show_of(e): return int(e.knob5 * 4.99)


def _draw(screen, eyesy):
    xres, yres = eyesy.xres, eyesy.yres
    dt, beats, frac, kick, energy = beat_clock(eyesy)
    h0, bg = colors(eyesy)
    A = _state["aux"]
    show = show_of(eyesy)
    if A.get("show") != show:                                  # switching the show flashes the floor
        A["show"] = show
        A["flash"] = 1.0
    A["flash"] = max(0.0, A.get("flash", 0.0) - dt * 2.5)
    flash = A["flash"]
    screen.fill(bg)
    cx, horizon = xres / 2.0, yres * 0.36
    for i in range(7):                                         # a glow band on the horizon
        pygame.draw.rect(screen, hsv(h0 + i * 0.05, 0.8, (0.30 - i * 0.04) + 0.25 * kick + 0.3 * flash), (0, int(horizon - (i + 1) * yres * 0.035), xres, int(yres * 0.03)))
    cols = 5 + int(eyesy.knob3 * 9.99)
    f = yres * (0.55 + eyesy.knob1 * 0.95)
    cam_h = 1.7 - 0.30 * kick                                  # the camera dips on every hit
    ncol = cols + 2
    scroll = 0.0 if show == 4 else (beats * 0.5) % 1.0         # the floor rolls toward you (except the equalizer, which stands still)
    base_row = 0 if show == 4 else int(math.floor(beats * 0.5))
    bi = int(math.floor(beats))
    spec = spectrum(eyesy, ncol) if show == 4 else None
    nrows = int(6 + 12 * _lod["q"])
    p_lit = 0.28 + 0.30 * energy + 0.12 * kick
    rip_r = (beats % 4.0) * 3.2                                # the ripple front grows for 4 beats, then restarts
    for row in range(nrows, -1, -1):                           # far to near
        z0 = 1.0 + row - scroll
        z1 = z0 + 1.0
        if z0 < 0.35:
            continue
        gi = row + base_row
        fog = clamp(1.0 - z0 / 20.0)
        for c in range(ncol):
            x0 = c - ncol / 2.0
            lit = 0.0
            hue = h0
            if show == 0:                                      # sparkle: random tiles, re-rolled each beat
                hsh = ((c * 73856093) ^ (gi * 19349663) ^ (bi * 83492791)) % 1000 / 1000.0
                hsh2 = ((c * 2654435761) ^ (gi * 40503) ^ (bi * 12347)) % 1000 / 1000.0
                if hsh < p_lit:
                    lit = 0.45 + 0.55 * kick
                    hue = h0 + hsh2 * 0.45
            elif show == 1:                                    # checker: two colours swap on every beat
                lit = 0.55 + 0.45 * kick
                hue = h0 + (0.0 if (c + gi + bi) % 2 == 0 else 0.5)
            elif show == 2:                                    # ripple: a ring of light spreads from the front of the floor
                d = math.hypot(x0 + 0.5, row + 0.6)
                lit = clamp(1.15 - abs(d - rip_r) / 1.8)
                hue = h0 + d * 0.04
            elif show == 3:                                    # stripes sweeping toward you
                m = (gi + bi) % 4
                lit = (0.55 + 0.45 * kick) if m == 0 else (0.25 if m == 1 else 0.0)
                hue = h0 + (gi % 8) * 0.06
            else:                                              # equalizer: columns of light grow up from the front edge
                v = spec[c]
                if row < v * 14.0:
                    lit = 0.5 + 0.5 * row / 14.0
                    hue = h0 + c / float(ncol) * 0.5
            if lit > 0.02:
                col = hsv(hue, 0.85, min(1.0, lit * fog + 0.05))
            else:
                col = hsv(h0 + 0.5, 0.5, (0.07 + 0.05 * ((c + gi) % 2)) * fog + 0.02)
            g = 0.04
            pts = []
            for (x, z) in ((x0 + g, z0 + g), (x0 + 1 - g, z0 + g), (x0 + 1 - g, z1 - g), (x0 + g, z1 - g)):
                pts.append((cx + x * f / z, horizon + cam_h * f / z))
            pygame.draw.polygon(screen, col, pts)
    if flash > 0.05:                                           # the whole room flashes when you change the show
        fl = _state.get("flashsurf")
        if fl is None or fl.get_size() != (xres, yres):
            fl = _state["flashsurf"] = pygame.Surface((xres, yres))
            fl.fill((255, 255, 255))
        fl.set_alpha(int(110 * flash))
        screen.blit(fl, (0, 0))
