# Kaleido Bloom: glowing petals, orbs and ribbons orbit inside a live kaleidoscope with mirrored wedges.
# Turn the segment knob and the whole flower re-folds itself; spin it either way; make it huge or tiny.
#
# Knob convention (same in every mode):
#   knob1 = size            (how big the petals and orbs are)
#   knob2 = main motion     (spin the kaleidoscope: 0.5 = still, left/right = spin either way, faster toward the ends)
#   knob3 = extra detail    (number of mirrored wedges, 4 to 18)
#   knob4 = foreground color (hue of the whole bloom)
#   knob5 = background color (also the color the trails fade into)
#
# Playing it (how you turn a knob changes the picture, not just where it ends up):
#   flick knob2 -> the flower keeps spinning like a record platter, then settles; a fast swirl while you touch anything
#   knob1       -> the bloom swells past its resting size and relaxes back
#   knob3       -> the petals burst outward as the wedges re-fold
#   knob4       -> the petals fan out into a rainbow while you turn it
#   knob5       -> the trails smear out long while you turn it
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

_state = {"t": 0.0, "rot": 0.0, "last": None, "canvas": None, "fade": None, "size": None}

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

    fg = eyesy.color_picker(eyesy.knob4)
    h0 = colorsys.rgb_to_hsv(fg[0] / 255.0, fg[1] / 255.0, fg[2] / 255.0)[0]
    bg = tuple(int(c) for c in eyesy.color_picker_bg(eyesy.knob5))

    if _state["size"] != (xres, yres):
        _state["size"] = (xres, yres)
        _state["canvas"] = pygame.Surface((xres, yres))
        _state["canvas"].fill(bg)
        _state["fade"] = pygame.Surface((xres, yres))

    # ---- knobs ----
    vel, env, mom = knob_play(eyesy, dt)
    spin = (eyesy.knob2 - 0.5) * 2 * 1.6 + mom[1] * 14.0     # radians per second; flick knob 2 like a record platter and it keeps spinning, then settles
    _state["rot"] += spin * dt
    _state["t"] += dt * (0.7 + abs(spin) * 0.6 + max(env) * 1.5)     # the petals swirl faster when you spin harder, or play any knob
    t, rot = _state["t"], _state["rot"]
    pairs = 2 + int(eyesy.knob3 * 7.99)                       # 2..9 mirrored pairs = 4..18 wedges
    size = (0.35 + eyesy.knob1 * 1.3) * (1.0 + clamp(mom[0] * 2.0, -0.4, 0.8))     # knob 1 swells the bloom past where it will rest, then it relaxes
    spread = 1.0 + clamp(mom[2] * 3.0, -0.5, 0.35)            # changing the wedges blows the petals outward (or sucks them in)

    canvas = _state["canvas"]
    fade = _state["fade"]
    fade.fill(bg)
    fade.set_alpha(int(max(6, 36 - 30 * env[4])))             # a soft trail; play knob 5 and the trails smear out long
    canvas.blit(fade, (0, 0))

    cx, cy = xres / 2.0, yres / 2.0
    R = min(xres, yres) * 0.5
    unit = R / 360.0

    # the petals: each one wanders in and out along its own orbit
    E = max(6, int(16 * (0.5 + 0.5 * _lod["q"])))            # fewer petals when the machine is struggling
    els = []
    for i in range(E):
        rr = R * (0.10 + 0.85 * (0.5 + 0.5 * math.sin(t * (0.5 + 0.09 * i) + i * 1.9))) * spread
        aa = t * (0.35 + 0.06 * i) + i * 0.71
        s = (6 + 26 * (0.5 + 0.5 * math.sin(t * 1.3 + i))) * size * unit * 1.6
        hp = h0 + i * (0.05 + 0.12 * env[3]) + t * 0.04 + mom[3] * 2.0     # play knob 4 and the petals fan out into a rainbow
        els.append((rr, aa, s, hsv(hp, 0.85, 1.0), hsv(hp, 0.35, 1.0)))

    for m in range(pairs):
        base = rot + 2 * math.pi * m / pairs
        for mirror in (1, -1):
            pos = []
            for rr, aa, s, c1, c2 in els:
                a = base + mirror * aa
                pos.append((cx + rr * math.cos(a), cy + rr * math.sin(a), a))
            for i in range(E - 1):                              # ribbons between neighbouring petals
                if i % 2 == 0:
                    pygame.draw.line(canvas, els[i][3], pos[i][:2], pos[i + 1][:2], max(1, int(2 * size * rs)))
            for i, (rr, aa, s, c1, c2) in enumerate(els):
                x, y, a = pos[i]
                ux, uy = math.cos(a), math.sin(a)
                vx, vy = -uy, ux
                pygame.draw.polygon(canvas, c1, [(x + ux * s * 2.2, y + uy * s * 2.2), (x + vx * s * 0.8, y + vy * s * 0.8),
                                                 (x - ux * s, y - uy * s), (x - vx * s * 0.8, y - vy * s * 0.8)])
                pygame.draw.circle(canvas, c2, (int(x), int(y)), max(2, int(s * 0.55)))

    pulse = 0.5 + 0.5 * math.sin(t * 2.0)                     # a beating core
    pygame.draw.circle(canvas, hsv(h0 + 0.5, 0.6, 1.0), (int(cx), int(cy)), int((10 + 22 * pulse) * size * unit * 1.6))
    pygame.draw.circle(canvas, hsv(h0, 0.2, 1.0), (int(cx), int(cy)), int((4 + 8 * pulse) * size * unit * 1.6))
    if rs == 1.0:
        screen.blit(canvas, (0, 0))
    else:
        pygame.transform.scale(canvas, (full_x, full_y), screen)     # straight into the screen
