# OG Shroom Trip: a breathing, melting mushroom hallucination. A giant mushroom pulses in the middle while a ring
# of them orbits it, sprouts baby mushrooms off its own cap, and rains spores. Everything leaves smeared echo
# trails, the whole room tunnels in and out like it is breathing, and the picture ripples like heat haze.
#
# Knob convention (same in every mode):
#   knob1 = size            (how big the mushrooms are; they also swell and pulse harder as you play it)
#   knob2 = main motion     (the swirl: the middle is calm, either end spins and tunnels harder, in opposite directions)
#   knob3 = extra detail    (how many mushrooms, how many eyes/spots, and how many babies sprout off their caps)
#   knob4 = foreground color (base hue; the whole thing keeps drifting through the rainbow from it)
#   knob5 = background color
#
# Playing it (how you turn a knob changes the picture, not just where it ends up):
#   knob1       -> the mushrooms balloon and throb while you turn it
#   flick knob2 -> an extra whip of swirl that unwinds, so you can snap the whole world round on a beat
#   knob3       -> turning it makes the picture melt and ripple, and the spores pour out
#   knob4       -> the colors slam round the rainbow while you turn it
#   knob5       -> turning it flares the background and stretches the echo trails way out
#   key 0       -> tap it on the beat: a spore explosion, a jolt in size and a color jump (on the real device an audio hit does it)
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

_state = {"t": 0.0, "last": None, "buf": None, "full": None, "size": None, "burst": 0.0, "n": 0, "spores": [], "jump": 0.0}
_rng = random.Random(23)
# eight fixed "eyes" per cap: (across, up the dome, size); the first few show at low detail, all of them at high detail
_SPOTS = [(_rng.uniform(-1, 1), _rng.uniform(0.1, 0.85), _rng.uniform(0.07, 0.14)) for _ in range(8)]
_CAP_N = 22                                                    # points along the cap's arc

def setup(screen, eyesy):
    pass

