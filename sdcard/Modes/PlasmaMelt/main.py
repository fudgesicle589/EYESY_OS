# Plasma Melt: a liquid, molten light show. Waves of color slosh and melt into each other, and you can
# stretch them, reverse time, layer them thicker, and turn smooth color into razor-sharp contour rings.
#
# Knob convention (same in every mode):
#   knob1 = size            (zoom: big lazy waves to fine ripples)
#   knob2 = main motion     (flow: 0.5 = frozen, left = backward, right = forward, faster toward the ends)
#   knob3 = extra detail    (layers and melt, plus how many color rings; at the top it goes full zebra)
#   knob4 = foreground color (hue)
#   knob5 = bonus control    (palette spin: 0.5 = colors hold still, left = they roll backward, right = forward, faster toward the ends)
#
# Playing it (how you turn a knob changes the picture, not just where it ends up):
#   knob1       -> zoom lurches in or out past where it will rest, then relaxes
#   flick knob2 -> shoves the liquid along even when the flow is frozen; it drifts to a stop
#   knob3       -> the waves fold over themselves much harder while you turn it
#   knob4/knob5 -> the colors whoosh round the palette while you turn them, then settle
import colorsys
import math
import time
import pygame

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))

_state = {"t": 0.0, "last": None}
_cache = {"lut_key": None, "lut": None, "grid_key": None, "dist": None}

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

def _ramp(h0, bands, bg):
    """the colour ramp as 256 four-byte pixels; only rebuilt when the colour knobs actually move"""
    key = (round(h0, 2), round(bands, 1), int(bg[0]) >> 2, int(bg[1]) >> 2, int(bg[2]) >> 2)
    if _cache["lut_key"] != key:
        lut = []
        for i in range(256):
            ph = i / 255.0 * bands * 2 * math.pi
            k = 0.5 + 0.5 * math.sin(ph)
            r, g, b = colorsys.hsv_to_rgb((h0 + 0.18 * math.sin(ph * 0.5) + i / 255.0 * 0.25) % 1.0, 0.85, 0.35 + 0.65 * k)
            m = 1.0 - k
            lut.append(bytes((int(clamp(b * 255 * (1 - 0.6 * m) + bg[2] * 0.6 * m, 0, 255)),      # blue, green, red, alpha
                              int(clamp(g * 255 * (1 - 0.6 * m) + bg[1] * 0.6 * m, 0, 255)),
                              int(clamp(r * 255 * (1 - 0.6 * m) + bg[0] * 0.6 * m, 0, 255)), 255)))
        _cache["lut_key"], _cache["lut"] = key, lut
    return _cache["lut"]

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

    vel, env, mom = knob_play(eyesy, dt)
    flow = (eyesy.knob2 - 0.5) * 2
    _state["t"] += dt * (flow * 3.0 + clamp(mom[1] * 25.0, -8.0, 8.0))     # a flick shoves the liquid along, even when the knob is in the frozen spot
    t = _state["t"]

    # the plasma is worked out on a small grid, then scaled up smoothly; the grid shrinks if the machine is slow
    q = _lod["q"]
    W = int(56 + 56 * q)
    H = max(2, int(W * 9 / 16))
    if _cache["grid_key"] != (W, H):
        _cache["grid_key"] = (W, H)
        _cache["dist"] = [[math.hypot((i / W - 0.5) * (W / H), j / H - 0.5) for i in range(W)] for j in range(H)]
    dist = _cache["dist"]

    # ---- knobs ----
    scale = (2.0 + eyesy.knob1 * 16.0) * (1.0 + clamp(mom[0] * 3.0, -0.5, 1.0))
    detail = eyesy.knob3
    layers = 2 + int(detail * 2.99)                           # 2..4 layers of waves
    melt = 0.4 + detail * 2.4 + env[2] * 2.0                  # how much the waves fold over themselves; play knob 3 and they fold hard
    _state["pal"] = _state.get("pal", 0.0) + dt * (eyesy.knob5 - 0.5) * 2 * 160.0       # knob 5 spins the palette round the plasma
    roll = int(mom[3] * 700 + _state["pal"])                  # (and it whooshes while the color knob moves)
    bands = 1.0 + detail * 7.0                                # how many color rings

    fg = eyesy.color_picker(eyesy.knob4)
    h0 = colorsys.rgb_to_hsv(fg[0] / 255.0, fg[1] / 255.0, fg[2] / 255.0)[0]
    bg = tuple(int(c * 255) for c in colorsys.hsv_to_rgb((h0 + 0.55) % 1.0, 0.65, 0.10))      # the dark tone the plasma dips into
    lutb = _ramp(h0, bands, bg)

    # ---- the field: separable waves per column and per row, plus a radial one per pixel ----
    aspect = W / H
    sin, cos = math.sin, math.cos
    cs1 = [sin((i / W - 0.5) * aspect * scale + t * 0.9) for i in range(W)]
    rs1 = [sin((j / H - 0.5) * scale * 1.3 - t * 0.7) for j in range(H)]
    sc = [sin((i / W - 0.5) * aspect * scale * 0.8 + t * 0.5) for i in range(W)]
    cc = [cos((i / W - 0.5) * aspect * scale * 0.8 + t * 0.5) for i in range(W)]
    sr = [sin((j / H - 0.5) * scale * 0.8) for j in range(H)]
    cr = [cos((j / H - 0.5) * scale * 0.8) for j in range(H)]
    tt, k14, t11 = t * 0.6, scale * 1.4, t * 1.1
    rows = []
    for j in range(H):
        r1 = rs1[j]
        if layers == 2:
            vs = [c + r1 for c in cs1]
        elif layers == 3:
            s_r, c_r = sr[j], cr[j]
            vs = [c + r1 + a * c_r + b * s_r for c, a, b in zip(cs1, sc, cc)]
        else:
            s_r, c_r = sr[j], cr[j]
            vs = [c + r1 + a * c_r + b * s_r + sin(d * k14 - t11) for c, a, b, d in zip(cs1, sc, cc, dist[j])]
        rows.append(b"".join([lutb[int((v + melt * sin(v * 1.3 + tt)) * 40.8 + 127.5 + roll) & 255] for v in vs]))
    small = pygame.image.frombuffer(b"".join(rows), (W, H), "BGRA")
    pygame.transform.smoothscale(small, (xres, yres), screen)     # scaled straight into the screen: no temporary picture
