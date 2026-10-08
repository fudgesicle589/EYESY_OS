# OGBicycleDay: April 19, 1943. Albert Hofmann, 3 days after his first accidental dose of LSD, takes a deliberate one in
# his lab in Basel, and as it comes on he cycles home through a world that is breathing, melting and turning to
# kaleidoscopes. This is that ride, built from the way people describe the visuals (Hofmann's own notes, the Klüver
# "form constants" that every account keeps coming back to, and a lot of trip reports):
#   * a hyperspace TUNNEL that you fly down, made of mirrored kaleidoscope segments, spirals and lattices in
#     iridescent colors that slide through the whole rainbow (and that "breathe" in and out)
#   * glowing concentric rings, spiral arms of beads, and a MANDALA EYE at the vanishing point; small EYES drift
#     out of the tunnel and watch you ("eyes everywhere", faces in the patterns)
#   * the ROAD is a rainbow ribbon that rolls like waves, and the bike really rides over its hills
#   * the world MELTS: rows of the picture slide side to side, edges grow rainbow halos (auras) and
#     the rider leaves colored trails (echoes) that lag behind in time, with a bit of visual-snow grain on top
#   * the rider is a pedalling silhouette (legs bend with real two-bone IK, wheels spin and make moire with the
#     scenery) with a spiral eye, and a scarf streaming behind
#
# Knobs (project convention, plus the "dose" idea on knob 3):
#   knob1 = size       how big the rider is and how big the swirls in the tunnel are
#   knob2 = motion     how hard you pedal and how fast you fly down the tunnel (0 = coasting, 1 = flat out)
#   knob3 = DOSE       extra detail: from a clean tunnel (0) to full peak (1): more kaleidoscope segments, more
#                      melting, more trails, more eyes, more color bands
#   knob4 = foreground color  (halos, rings, road, eyes)
#   knob5 = background color  (the tunnel's palette and its dark tones)
#
# Playing it (how you turn a knob matters, not just where it ends up):
#   knob1       -> flick it and everything swells then settles, like a breath
#   knob2       -> flick it up and you surge forward (the whole world rushes), then you settle back
#   knob3       -> while you are turning it the picture melts harder and the eyes pop wide open
#   knob4/knob5 -> the colors whoosh round the rainbow while you turn them, then settle
# Loud sound also dilates the pupils, opens the eyes and makes the picture ripple.
import colorsys
import math
import random
import time
import pygame

TAU = math.pi * 2.0
sin, cos = math.sin, math.cos

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))

def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, clamp(s), clamp(v))
    return (int(r * 255), int(g * 255), int(b * 255))

_state = {"last": None, "t": 0.0, "fly": 0.0, "ph": 0.0, "crank": 0.0, "wheel": 0.0, "dist": 0.0,
          "roll": 0.0, "lvl": 0.0, "surge": 0.0, "tmp": None, "tmp_size": None}
_cache = {"lut_key": None, "lut": None, "grid_key": None, "an": None, "dp": None, "poly": {}}
_play = {"prev": None, "vel": [0.0] * 5, "env": [0.0] * 5, "mom": [0.0] * 5}
_eyes = [(random.random(), random.random(), random.random()) for _ in range(6)]       # (arm angle, start phase, blink offset)

# ---- playing the knobs: HOW a knob is being turned matters as much as where it sits ----
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

# ---- adaptive quality: if this pattern runs slowly (say, on a Raspberry Pi) it quietly draws less detail ----
_lod = {"q": 1.0, "avg": 0.0, "t0": 0.0}
LOD_BUDGET = 0.028

def setup(screen, eyesy):
    pass

def draw(screen, eyesy):
    _lod["t0"] = time.perf_counter()
    _draw(screen, eyesy)
    dt = time.perf_counter() - _lod["t0"]
    _lod["avg"] = _lod["avg"] * 0.9 + dt * 0.1 if _lod["avg"] else dt
    if _lod["avg"] > LOD_BUDGET:
        _lod["q"] = max(0.25, _lod["q"] - 0.04)
    elif _lod["avg"] < LOD_BUDGET * 0.6:
        _lod["q"] = min(1.0, _lod["q"] + 0.01)