def mushroom(buf, x, y, ang, s, hue, t, seed, nspots, sprout, depth):
    """one mushroom standing on (x, y), tilted by ang (0 = upright), s pixels tall; sprout > 0 grows baby mushrooms off the cap"""
    ca, sa = math.cos(ang), math.sin(ang)

    def P(lx, ly):
        return (x + (lx * ca - ly * sa) * s, y + (lx * sa + ly * ca) * s)

    # stem: sways like it is underwater, fat at the foot
    left, right = [], []
    for i in range(7):
        u = i / 6.0
        sw = 0.16 * math.sin(t * 1.6 + seed + u * 3.0) * u
        w = 0.17 - 0.07 * u + 0.12 * (1.0 - u) ** 4
        left.append(P(sw - w, -u))
        right.append(P(sw + w, -u))
    top_sw = 0.16 * math.sin(t * 1.6 + seed + 3.0)
    pygame.draw.polygon(buf, hsv(hue + 0.12, 0.3, 1.0), left + right[::-1])
    pygame.draw.lines(buf, hsv(hue + 0.55, 0.9, 1.0), False, left, 1)
    pygame.draw.lines(buf, hsv(hue + 0.55, 0.9, 1.0), False, right, 1)

    # cap: a wobbling dome with a wavy underside
    cw = 0.78 * (1.0 + 0.10 * math.sin(t * 1.3 + seed))
    ch = 0.56 * (1.0 + 0.16 * math.sin(t * 2.1 + seed * 1.7))
    top, bottom = [], []
    for j in range(_CAP_N + 1):
        th = math.pi * j / _CAP_N
        wob = 1.0 + 0.07 * math.sin(th * 7.0 + t * 2.6 + seed)
        c, sn = math.cos(th), math.sin(th)
        top.append(P(top_sw + cw * c * wob, -1.0 - ch * sn * wob))
        bottom.append(P(top_sw + cw * c, -1.0 + 0.13 * sn + 0.025 * math.sin(c * 14.0 + t * 3.0)))
    cap_col = hsv(hue, 0.85, 0.95)
    pygame.draw.polygon(buf, cap_col, top + bottom[::-1])
    for j in range(2, _CAP_N - 1, 2):                          # gills fanning out under the cap
        pygame.draw.line(buf, hsv(hue + 0.3, 0.8, 0.55), P(top_sw, -1.0 - 0.02), bottom[j], 1)

    # eyes: concentric rings that throb out of time with each other
    for i in range(nspots):
        u, v, r = _SPOTS[i]
        sx = top_sw + cw * u * math.sqrt(1.0 - v * v) * 0.85
        sy = -1.0 - ch * v * 0.9
        px, py = P(sx, sy)
        rr = r * s * (1.0 + 0.35 * math.sin(t * 3.5 + i * 1.9 + seed))
        if rr >= 1.5:
            pygame.draw.circle(buf, hsv(hue + 0.5, 0.9, 1.0), (int(px), int(py)), int(rr))
            pygame.draw.circle(buf, hsv(hue + 0.15, 0.6, 1.0), (int(px), int(py)), max(1, int(rr * 0.6)))
            pygame.draw.circle(buf, (10, 0, 20), (int(px), int(py)), max(1, int(rr * 0.25)))

    pygame.draw.lines(buf, hsv(hue + 0.5, 1.0, 1.0), True, top, 2 if s > 40 else 1)

    # babies sprout off the cap's rim and wave about
    if depth < 1 and sprout > 0.04:
        for b in range(3):
            th = math.pi * (0.18 + 0.32 * b) + 0.18 * math.sin(t * 1.1 + b + seed)
            c, sn = math.cos(th), math.sin(th)
            bx, by = P(top_sw + cw * c, -1.0 - ch * sn)
            mushroom(buf, bx, by, ang + math.pi / 2 - th, s * (0.12 + 0.26 * sprout), hue + 0.2 + b * 0.15,
                     t * 1.6, seed + b * 2.3, 2, 0.0, depth + 1)

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
    if getattr(eyesy, "trig", False):                          # the 0 key (or an audio hit): spore explosion, size jolt, color jump
        _state["burst"] = 1.0
        _state["jump"] += 0.17
    _state["burst"] *= math.exp(-dt * 2.6)
    burst = _state["burst"]
    level = 0.0
    try:
        ai = eyesy.audio_in
        level = clamp(max(abs(v) for v in ai[:100]) / 32768.0 * 1.5)    # how loud the room is right now
    except Exception:
        pass

    tier = 2
    bw, bh = max(xres // tier, 64), max(yres // tier, 64)
    fg = eyesy.color_picker(eyesy.knob4)
    h0 = colorsys.rgb_to_hsv(fg[0] / 255.0, fg[1] / 255.0, fg[2] / 255.0)[0] + _state["jump"]
    bgc = eyesy.color_picker_bg(eyesy.knob5)
    bg = tuple(int(c * (0.22 + 0.5 * env[4])) for c in bgc)    # a dim background that flares while knob 5 is turned
    if _state["size"] != (xres, yres):
        _state["size"] = (xres, yres)
        _state["buf"] = pygame.Surface((bw, bh))
        _state["buf"].fill(bg)
        _state["full"] = pygame.Surface((xres, yres))
    buf = _state["buf"]

    # ---- knobs ----
    warp = max(-1.5, min(1.5, (eyesy.knob2 - 0.5) * 2 + mom[1] * 6.0))     # -1 .. +1, plus a whip when knob 2 is flicked
    twist = warp * 5.0 + 0.4 * math.sin(t * 0.37)              # degrees per frame; never perfectly still
    breath = math.sin(t * 0.8)                                 # the room breathes in and out
    zoom = 1.012 + 0.012 * breath + abs(warp) * 0.05 + burst * 0.03 + level * 0.02
    n = 2 + int(eyesy.knob3 * 6.99)                            # 2 .. 8 orbiting mushrooms
    nspots = 2 + int(eyesy.knob3 * 5.99)                       # 2 .. 7 eyes per cap
    sprout = clamp(env[2] + max(0.0, eyesy.knob3 - 0.45) * 1.4)
    size = min(bw, bh) * (0.16 + eyesy.knob1 * 0.30) * (1.0 + env[0] * 0.5 + 0.07 * math.sin(t * 5.0) * env[0] + burst * 0.25 + level * 0.18 + 0.08 * breath)

    ox = bw / 2 + bw * 0.06 * math.sin(t * 0.43)
    oy = bh / 2 + bh * 0.06 * math.sin(t * 0.61 + 1.0)

    # ---- feedback: breathe the last frame in or out and swirl it, so everything leaves melting echoes ----
    tw = math.radians(abs(twist))
    zoom = max(zoom, (math.cos(tw) + (bw / float(bh)) * math.sin(tw)) * 1.02)     # a hard swirl needs a little extra zoom to avoid empty corners
    rz = pygame.transform.rotozoom(buf, twist, zoom)
    buf.blit(rz, rz.get_rect(center=(int(ox + (bw / 2.0 - ox) * zoom), int(oy + (bh / 2.0 - oy) * zoom))))
    keep = 232 + int(env[4] * 20) + int(eyesy.knob5 * 0)       # turning knob 5 stretches the trails out
    buf.fill((keep, keep, keep), special_flags=pygame.BLEND_RGB_MULT)
    _state["n"] += 1
    if _state["n"] % 2 == 0:                                   # fade toward the background (every other frame)
        buf.fill((int(bg[0] * 0.03), int(bg[1] * 0.03), int(bg[2] * 0.03)), special_flags=pygame.BLEND_RGB_ADD)

    # ---- spores drift up in lazy wobbling lines ----
    spores = _state["spores"]
    want = 6 + int(eyesy.knob3 * 14 + env[2] * 60 + burst * 120)
    for _ in range(min(want // 6 + 1, 14)):
        if len(spores) < 260:
            spores.append([random.random() * bw, bh + 4.0, random.random() * 6.28, random.random(), random.uniform(18, 60)])
    alive = []
    for sp in spores:
        sp[1] -= sp[4] * dt * (1.0 + burst * 3.0)
        sp[0] += math.sin(t * 1.7 + sp[2]) * 20.0 * dt
        if sp[1] > -6:
            alive.append(sp)
            pygame.draw.circle(buf, hsv(h0 + sp[3] * 0.6 + t * 0.1, 0.5, 1.0), (int(sp[0]), int(sp[1])), 1 + int(sp[3] * 2 + env[0] * 2))
    _state["spores"] = alive

    # ---- the ring of mushrooms, orbiting and tipped to point away from the middle ----
    spin = t * 0.22 * (1.0 if warp >= 0 else -1.0) + mom[1] * 3.0
    R = min(bw, bh) * (0.30 + 0.05 * math.sin(t * 0.7)) * (0.7 + eyesy.knob1 * 0.6)
    for k in range(n):
        a = spin + 2 * math.pi * k / n
        rr = R * (1.0 + 0.12 * math.sin(t * 1.3 + k * 1.7))
        px, py = ox + rr * math.cos(a), oy + rr * math.sin(a)
        hue = h0 + k / float(n) * 0.45 + t * 0.04 + mom[3] * 3.0 + env[3] * 0.2 * k
        mushroom(buf, px, py + size * 0.15, a + math.pi / 2 + 0.25 * math.sin(t * 0.9 + k), size * 0.55,
                 hue, t, k * 1.9, nspots, sprout, 0)

    # ---- the big one in the middle, pulsing with the breath ----
    mushroom(buf, ox, oy + size * 0.85, 0.12 * math.sin(t * 0.5) + mom[1] * 1.5, size * 1.3,
             h0 + 0.5 + mom[3] * 3.0 + t * 0.04, t, 0.0, nspots, sprout, 0)

    # ---- up to the screen with a ripple: each strip slides sideways so the picture melts like heat haze ----
    full = _state["full"]
    pygame.transform.smoothscale(buf, (xres, yres), full)
    amp = xres * (0.004 + 0.035 * env[2] + 0.02 * min(1.0, abs(mom[2]) * 6) + 0.02 * burst + 0.01 * level)
    step = 8
    for y in range(0, yres, step):
        dx = int(amp * math.sin(y * 0.022 + t * 2.4) + amp * 0.5 * math.sin(y * 0.057 - t * 3.1))
        h = min(step, yres - y)
        screen.blit(full, (dx, y), (0, y, xres, h))
        if dx > 0:
            screen.blit(full, (dx - xres, y), (0, y, xres, h))
        elif dx < 0:
            screen.blit(full, (dx + xres, y), (0, y, xres, h))

def draw(screen, eyesy):
    _draw(screen, eyesy)
