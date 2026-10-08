# Poly Portal: an endless tunnel of nested, twisting shapes with neon edges. You fall in forever.
# Step the sides from triangle to hendecagon, wind the spiral tighter and tighter, and set the speed.
#
# Knob convention (same in every mode):
#   knob1 = size            (zoom: how fast you fall into the tunnel)
#   knob2 = main motion     (twist: 0.5 = straight, left/right = spiral either way, tighter toward the ends)
#   knob3 = extra detail    (number of sides, 3 to 11)
#   knob4 = foreground color (hue that cycles along the tunnel)
#   knob5 = bonus control    (ring spacing: tightly packed rings up to wide, bold steps)
#
# Playing it (how you turn a knob changes the picture, not just where it ends up):
#   knob1       -> lurch the tunnel forward (turn up) or yank it back (turn down)
#   flick knob2 -> whip the spiral round; it unwinds on its own like a spring
#   knob3       -> the rings wobble and flash white while you change the sides
#   knob4       -> the rainbow along the tunnel stretches while you turn it
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

_state = {"t": 0.0, "pos": 0.0, "last": None}

# ---- playing the knobs: HOW a knob is being turned matters as much as where it sits ----
_play = {"prev": None, "vel": [0.0] * 5, "env": [0.0] * 5, "mom": [0.0] * 5}

def knob_play(eyesy, dt):
    """returns (vel, env, mom), one number per knob:
    vel = how fast and which way it is turning (per second, smoothed)
    env = 0..1 'being played' level; a flick jumps it to 1 and it rings out over about a second
    mom = swing: each turn adds a kick that unwinds over about a second, so a flick overshoots and settles back"""
    ks = (eyesy.knob1, eyesy.knob2, eyesy.knob3, eyesy.knob4, eyesy.knob5)
    prev = _play["prev"]
    _play["prev"] = ks
    vel, env, mom = _play["vel"], _play["env"], _play["mom"]
    ring, unwind = math.exp(-dt * 3.0), math.exp(-dt * 1.4)
    for i in range(5):
        delta = 0.0 if prev is None else ks[i] - prev[i]
        raw = delta / dt if dt > 0 else 0.0
        vel[i] += (raw - vel[i]) * min(1.0, dt * 15.0)
        env[i] = max(env[i] * ring, min(1.0, abs(vel[i]) / 1.2))
        mom[i] = mom[i] * unwind + delta
    return vel, env, mom

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
    now = time.time()
    if _state["last"] is None:
        _state["last"] = now
    dt = min(now - _state["last"], 0.1)
    _state["last"] = now
    _state["t"] += dt
    vel, env, mom = knob_play(eyesy, dt)

    # ---- knobs ----
    zoom_speed = 0.15 + eyesy.knob1 * 2.2 + clamp(mom[0] * 12.0, -2.5, 4.0)     # tunnel levels per second, plus a lurch while knob 1 moves
    twist = (eyesy.knob2 - 0.5) * 2 * 0.95 + clamp(mom[1] * 5.0, -1.5, 1.5)      # radians of extra turn per level, plus a whip that unwinds
    n = 3 + int(eyesy.knob3 * 8.99)                           # 3..11 sides
    fg = eyesy.color_picker(eyesy.knob4)
    h0 = colorsys.rgb_to_hsv(fg[0] / 255.0, fg[1] / 255.0, fg[2] / 255.0)[0]
    bg = hsv(h0 + 0.55, 0.6, 0.08)
    dark = hsv(h0 + 0.55, 0.6, 0.05)                           # the dark rings between the bright ones
    spread = 0.037 + 0.10 * env[3]                            # the colour change from ring to ring
    hshift = h0 + mom[3] * 2.0

    _state["pos"] += dt * zoom_speed
    t = _state["t"]
    pos = _state["pos"]
    g = int(math.floor(pos))
    f = pos - g

    cx, cy = xres / 2.0, yres / 2.0
    diag = math.hypot(xres, yres)
    q = 0.74 + 0.18 * eyesy.knob5                             # each level is this much smaller than the last (knob 5: tight rings to wide steps)
    K = int(14 + 22 * _lod["q"])                              # fewer levels when the machine is struggling
    R0 = diag * 0.72 * (1.0 + 0.03 * math.sin(t * 3.0))
    screen.fill(bg)
    sway = (0.05 * xres * math.sin(t * 0.6), 0.05 * yres * math.sin(t * 0.9 + 1.0))    # the tunnel sways a little

    for k in range(K):
        gi = g + k                                            # this level's permanent number, so it keeps its colour as it grows
        r = R0 * q ** (k + 1 - f)
        if r < 3:
            break
        depth = k / K
        ang = gi * twist + t * 0.35
        lit = (gi % 2 == 0)
        fill = hsv(hshift + gi * spread, 0.75, 0.95 - 0.35 * depth) if lit else dark
        edge = hsv(hshift + gi * spread + 0.5, 0.6 * (1.0 - env[2]), 1.0)     # the edges flash white while knob 3 is played
        if env[2] > 0.05:
            r *= 1.0 + env[2] * 0.10 * math.sin(gi * 1.7 + t * 9.0)           # ...and the rings wobble
        ox, oy = cx + sway[0] * depth, cy + sway[1] * depth
        pts = [(ox + r * math.cos(ang + 2 * math.pi * s / n), oy + r * math.sin(ang + 2 * math.pi * s / n)) for s in range(n)]
        pygame.draw.polygon(screen, fill, pts)
        pygame.draw.polygon(screen, edge, pts, max(1, int(min(6, 1 + r * 0.012))))
        if r > 12:
            for pt in pts:
                pygame.draw.circle(screen, edge, (int(pt[0]), int(pt[1])), max(2, int(r * 0.018)))
    pygame.draw.circle(screen, hsv(h0 + 0.5, 0.5, 1.0), (int(cx + sway[0]), int(cy + sway[1])), int(4 + 3 * math.sin(t * 5.0)))