# ------------------------------------------------------------------------------------------ the tunnel (background)
CX, CY = 0.62, 0.42               # where the vanishing point sits on screen (fractions of width / height)

def _grid(W, H):
    """for each cell of the small background grid: its angle round the vanishing point (0..1) and its 'depth' down the tunnel"""
    if _cache["grid_key"] != (W, H):
        asp = W / H
        an, dp = [], []
        for j in range(H):
            ra, rd = [], []
            for i in range(W):
                x = ((i + 0.5) / W - CX) * asp
                y = (j + 0.5) / H - CY
                ra.append(math.atan2(y, x) / TAU + 0.5)
                rd.append(min(2.2, 0.22 / (math.hypot(x, y) + 0.04)))
            an.append(ra)
            dp.append(rd)
        _cache["grid_key"], _cache["an"], _cache["dp"] = (W, H), an, dp
    return _cache["an"], _cache["dp"]

def _lut(h0, bands, bgc):
    """256 iridescent colors: one full trip round the rainbow, with bright and dark bands that melt toward the background tone"""
    key = (round(h0, 2), bands, bgc[0] >> 3, bgc[1] >> 3, bgc[2] >> 3)
    if _cache["lut_key"] != key:
        lut = []
        for i in range(256):
            p = i / 255.0
            k = 0.5 + 0.5 * sin(TAU * p * bands)
            r, g, b = colorsys.hsv_to_rgb((h0 + p + 0.07 * sin(TAU * p * 3)) % 1.0, 0.72 + 0.26 * k, 0.28 + 0.72 * k)
            m = (1.0 - k) * 0.45
            lut.append(bytes((int(clamp(b * 255 * (1 - m) + bgc[2] * 0.35 * m, 0, 255)),      # blue, green, red, alpha
                              int(clamp(g * 255 * (1 - m) + bgc[1] * 0.35 * m, 0, 255)),
                              int(clamp(r * 255 * (1 - m) + bgc[0] * 0.35 * m, 0, 255)), 255)))
        _cache["lut_key"], _cache["lut"] = key, lut
    return _cache["lut"]

def _tunnel(screen, xres, yres, t, fly, spin, N, detail, zoom, roll, h0, bgc, q):
    W = int(52 + 52 * q)
    H = max(2, int(W * yres / xres))
    an, dp = _grid(W, H)
    lut = _lut(h0, 3 + int(detail * 4.99), bgc)
    tt = fly + 0.9 * sin(t * 0.8)                                  # the breathing: the whole tunnel swells in and out
    tw = 0.3 + detail * 0.7                                        # spiral twist
    w2, kk, dd = 11.0 + 12.0 * detail, 26.0 + 22.0 * detail, 30.0
    k1, k2, k3 = 4.5 * zoom, 1.8 * zoom, 8.0 * zoom
    rows = []
    for j in range(H):
        afr = [abs((a * N + spin + d * tw) % 1.0 - 0.5) for a, d in zip(an[j], dp[j])]      # mirror-folded angle = kaleidoscope
        rows.append(b"".join([lut[int((sin(d * k1 + tt + af * 3.0) + sin(af * w2 + d * k2 - tt * 0.6)
                                       + 0.7 * sin(d * k3 - tt * 1.7 + af * 5.0)) * kk + roll + d * dd) & 255]
                              for af, d in zip(afr, dp[j])]))
    small = pygame.image.frombuffer(b"".join(rows), (W, H), "BGRA")
    pygame.transform.smoothscale(small, (xres, yres), screen)

# ------------------------------------------------------------------------------------------ geometry painted over it
def _angles(n):
    if n not in _cache["poly"]:
        _cache["poly"][n] = [(cos(TAU * k / n), sin(TAU * k / n)) for k in range(n)]
    return _cache["poly"][n]

