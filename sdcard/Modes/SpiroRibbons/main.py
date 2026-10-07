# Spiro Ribbons: neon spirograph ribbons that react to every knob straight away.
# The ratio knob melts the shape into hundreds of different flowers, the ribbon knob snaps in more
# petals of perfect symmetry, and size changes the line thickness as well as the radius.
#
# Knob convention (same in every mode):
#   knob1 = size            (radius and line thickness)
#   knob2 = main motion     (the spirograph ratio, 1 to 13: sweep it and the whole flower morphs)
#   knob3 = extra detail    (number of ribbons, 1 to 9, spread evenly so they lock into symmetric flowers)
#   knob4 = foreground color (base hue; the ribbons fan out from it)
#   knob5 = background color (also the color the trails fade into)
#
# Playing it (how you turn a knob changes the picture, not just where it ends up):
#   knob1       -> the flower swells past its size and relaxes back; the lines throb bolder
#   flick knob2 -> the ratio overshoots and springs back, and the trails smear so you see the morph
#   knob3       -> the ribbons peel apart while you change the count, then lock back into symmetry
#   knob4       -> the ribbons fan out into a wide rainbow while you turn it
#   knob5       -> the beads on the ribbons swell and the whole flower twirls
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

_state = {"t": 0.0, "last": None, "canvas": None, "fade": None, "size": None}

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
    full_x, full_y = eyesy.xres, eyesy.yres
    rs = render_scale()                                       # 0.5 if the machine is struggling: draw a quarter of the pixels
    xres, yres = int(full_x * rs), int(full_y * rs)
    now = time.time()
    if _state["last"] is None:
        _state["last"] = now
    dt = min(now - _state["last"], 0.1)
    _state["last"] = now
    _state["t"] += dt
    t = _state["t"]
    vel, env, mom = knob_play(eyesy, dt)

    bg = tuple(int(c) for c in eyesy.color_picker_bg(eyesy.knob5))
    if _state["size"] != (xres, yres):
        _state["size"] = (xres, yres)
        _state["canvas"] = pygame.Surface((xres, yres))
        _state["fade"] = pygame.Surface((xres, yres))
    canvas, fade = _state["canvas"], _state["fade"]
    fade.fill(bg)
    fade.set_alpha(int(80 - 62 * env[1]))                     # short trails, so every change shows right away; play knob 2 and they smear
    canvas.blit(fade, (0, 0))

    fg = eyesy.color_picker(eyesy.knob4)
    h0 = colorsys.rgb_to_hsv(fg[0] / 255.0, fg[1] / 255.0, fg[2] / 255.0)[0]

    # ---- knobs ----
    R = min(xres, yres) * 0.47 * (0.18 + eyesy.knob1 * 1.05) * (1.0 + clamp(mom[0] * 2.0, -0.4, 0.6))
    thick = max(1, int((2 + int(eyesy.knob1 * 6) + env[0] * 4) * rs))     # bigger also means bolder lines
    ratio = 1.0 + eyesy.knob2 * 12.0 + 0.12 * math.sin(t * 0.8) + mom[1] * 8.0    # a little wobble keeps it alive; a flick overshoots and springs back
    n = 1 + int(eyesy.knob3 * 8.99)

    cx, cy = xres / 2.0, yres / 2.0
    A = R * 0.60
    B = R * (0.40 + 0.06 * math.sin(t * 0.6))
    spin = t * 0.18 + mom[4] * 4.0
    q = _lod["q"]
    pts_n = int(110 + 210 * q)                                # fewer points per ribbon when the machine is struggling
    step = math.pi * 4 / pts_n
    cos, sin = math.cos, math.sin
    cj = [cos(j * step) for j in range(pts_n)]                # the same for every ribbon
    sj = [sin(j * step) for j in range(pts_n)]
    rstep = ratio * step
    Cv = [cos(j * rstep) for j in range(pts_n)]               # depends on the ratio knob, but shared by all ribbons
    Sv = [sin(j * rstep) for j in range(pts_n)]
    bead_gap = max(1, pts_n // 8)
    lines, circle = pygame.draw.lines, pygame.draw.circle
    for i in range(n):
        off = i * (2 * math.pi / n)                           # even spacing: n ribbons make an n-fold flower
        a0 = spin + off * 0.25
        p0 = ratio * spin + off * 0.5 + t * 0.35 + mom[2] * 9.0 * i     # while knob 3 moves, each ribbon drifts off by its own amount
        ca0, sa0, cp0, sp0 = cos(a0), sin(a0), cos(p0), sin(p0)
        pts = [(cx + A * (ca0 * cj[j] - sa0 * sj[j]) + B * (cp0 * Cv[j] - sp0 * Sv[j]),
                cy + A * (sa0 * cj[j] + ca0 * sj[j]) + B * (sp0 * Cv[j] + cp0 * Sv[j])) for j in range(pts_n)]
        hue = h0 + i / n * (0.7 + 0.9 * env[3]) + t * 0.03 + mom[3] * 2.0
        if q > 0.5:
            lines(canvas, hsv(hue, 0.9, 0.55), False, pts, thick + 5)      # glow
        lines(canvas, hsv(hue, 0.65, 1.0), False, pts, thick)              # bright core
        if q > 0.4:
            for j in range(0, pts_n, bead_gap):                            # beads along the ribbon
                circle(canvas, hsv(hue + 0.15, 0.3, 1.0), (int(pts[j][0]), int(pts[j][1])), thick + 2 + int(env[4] * 8 * rs))
    if rs == 1.0:
        screen.blit(canvas, (0, 0))
    else:
        pygame.transform.scale(canvas, (full_x, full_y), screen)     # straight into the screen
