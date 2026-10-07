# Dance Floor
# A glowing disco floor in perspective. Tiles flash on and off with every beat and the floor rolls toward you.
# Turn any knob and the picture reacts at once. Tap the `0` key on the beat to sync it by hand
# (on the real device it also locks to the audio kick).
#
# Knob convention (same in every mode):
#   knob1 = size            (how big the tiles are (zoom))
#   knob2 = main motion     (tempo, 30 to 120 BPM)
#   knob3 = extra detail    (tiles across the floor, 5 to 14)
#   knob4 = foreground color (hue of the whole floor)
#   knob5 = bonus control    (camera height: skim the floor low or look straight down on it)
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

def _draw(screen, eyesy):
    xres, yres = eyesy.xres, eyesy.yres
    dt, beats, frac, kick, energy = beat_clock(eyesy)
    h0, bg = colors(eyesy)
    screen.fill(bg)
    cx, horizon = xres / 2.0, yres * 0.36
    for i in range(7):                                        # a glow band on the horizon
        pygame.draw.rect(screen, hsv(h0 + i * 0.05, 0.8, (0.30 - i * 0.04) + 0.25 * kick), (0, int(horizon - (i + 1) * yres * 0.035), xres, int(yres * 0.03)))
    cols = 5 + int(eyesy.knob3 * 9.99)
    f = yres * (0.55 + eyesy.knob1 * 0.95)
    cam_h = 0.5 + 3.5 * eyesy.knob5                           # fly low over the floor or look down from above
    scroll = (beats * 0.5) % 1.0                              # the floor rolls toward you
    base_row = int(math.floor(beats * 0.5))
    bi = int(math.floor(beats))
    p_lit = 0.28 + 0.30 * energy + 0.12 * kick
    for row in range(int(6 + 12 * _lod["q"]), -1, -1):        # far to near (a shorter floor when the machine is struggling)
        z0 = 1.0 + row - scroll
        z1 = z0 + 1.0
        if z0 < 0.35:
            continue
        gi = row + base_row
        for c in range(cols + 2):
            x0 = c - (cols + 2) / 2.0
            hsh = ((c * 73856093) ^ (gi * 19349663) ^ (bi * 83492791)) % 1000 / 1000.0
            hsh2 = ((c * 2654435761) ^ (gi * 40503) ^ (bi * 12347)) % 1000 / 1000.0
            lit = hsh < p_lit
            fog = clamp(1.0 - z0 / 20.0)
            if lit:
                col = hsv(h0 + hsh2 * 0.45, 0.85, (0.45 + 0.55 * kick) * fog + 0.05)
            else:
                col = hsv(h0 + 0.5, 0.5, (0.07 + 0.05 * ((c + gi) % 2)) * fog + 0.02)
            g = 0.04
            pts = []
            for (x, z) in ((x0 + g, z0 + g), (x0 + 1 - g, z0 + g), (x0 + 1 - g, z1 - g), (x0 + g, z1 - g)):
                pts.append((cx + x * f / z, horizon + cam_h * f / z))
            pygame.draw.polygon(screen, col, pts)