def _rings(screen, cx, cy, Rmax, ph, t, N, hue, detail, q):
    """flower-shaped rings that grow out of the vanishing point toward you, each one twisted a bit more"""
    NR = 9 + int(9 * q)
    n = 36 + int(36 * q)
    cs = _angles(n)
    Rmin = Rmax * 0.025
    order = sorted(range(NR), key=lambda i: (i / NR + ph) % 1.0)
    wob = 0.08 + 0.18 * detail
    for i in order:
        z = (i / NR + ph) % 1.0
        r = Rmin * (Rmax / Rmin) ** z
        rot = (t * 0.25 + z * 2.5) * (1 if i % 2 == 0 else -1)
        pts = [(cx + r * (1 + wob * cos(N * 2 * TAU * k / n + rot)) * c, cy + r * (1 + wob * cos(N * 2 * TAU * k / n + rot)) * s)
               for k, (c, s) in enumerate(cs)]
        hh = hue + z * 0.9 + i * 0.07
        v = 0.3 + 0.7 * z
        w = 1 + int(z * z * (5 + detail * 9))
        pygame.draw.polygon(screen, hsv(hh, 0.9, v * 0.45), pts, w + 5)
        pygame.draw.polygon(screen, hsv(hh + 0.04, 0.55, v), pts, w)

def _beads(screen, cx, cy, Rmax, ph, t, hue, detail, q):
    """spiral arms of glowing beads swirling out of the center"""
    arms = 5 + int(detail * 3)
    per = 14 + int(12 * q)
    Rmin = Rmax * 0.03
    for a in range(arms):
        for m in range(per):
            s = (m / per + ph * 0.5) % 1.0
            r = Rmin * (Rmax * 0.9 / Rmin) ** s
            ang = a * TAU / arms + s * (2.4 + detail * 1.5) * TAU + t * 0.35
            x, y = cx + r * cos(ang), cy + r * sin(ang)
            rad = 1.5 + s * s * Rmax * 0.025
            pygame.draw.circle(screen, hsv(hue + a / arms + s * 0.5, 0.9, 0.35 + 0.4 * s), (x, y), rad * 1.9)
            pygame.draw.circle(screen, hsv(hue + a / arms + s * 0.5, 0.35, 1.0), (x, y), rad)

def _eye(screen, x, y, w, hue, look, opn, dil):
    """one almond-shaped eye: pale lens, colored iris, black pupil"""
    h = w * 0.5 * opn
    if h < 2:
        return
    n = 12
    top = [(x + w * cos(math.pi * k / n), y - h * sin(math.pi * k / n)) for k in range(n + 1)]
    bot = [(x + w * cos(math.pi * k / n), y + h * sin(math.pi * k / n)) for k in range(n - 1, 0, -1)]
    lens = top + bot
    pygame.draw.polygon(screen, hsv(hue + 0.5, 0.12, 1.0), lens)
    ir = h * 0.8
    ix = x + look * w * 0.18
    pygame.draw.circle(screen, hsv(hue, 0.9, 1.0), (ix, y), ir)
    pygame.draw.circle(screen, hsv(hue + 0.15, 0.9, 0.7), (ix, y), ir * 0.7, max(1, int(ir * 0.12)))
    pygame.draw.circle(screen, (0, 0, 0), (ix, y), ir * (0.25 + 0.4 * dil))
    pygame.draw.circle(screen, (255, 255, 255), (ix - ir * 0.3, y - ir * 0.3), max(1, ir * 0.14))
    pygame.draw.polygon(screen, (10, 0, 20), lens, max(2, int(w * 0.05)))

def _wandering_eyes(screen, cx, cy, Rmax, ph, t, hue, detail, lvl, env3, bike):
    count = int(detail * 6.99)
    Rmin = Rmax * 0.03
    for idx in range(count):
        a0, s0, b0 = _eyes[idx]
        s = (s0 + ph * 0.35) % 1.0
        r = Rmin * (Rmax * 0.7 / Rmin) ** s
        ang = a0 * TAU + s * 2.0 * TAU + t * 0.2
        x, y = cx + r * cos(ang), cy + r * sin(ang)
        w = 8 + s * s * Rmax * 0.16
        blink = clamp(1.3 + 1.2 * sin(t * 0.9 + b0 * 20), 0.0, 1.0)                  # blinks every few seconds
        look = clamp((bike[0] - x) / (Rmax * 0.6), -1, 1)                            # the eyes watch the rider
        _eye(screen, x, y, w, hue + s * 0.6 + idx * 0.13, look, clamp(blink * (0.55 + 0.45 * s) + env3 * 0.4 + lvl * 0.4), clamp(lvl + env3))

