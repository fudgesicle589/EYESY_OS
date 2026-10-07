# Vortex Feedback: a screen-on-screen tunnel. Each frame the picture is zoomed and twisted back into
# itself, so paint dropped at the middle is flung into spiral arms. The knobs steer the flow live.
# Sparkles are sprinkled all over the screen so you can watch the zoom and twist react instantly.
#
# Knob convention (same in every mode):
#   knob1 = size            (brush size and how wide the arms swing)
#   knob2 = main motion     (warp: the middle is calm, either end twists and zooms harder, in opposite directions)
#   knob3 = extra detail    (number of arms, 1 to 12, and how many sparkles rain down)
#   knob4 = foreground color (base hue; the trails keep cycling through the rainbow from it)
#   knob5 = background color (what the tunnel fades into)
#
# Playing it (how you turn a knob changes the picture, not just where it ends up):
#   knob1       -> the brushes balloon and the arms fling wide while you turn it
#   flick knob2 -> an extra whip of twist and zoom that unwinds, so you can snap the whole tunnel round on a beat
#   knob3       -> a burst of sparkles rains down while you turn it
#   knob4       -> the colors slam round the rainbow while you turn it
#   knob5       -> the trails hang on much longer while you turn it
import colorsys
import math
import random
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

_state = {"t": 0.0, "last": None, "buf": None, "size": None, "prev": {}}

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
    t = _state["t"]
    vel, env, mom = knob_play(eyesy, dt)

    q = _lod["q"]
    tier = _state.get("tier", 2)                              # the feedback runs at half size, or a third if the machine is struggling
    if tier == 2 and q < 0.4:
        tier = 3
    elif tier == 3 and q > 0.85:
        tier = 2
    _state["tier"] = tier
    bw, bh = max(xres // tier, 64), max(yres // tier, 64)
    bg = tuple(int(c) for c in eyesy.color_picker_bg(eyesy.knob5))
    if _state["size"] != (xres, yres, tier):
        _state["size"] = (xres, yres, tier)
        _state["buf"] = pygame.Surface((bw, bh))
        _state["buf"].fill(bg)
        _state["prev"] = {}
    buf = _state["buf"]

    fg = eyesy.color_picker(eyesy.knob4)
    h0 = colorsys.rgb_to_hsv(fg[0] / 255.0, fg[1] / 255.0, fg[2] / 255.0)[0]

    # ---- knobs ----
    warp = max(-1.4, min(1.4, (eyesy.knob2 - 0.5) * 2 + mom[1] * 6.0))     # -1 .. +1, plus a whip when knob 2 is flicked
    twist = warp * 6.0                                        # degrees per frame, and which way
    zoom = 1.008 + abs(warp) * 0.07                           # the further from the middle, the harder it rushes in
    arms = 1 + int(eyesy.knob3 * 11.99)
    sparkles = 4 + int(eyesy.knob3 * 60 + env[2] * 120 * (0.5 + 0.5 * q))
    brush = (3 + eyesy.knob1 * 22) * (1.0 + env[0] * 0.8) * 2.0 / tier     # pixels of the small picture
    swing = 0.55 + eyesy.knob1 * 1.6 + clamp(mom[0] * 4.0, -0.4, 1.2)       # how far out the arms orbit

    # the whole tunnel drifts around a wandering centre, so it curves
    ox = bw / 2 + bw * 0.14 * math.sin(t * 0.55)
    oy = bh / 2 + bh * 0.14 * math.sin(t * 0.83 + 1.0)

    # ---- feedback: zoom and twist the last frame back into itself ----
    tw = math.radians(abs(twist))
    zoom = max(zoom, (math.cos(tw) + (bw / float(bh)) * math.sin(tw)) * 1.03)     # a hard twist needs a little extra zoom to avoid black corners
    rz = pygame.transform.rotozoom(buf, twist, zoom)
    tx = ox + (bw / 2.0 - ox) * zoom                          # zoom about the wandering centre, still covering the whole screen
    ty = oy + (bh / 2.0 - oy) * zoom
    buf.blit(rz, rz.get_rect(center=(int(tx), int(ty))))
    keep = 247 + int(env[4] * 7)                              # play knob 5 and the trails linger
    buf.fill((keep, keep, keep), special_flags=pygame.BLEND_RGB_MULT)                                   # fade a little
    _state["n"] = _state.get("n", 0) + 1
    if _state["n"] % 2 == 0:                                                                                     # ...toward the background (every other frame, twice as strongly)
        buf.fill((int(bg[0] * 0.018), int(bg[1] * 0.018), int(bg[2] * 0.018)), special_flags=pygame.BLEND_RGB_ADD)

    # ---- sparkles all over the screen: they get smeared along the flow, so you can see it react at once ----
    for _ in range(sparkles):
        x, y = random.random() * bw, random.random() * bh
        pygame.draw.circle(buf, hsv(h0 + random.random() * 0.4 + t * 0.1, 1.0, 1.0), (int(x), int(y)), 1 + int(brush * 0.15))

    # ---- fresh paint: fat orbiting brushes joined to where they were a moment ago ----
    R = min(bw, bh) * 0.12 * swing * (1.0 + 0.35 * math.sin(t * 0.9))
    for k in range(arms):
        a = t * (1.4 + 0.3 * math.sin(t * 0.3)) + 2 * math.pi * k / arms
        rr = R * (1.0 + 0.4 * math.sin(t * 1.7 + k * 1.3))
        x, y = ox + rr * math.cos(a), oy + rr * math.sin(a)
        hue = h0 + k / arms * (0.5 + 0.8 * env[3]) + t * 0.15 + mom[3] * 3.0     # the rainbow keeps rolling, and slams round when knob 4 is played
        prev = _state["prev"].get(k)
        if prev is not None:
            pygame.draw.line(buf, hsv(hue, 1.0, 1.0), prev, (x, y), max(2, int(brush * 1.6)))
        pygame.draw.circle(buf, hsv(hue, 0.55, 1.0), (int(x), int(y)), max(2, int(brush)))
        _state["prev"][k] = (x, y)
    for k in list(_state["prev"]):
        if k >= arms:
            del _state["prev"][k]
    pygame.draw.circle(buf, hsv(h0 + 0.5, 0.8, 1.0), (int(ox), int(oy)), int(brush * (0.7 + 0.4 * math.sin(t * 3.0))))

    if q > 0.6:
        pygame.transform.smoothscale(buf, (xres, yres), screen)    # scaled straight into the screen: no temporary picture
    else:
        pygame.transform.scale(buf, (xres, yres), screen)
