# Sunburst
# A retro sunburst of bold rays that step round on the beat, with a counter-rotating inner burst
# and a thumping core.
# Turn any knob and the picture reacts at once. Tap the `0` key on the beat to sync it by hand
# (on the real device it also locks to the audio kick).
#
# Knob convention (same in every mode):
#   knob1 = size            (size of the core and inner burst)
#   knob2 = main motion     (tempo, 30 to 120 BPM)
#   knob3 = extra detail    (number of rays, 6 to 48)
#   knob4 = foreground color (hue of the rays)
#   knob5 = bonus control    (curl: bend the rays into a pinwheel spiral)
#
# Playing it (how you turn a knob changes the picture, not just where it ends up):
#   knob1       -> the core swells past its size and relaxes back
#   flick knob2 -> the whole burst whips round, then settles back onto the beat
#   knob3       -> the inner burst spins hard against the outer one
#   knob4       -> the rays split into a rainbow and the colors slam round
#   knob5       -> the pinwheel curl whips tighter, then eases back
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
    knob_play(eyesy, dt)
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
    _fx["rings"] = []
    _fx["sparks"] = []
    _fx["floor"] = None

# ---- beat extras: shockwave rings and sparks that fly out along the rays on every beat ----
_fx = {"rings": [], "sparks": [], "floor": None}
_MAX_SPARKS = 60

def ray_edges(curl, n):
    """cos/sin of the bend at n steps along a ray; the bend is the same for every ray, so it is worked out once a frame"""
    offs = [curl * (j / n) ** 2 for j in range(1, n + 1)]
    return [math.cos(o) for o in offs], [math.sin(o) for o in offs]

def ray_points(cx, cy, far, a, coso, sino, n):
    """points along one edge of a ray at angle a, using the angle-sum identity instead of a cos/sin call per point"""
    ca, sa = math.cos(a), math.sin(a)
    return [(cx + far * (j + 1) / n * (ca * coso[j] - sa * sino[j]),
             cy + far * (j + 1) / n * (sa * coso[j] + ca * sino[j])) for j in range(n)]

def draw(screen, eyesy):
    xres, yres = eyesy.xres, eyesy.yres
    dt, beats, frac, kick, energy = beat_clock(eyesy)
    vel, env, mom = _play["vel"], _play["env"], _play["mom"]
    h0, bg = colors(eyesy)
    h0 += mom[3] * 2.0                                         # knob 4 slams the colors round while you turn it
    screen.fill(bg)
    cx, cy = xres / 2.0, yres / 2.0
    far = math.hypot(cx, cy)                                   # centre to corner is all the rays need to reach
    rays = 2 * (3 + int(eyesy.knob3 * 21.99))                 # an even number, 6..48
    wedge = 2 * math.pi / rays
    step = ease(clamp(frac * 1.4))
    rot = (math.floor(beats) + step) * wedge + mom[1] * 7.0 + env[1] * 0.4 * math.sin(beats * 4)     # flick knob 2 and the burst whips round, then settles back onto the beat
    light = hsv(h0, 0.85, 0.95)
    curl = eyesy.knob5 * 3.2 + mom[4] * 9.0                                  # how far the rays bend by the time they reach the edge
    n = 1 if abs(curl) < 0.05 else (4 if abs(curl) < 1.0 else 8)            # straight rays need no extra points
    coso, sino = ray_edges(curl, n)
    rainbow = env[3] > 0.02
    r1 = min(xres, yres) * (0.16 + 0.22 * eyesy.knob1) * (1.0 + 0.10 * kick) * (1.0 + clamp(mom[0] * 2.5, -0.4, 0.9))     # knob 1 swells the core past its size and relaxes

    # a new beat: send out a shockwave ring and a fan of sparks
    fl = math.floor(beats)
    if _fx["floor"] is not None and fl != _fx["floor"]:
        _fx["rings"].append(0.0)
        for k in range(0, rays, 2):
            if len(_fx["sparks"]) < _MAX_SPARKS:
                _fx["sparks"].append([rot + (k + 0.5) * wedge, r1, far * random.uniform(0.5, 1.1), random.random()])
    _fx["floor"] = fl

    # the dim accent slivers in the gaps between the big rays give the burst some depth
    dim = hsv(h0 + 0.08, 0.6, 0.30 + 0.12 * kick)
    for i in range(1, rays, 2):
        a = rot + i * wedge + wedge * 0.3
        left = ray_points(cx, cy, far, a, coso, sino, n)
        right = ray_points(cx, cy, far, a + wedge * 0.4, coso, sino, n)
        pygame.draw.polygon(screen, dim, [(cx, cy)] + left + right[::-1])

    for i in range(0, rays, 2):                               # the big rays: every other wedge
        a = rot + i * wedge
        left = ray_points(cx, cy, far, a, coso, sino, n)
        right = ray_points(cx, cy, far, a + wedge, coso, sino, n)
        ray = hsv(h0 + (i // 2) * 0.03 * env[3], 0.85, 0.95) if rainbow else light      # the rays split into a rainbow while knob 4 is played
        pygame.draw.polygon(screen, ray, [(cx, cy)] + left + right[::-1])

    rings = []                                                # shockwave rings expand from the core and fade out
    for age in _fx["rings"]:
        age += dt
        t = age / 1.2
        if t < 1.0:
            rings.append(age)
            rad = int(r1 + (far - r1) * ease(t))
            col = hsv(h0 + 0.5, 0.6, 1.0 - t)
            pygame.draw.circle(screen, col, (int(cx), int(cy)), rad, max(1, int(6 * (1.0 - t))))
    _fx["rings"] = rings

    sparks = []                                               # sparks fly out along the rays and twinkle
    for sp in _fx["sparks"]:
        sp[1] += sp[2] * dt
        if sp[1] < far:
            sparks.append(sp)
            col = hsv(h0 + 0.5 + sp[3] * 0.2, 0.4, 1.0)
            size = 2 + int(3 * (1.0 - sp[1] / far))
            pygame.draw.circle(screen, col, (int(cx + sp[1] * math.cos(sp[0])), int(cy + sp[1] * math.sin(sp[0]))), size)
    _fx["sparks"] = sparks

    pygame.draw.circle(screen, bg, (int(cx), int(cy)), int(r1 * 1.08))                 # a clean disc for the inner burst
    rot2 = -rot * 1.5 + mom[2] * 10.0                          # knob 3 spins the inner burst against the outer one
    alt = hsv(h0 + 0.5, 0.75, 0.95)
    for i in range(0, rays, 2):                               # the inner burst turns the other way
        a = rot2 + i * wedge
        pts = [(cx, cy)] + [(cx + r1 * math.cos(a + wedge * j / 4), cy + r1 * math.sin(a + wedge * j / 4)) for j in range(5)]
        pygame.draw.polygon(screen, alt, pts)
    pygame.draw.circle(screen, hsv(h0, 0.2, 1.0), (int(cx), int(cy)), int(r1 * (0.32 + 0.16 * kick)))
    pygame.draw.circle(screen, hsv(h0 + 0.5, 0.9, 1.0), (int(cx), int(cy)), int(r1 * 0.12))