def _mandala(screen, cx, cy, R, t, N, hue, dil, detail):
    """the big mandala eye at the end of the tunnel"""
    rays = N * 6
    for k in range(rays):
        a = TAU * k / rays + t * 0.12
        r1 = R * (1.05 + 0.3 * sin(k * 1.7 + t * 1.5))
        pygame.draw.line(screen, hsv(hue + k / rays * 2.0, 0.85, 1.0), (cx + R * 0.5 * cos(a), cy + R * 0.5 * sin(a)),
                         (cx + r1 * cos(a), cy + r1 * sin(a)), max(1, int(R * 0.05)))
    for L in range(5):
        rr = R * (0.95 - 0.17 * L)
        pts = []
        for k in range(N * 2):
            a = TAU * k / (N * 2) + t * 0.3 * (1 if L % 2 else -1) + L * 0.4
            rk = rr if k % 2 == 0 else rr * 0.62
            pts.append((cx + rk * cos(a), cy + rk * sin(a)))
        col = hsv(hue + L * 0.17 + t * 0.05, 0.9, 1.0) if L % 2 == 0 else hsv(hue + 0.5 + L * 0.1, 0.8, 0.22)
        pygame.draw.polygon(screen, col, pts)
    pygame.draw.circle(screen, (0, 0, 0), (cx, cy), R * (0.12 + 0.15 * dil))
    pygame.draw.circle(screen, hsv(hue + 0.5, 0.3, 1.0), (cx, cy), R * (0.12 + 0.15 * dil), max(1, int(R * 0.03)))
    pygame.draw.circle(screen, (255, 255, 255), (cx - R * 0.07, cy - R * 0.07), max(1, int(R * 0.035)))

# ------------------------------------------------------------------------------------------ the road and the rider
def _road_y(x, dist, gy, A1, A2, bump):
    return gy + A1 * sin((x + dist) * 0.0045) + A2 * sin((x + dist) * 0.011 + 1.3) + bump * sin((x + dist) * 0.023)

def _ribbon(screen, xres, yres, dist, gy, A1, A2, bump, th, hue, t, q):
    """the rainbow road: three stacked ribbons of sliding colored stripes, each one a beat behind the one above it"""
    step = max(14, int(xres / (30 + 14 * q)))
    xs = list(range(-step, xres + 2 * step, step))
    for layer in (2, 1, 0):
        off = layer * th * 1.15
        for a, b in zip(xs, xs[1:]):
            ya = _road_y(a, dist - layer * 70, gy, A1, A2, bump) + off
            yb = _road_y(b, dist - layer * 70, gy, A1, A2, bump) + off
            wa = int((a + dist) / step)
            col = hsv(hue + (a + dist) * 0.0012 + layer * 0.17 + t * 0.05, 0.95 - 0.1 * (wa % 2), (1.0 if wa % 2 else 0.62) * (1.0 - 0.22 * layer))
            pygame.draw.polygon(screen, col, [(a, ya), (b, yb), (b, yb + th), (a, ya + th)])
        pygame.draw.lines(screen, hsv(hue + 0.5 + layer * 0.1, 0.25, 1.0), False,
                          [(x, _road_y(x, dist - layer * 70, gy, A1, A2, bump) + off) for x in xs], 3)

def _ik(a, b, l1, l2, s):
    """two-bone limb: where the middle joint (knee or elbow) sits when the end joints are at a and b"""
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = clamp(math.hypot(dx, dy), 0.05, l1 + l2 - 0.001)
    al = math.acos(clamp((l1 * l1 + d * d - l2 * l2) / (2 * l1 * d), -1, 1))
    base = math.atan2(dy, dx)
    return (a[0] + l1 * cos(base + s * al), a[1] + l1 * sin(base + s * al))

def _rider(tf, crank, wheel, t, lvl):
    """the bike and the man as a list of pieces in screen coordinates: ('l', a, b, width), ('c', center, radius), ('r', center, radius, width)
    (sizes in bike units: 1 = a wheel's radius). Local coordinates: x forward, y up, origin on the rear axle."""
    P = []
    R, F = (0.0, 0.0), (3.0, 0.0)
    BB, S, HT, HB, BAR = (1.25, -0.2), (0.78, 1.5), (2.4, 1.55), (2.55, 1.1), (2.45, 1.95)
    for a, b, w in ((R, BB, 0.1), (R, S, 0.1), (BB, S, 0.12), (S, HT, 0.1), (BB, HT, 0.12), (HT, F, 0.1), (HT, BAR, 0.1), (BAR, (2.2, 2.0), 0.08)):
        P.append(('l', tf(*a), tf(*b), w))
    P.append(('l', tf(0.55, 1.57), tf(1.0, 1.55), 0.12))                                       # saddle
    P.append(('r', tf(*R), 1.0, 0.14))
    P.append(('r', tf(*F), 1.0, 0.14))
    P.append(('c', tf(*BB), 0.2))
    hip = (0.8, 1.7 + 0.04 * sin(crank * 2))
    sho = (1.75, 3.1)
    head = (2.1, 3.62)
    P.append(('l', tf(*hip), tf(*sho), 0.72))                                                  # torso
    P.append(('c', tf(*hip), 0.38))
    P.append(('c', tf(*sho), 0.36))
    P.append(('l', tf(1.85, 3.2), tf(*head), 0.3))                                             # neck
    P.append(('c', tf(*head), 0.36))                                                           # head
    for k, side in enumerate((0.0, math.pi)):                                                  # both legs
        ped = (BB[0] + 0.5 * cos(crank + side), BB[1] + 0.5 * sin(crank + side))
        knee = _ik(hip, ped, 1.2, 1.25, 1)
        P.append(('l', tf(*hip), tf(*knee), 0.4))
        P.append(('l', tf(*knee), tf(*ped), 0.28))
        P.append(('l', tf(*ped), tf(ped[0] + 0.4, ped[1] - 0.03), 0.2))                        # shoe
        P.append(('l', tf(*BB), tf(*ped), 0.07))                                               # crank arm
        P.append(('c', tf(*knee), 0.17))
    elbow = _ik(sho, BAR, 1.0, 1.05, -1)                                                       # arm
    P.append(('l', tf(*sho), tf(*elbow), 0.24))
    P.append(('l', tf(*elbow), tf(*BAR), 0.2))
    P.append(('c', tf(*BAR), 0.11))
    prev = tf(1.7, 3.25)                                                                       # a scarf streaming back in the wind
    for k in range(1, 11):
        x = 1.7 - k * 0.32
        y = 3.2 - k * 0.04 + (0.06 + 0.035 * k) * sin(k * 0.9 - t * 9.0) * (1 + lvl)
        cur = tf(x, y)
        P.append(('l', prev, cur, 0.2 - k * 0.015))
        prev = cur
    return P

def _spokes(screen, c, rad, ang, n, col, w):
    for k in range(n):
        a = ang + TAU * k / n
        pygame.draw.line(screen, col, c, (c[0] + rad * cos(a), c[1] + rad * sin(a)), w)

def _paint(screen, prims, U, col, e):
    """every piece fattened by e pixels in one color; stacking these in different colors makes the rainbow aura"""
    for p in prims:
        if p[0] == 'l':
            w = max(1, int(p[3] * U + 2 * e))
            pygame.draw.line(screen, col, p[1], p[2], w)
            if w > 3:
                r = w * 0.5
                pygame.draw.circle(screen, col, p[1], r)
                pygame.draw.circle(screen, col, p[2], r)
        elif p[0] == 'c':
            pygame.draw.circle(screen, col, p[1], p[2] * U + e)
        else:
            pygame.draw.circle(screen, col, p[1], p[2] * U + e, max(1, int(p[3] * U + 2 * e)))

def _ghost(screen, prims, U, col):
    """a thin colored outline of the rider: one of the lagging trails"""
    for p in prims:
        if p[0] == 'l':
            pygame.draw.line(screen, col, p[1], p[2], max(2, int(p[3] * U * 0.18)))
        elif p[0] == 'c':
            pygame.draw.circle(screen, col, p[1], p[2] * U, 2)
        else:
            pygame.draw.circle(screen, col, p[1], p[2] * U, 3)

# ------------------------------------------------------------------------------------------ the main loop
def _draw(screen, eyesy):
    xres, yres = eyesy.xres, eyesy.yres
    now = time.time()
    if _state["last"] is None:
        _state["last"] = now
    dt = max(0.001, min(now - _state["last"], 0.1))
    _state["last"] = now
    q = _lod["q"]

    vel, env, mom = knob_play(eyesy, dt)
    try:
        level = clamp(max(abs(v) for v in eyesy.audio_in[:100]) / 30000.0)
    except Exception:
        level = 0.0
    _state["lvl"] += (level - _state["lvl"]) * min(1.0, dt * (14 if level > _state["lvl"] else 4))
    lvl = _state["lvl"]
    if getattr(eyesy, "trig", False):
        lvl = max(lvl, 0.8)

    detail = eyesy.knob3
    # ---- the speed of everything ----
    _state["surge"] = _state["surge"] * math.exp(-dt * 1.2) + clamp(mom[1] * 12.0, -1.5, 3.0) * dt * 3.0
    speed = clamp(0.12 + eyesy.knob2 * 1.9 + _state["surge"], 0.0, 4.5)
    _state["t"] += dt
    t = _state["t"]
    cadence = 1.5 + speed * 4.2                                            # pedal turns, radians per second
    _state["crank"] += cadence * dt
    _state["wheel"] += cadence * 2.2 * dt
    _state["fly"] += speed * 1.2 * dt                                      # how fast you fall down the tunnel
    _state["ph"] = (_state["ph"] + speed * 0.15 * dt) % 1.0
    # (the road scrolls at exactly the speed the wheels roll, in pixels)
    U = yres * (0.07 + 0.06 * eyesy.knob1) * (1.0 + clamp(mom[0] * 2.0, -0.25, 0.5))
    _state["dist"] += cadence * 2.2 * U * dt

    # ---- colors ----
    fgc = tuple(int(c) for c in eyesy.color_picker(eyesy.knob4))
    hf = colorsys.rgb_to_hsv(fgc[0] / 255.0, fgc[1] / 255.0, fgc[2] / 255.0)
    hue = hf[0] if hf[1] > 0.2 else eyesy.knob4
    bgc = tuple(int(c) for c in eyesy.color_picker_bg(eyesy.knob5))
    hb = colorsys.rgb_to_hsv(bgc[0] / 255.0, bgc[1] / 255.0, bgc[2] / 255.0)
    hbg = hb[0] if hb[1] > 0.2 else eyesy.knob5
    _state["roll"] += dt * (6.0 + speed * 10.0)
    roll = _state["roll"] + mom[3] * 600 + mom[4] * 600

    N = 3 + int(detail * 6.99)                                             # kaleidoscope segments
    zoom = (1.7 - eyesy.knob1 * 1.0) * (1.0 + clamp(mom[0] * 2.0, -0.4, 1.0))
    spin = t * 0.07

    # ---- 1. the tunnel ----
    _tunnel(screen, xres, yres, t, _state["fly"], spin, N, detail, zoom, roll, hbg, bgc, q)

    cx, cy = xres * CX + 6 * sin(t * 0.7), yres * CY + 6 * cos(t * 0.9)
    Rmax = math.hypot(xres, yres) * 0.6
    ph = _state["ph"]

    # ---- 2. rings, beads, eyes, mandala ----
    _rings(screen, cx, cy, Rmax, ph, t, N, hue, detail, q)
    _beads(screen, cx, cy, Rmax, ph, t, hue, detail, q)

    # ---- 3. the road under the rider (and the rider's position on it) ----
    gy = yres * 0.80
    A1 = yres * (0.025 + 0.05 * detail + 0.03 * lvl)
    A2 = yres * (0.012 + 0.02 * detail)
    bump = yres * 0.006
    th = yres * 0.05
    dist = _state["dist"]
    ox = xres * 0.27
    oy = _road_y(ox, dist, gy, A1, A2, bump) - U
    fx = ox + 3.0 * U
    for _ in range(3):
        fy = _road_y(fx, dist, gy, A1, A2, bump) - U
        fx = ox + math.sqrt(max(1.0, (3.0 * U) ** 2 - (fy - oy) ** 2))
    fy = _road_y(fx, dist, gy, A1, A2, bump) - U
    theta = math.atan2(oy - fy, fx - ox)
    ct, st = cos(theta), sin(theta)

    _wandering_eyes(screen, cx, cy, Rmax, ph, t, hue, detail, lvl, env[2], (ox + 1.7 * U, oy - 3.0 * U))
    _mandala(screen, cx, cy, yres * (0.085 + 0.01 * sin(t * 1.3) + 0.02 * lvl), t, N, hue, clamp(0.3 + lvl + env[2]), detail)
    _ribbon(screen, xres, yres, dist, gy, A1, A2, bump, th, hue, t, q)

    # ---- 4. the rider: lagging trails, rainbow aura, black silhouette ----
    def make_tf(px, py):
        return lambda x, y: (px + (x * ct - y * st) * U, py - (x * st + y * ct) * U)

    crank, wheel = _state["crank"], _state["wheel"]
    echoes = int(detail * 3.99)
    for k in range(echoes, 0, -1):
        px = ox - k * 0.9 * U * ct
        py = oy + k * 0.9 * U * st - U * 0.3 * k * sin(t * 2.0 + k)
        gp = _rider(make_tf(px, py), crank - k * 0.55, wheel, t - k * 0.15, lvl)
        _ghost(screen, gp, U, hsv(hue + k * 0.18 + t * 0.1, 1.0, 1.0))

    pr = _rider(make_tf(ox, oy), crank, wheel, t, lvl)
    auras = 3 + int(2 * q)
    for k in range(auras, 0, -1):
        e = k * U * 0.11 * (1.0 + 0.5 * lvl)
        _paint(screen, pr, U, hsv(hue + k * 0.11 + t * 0.12, 1.0, 1.0), e)
    _paint(screen, pr, U, (6, 0, 14), 0)
    nsp = 12 + int(10 * q)
    for hub in (make_tf(ox, oy)(0.0, 0.0), make_tf(ox, oy)(3.0, 0.0)):
        _spokes(screen, hub, U * 0.93, wheel, nsp, (6, 0, 14), 2)
        pygame.draw.circle(screen, hsv(hue + 0.5, 0.4, 1.0), hub, U * 0.1)
    tfm = make_tf(ox, oy)
    ex, ey = tfm(2.25, 3.7)                                                                    # the rider's eye: a tiny spiral
    pygame.draw.circle(screen, (255, 255, 255), (ex, ey), U * 0.13)
    pygame.draw.circle(screen, hsv(hue, 1.0, 1.0), (ex, ey), U * 0.09)
    pygame.draw.circle(screen, (0, 0, 0), (ex, ey), U * (0.03 + 0.05 * clamp(lvl + env[2])))

    # ---- 5. everything melts: rows of the picture slide sideways in waves ----
    amp = (3.0 + 20.0 * detail + 30.0 * env[2] + 20.0 * lvl) * yres / 720.0
    stripe = max(4, int((yres / 90.0) * (2.0 - q)))
    if _state["tmp_size"] != (xres, yres):
        _state["tmp"] = pygame.Surface((xres, yres), 0, screen)
        _state["tmp_size"] = (xres, yres)
    tmp = _state["tmp"]
    tmp.blit(screen, (0, 0))
    fr = 0.012 + 0.015 * detail
    for y in range(0, yres, stripe):
        dx = int(amp * sin(y * fr + t * 1.6) + amp * 0.5 * sin(y * fr * 2.7 - t * 2.3))
        if dx:
            screen.blit(tmp, (dx, y), (0, y, xres, stripe))

    # ---- 6. visual snow: a faint shimmer of grain ----
    rnd = random.random
    for _ in range(int((40 + 160 * detail) * q)):
        screen.fill(hsv(rnd(), 0.4, 1.0), (int(rnd() * xres), int(rnd() * yres), 2, 2))
