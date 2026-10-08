# OGJungleStream
# A low-detail, all-outline jungle at night with a stream winding down through it toward you. Everything is a line
# drawing, and everything DANCES like the plants in Mario games: they all bob together on the beat, squashing down and
# stretching up, the piranha-style bulb plants chomp, the big leaves flap, ferns bounce, tree canopies pump and the
# vines swing. The beat ripples through the jungle as a wave (each plant is a touch behind the one before it), so it
# feels like one big creature breathing to the bass. Made for wobbly, half-time bass music.
#
# It locks onto the audio kick (the `0` key on the desktop is a kick) and learns the tempo from it. With no kick it
# keeps dancing on a steady gentle tempo of its own. Every kick also sends a ripple across the stream and pumps its banks.
#
# Knobs (colors follow the usual convention, the rest is this mode's own set):
#   knob1 = GROWTH      how big and lush the jungle is. Flick it and it overshoots, like a growth spurt, then settles.
#   knob2 = DANCE       how hard the plants dance: 0 = nearly still, high = full Mario bounce and chomp. Flick it and a
#                       gust of wind whips through the whole jungle and swings back.
#   knob3 = STREAM      how fast the water flows (and a touch of wobble). Turn it and the whole
#                       river sloshes sideways, then rights itself; fast flicks make it surge wide.
#   knob4 = foreground color  (the plants and trees). Turn it fast and the colors fan out into a rainbow by depth.
#   knob5 = background color  Flick it and the fireflies swarm and the moon flares.
import colorsys
import math
import random
import time
import pygame

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))

def mix(a, b, t):
    t = clamp(t)
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))

def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, clamp(s), clamp(v))
    return (int(r * 255), int(g * 255), int(b * 255))

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

# ---------------------------------------------------------------- state
_S = {"last": None, "t": 0.0, "phase": 0.0, "bpm": 150.0, "beat": 0.0, "last_trig": -99.0, "flow": 0.0,
      "plants": None, "flies": None, "vines": None, "ripples": [], "wob": 0.0, "target": 0.0, "sm": None, "size": (0, 0)}

def build(xres, yres):
    rng = random.Random(11)
    plants = []
    kinds = ["bulb", "leaf", "fern", "tree", "bulb", "leaf", "fern", "fern", "leaf", "bulb"]
    n = 28
    for i in range(n):
        d = 0.14 + 0.84 * (i / (n - 1.0)) ** 1.15
        side = -1 if i % 2 == 0 else 1
        kind = rng.choice(kinds)
        if kind == "tree" and d > 0.6:
            kind = "leaf"
        if kind != "tree" and d < 0.22:
            kind = "fern"
        off = rng.uniform(0.02, 0.12) if kind != "tree" else rng.uniform(0.25, 0.5)
        plants.append({"kind": kind, "d": d, "side": side, "off": off, "lag": rng.uniform(0.0, 0.3) + d * 0.35,
                       "seed": rng.uniform(0, 6.28), "n": rng.randint(3, 5), "big": rng.uniform(0.8, 1.2)})
    # a few extras on the far side of the banks so it feels dense, and corner leaves that frame the picture
    for i in range(9):                                        # a wall of trees in the middle distance, both sides
        plants.append({"kind": "tree", "d": 0.08 + 0.05 * i + rng.uniform(0, 0.03), "side": -1 if i % 2 == 0 else 1,
                       "off": rng.uniform(0.3, 1.6), "lag": rng.uniform(0.0, 0.35), "seed": rng.uniform(0, 6.28),
                       "n": 4, "big": rng.uniform(0.9, 1.5)})
    for d, side in ((0.5, -1), (0.62, 1), (0.8, -1), (0.9, 1), (0.42, 1), (0.7, -1), (0.35, -1)):
        plants.append({"kind": "fern", "d": d, "side": side, "off": rng.uniform(0.45, 0.8), "lag": rng.uniform(0, 0.3),
                       "seed": rng.uniform(0, 6.28), "n": 5, "big": 1.0})
    for side in (-1, 1):
        plants.append({"kind": "leaf", "d": 1.0, "side": side, "off": 0.55, "lag": 0.35, "seed": rng.uniform(0, 6.28),
                       "n": 5, "big": 1.35})
    plants.sort(key=lambda p: p["d"])
    _S["plants"] = plants
    _S["flies"] = [{"x": rng.random(), "y": rng.uniform(0.15, 0.95), "s": rng.uniform(0, 6.28), "sp": rng.uniform(0.4, 1.2)}
                   for _ in range(26)]
    _S["vines"] = [{"x": rng.uniform(0.04, 0.96), "len": rng.uniform(0.18, 0.42), "s": rng.uniform(0, 6.28),
                    "lag": rng.uniform(0, 0.3)} for _ in range(9)]
    _S["size"] = (xres, yres)

def setup(screen, eyesy):
    build(eyesy.xres, eyesy.yres)

# ---------------------------------------------------------------- drawing helpers
def bez(p0, p1, p2, n=8):
    pts = []
    for i in range(n + 1):
        u = i / float(n)
        a, b, c = (1 - u) ** 2, 2 * u * (1 - u), u * u
        pts.append((a * p0[0] + b * p1[0] + c * p2[0], a * p0[1] + b * p1[1] + c * p2[1]))
    return pts

def line(screen, col, pts, w):
    if len(pts) > 1:
        pygame.draw.lines(screen, col, False, pts, max(1, int(w)))

def leaf(screen, col, w, bx, by, ang, length, wid, bend):
    """one pointed leaf outline with a midrib. ang is from straight up (radians, + leans right)."""
    dx, dy = math.sin(ang), -math.cos(ang)
    px, py = -dy, dx
    p0 = (bx, by)
    p1 = (bx + dx * length * 0.6, by + dy * length * 0.6)
    p2 = (bx + dx * length + px * bend * length, by + dy * length + py * bend * length)
    mid = bez(p0, p1, p2, 8)
    left, right = [], []
    for i, (mx, my) in enumerate(mid):
        u = i / 8.0
        if i < 8:
            tx, ty = mid[i + 1][0] - mx, mid[i + 1][1] - my
        else:
            tx, ty = mx - mid[i - 1][0], my - mid[i - 1][1]
        tl = math.hypot(tx, ty) or 1.0
        nx, ny = -ty / tl, tx / tl
        ww = wid * math.sin(math.pi * u ** 0.75)
        left.append((mx + nx * ww, my + ny * ww))
        right.append((mx - nx * ww, my - ny * ww))
    pygame.draw.lines(screen, col, True, left + right[::-1], w)
    line(screen, col, mid[:7], 1)
    return mid[-1]

def draw_bulb(screen, col, w, bx, by, sc, dz, lean, st, ph, p, dance):
    """the Mario piranha-style plant: a bouncing stem with a chomping pacman head"""
    s = sc * dz * p["big"]
    h = 120 * s * (1.0 + 0.28 * dance * st)
    top = (bx + lean * h * 0.55, by - h)
    stem = bez((bx, by), (bx - lean * h * 0.1, by - h * 0.55), top, 8)
    for off in (-3, 3):
        line(screen, col, [(x + off * s, y) for x, y in stem], w)
    # leaves at the base, flapping against the beat
    for sd in (-1, 1):
        leaf(screen, col, w, bx, by - 4 * s, sd * (0.9 + 0.25 * dance * math.sin(ph + sd)), 60 * s, 12 * s, sd * 0.2)
    r = 44 * s * (1.0 - 0.08 * dance * st)
    mouth = 0.25 + (0.1 + 0.45 * dance) * (0.5 + 0.5 * math.sin(ph + p["seed"]))
    a = -math.pi / 2 + 0.55 + lean * 0.9
    pts = [top]
    for i in range(15):
        ang = a + mouth + (2 * math.pi - 2 * mouth) * i / 14.0
        pts.append((top[0] + math.cos(ang) * r, top[1] + math.sin(ang) * r))
    pygame.draw.lines(screen, col, True, pts, w)
    for sgn in (-1, 1):                                       # a few teeth along both edges of the mouth
        ea = a + sgn * mouth
        for k in (0.45, 0.75):
            tx, ty = top[0] + math.cos(ea) * r * k, top[1] + math.sin(ea) * r * k
            na = ea - sgn * 0.5
            pygame.draw.lines(screen, col, False, [(tx, ty), (tx + math.cos(na) * r * 0.2, ty + math.sin(na) * r * 0.2)], max(1, w - 1))
    for k in range(3):                                        # spots on the back of the head
        sa = a + math.pi + (k - 1) * 0.7
        pygame.draw.circle(screen, col, (int(top[0] + math.cos(sa) * r * 0.55), int(top[1] + math.sin(sa) * r * 0.55)),
                           max(2, int(r * 0.16)), 1)

def draw_leafy(screen, col, w, bx, by, sc, dz, lean, st, ph, p, dance):
    """a big tropical leaf cluster that flaps"""
    s = sc * dz * p["big"]
    n = p["n"]
    for i in range(n):
        u = (i - (n - 1) / 2.0) / max(1.0, (n - 1) / 2.0)
        ang = u * 1.0 + lean * 0.8 + 0.28 * dance * math.sin(ph + i * 0.9)
        length = (120 + 30 * (1 - abs(u))) * s * (1.0 + 0.2 * dance * st)
        leaf(screen, col, w, bx, by, ang, length, 26 * s * (1.0 - 0.1 * dance * st), u * 0.35)

def draw_fern(screen, col, w, bx, by, sc, dz, lean, st, ph, p, dance):
    s = sc * dz * p["big"]
    n = p["n"] + 2
    for i in range(n):
        u = (i - (n - 1) / 2.0) / ((n - 1) / 2.0)
        ang = u * 1.15 + lean * 0.7 + 0.22 * dance * math.sin(ph + i * 0.7)
        length = (95 - 20 * abs(u)) * s * (1.0 + 0.18 * dance * st)
        dx, dy = math.sin(ang), -math.cos(ang)
        tip = (bx + dx * length + u * length * 0.45, by + dy * length * 0.9 + length * 0.3 * abs(u))
        mid = bez((bx, by), (bx + dx * length * 0.7, by + dy * length * 0.9), tip, 9)
        line(screen, col, mid, w)
        for j in range(2, 9):
            mx, my = mid[j]
            tx, ty = mid[j][0] - mid[j - 1][0], mid[j][1] - mid[j - 1][1]
            tl = math.hypot(tx, ty) or 1.0
            nx, ny = -ty / tl, tx / tl
            ll = length * 0.22 * (1.0 - j / 10.0)
            pygame.draw.line(screen, col, (mx, my), (mx + nx * ll + tx / tl * ll * 0.5, my + ny * ll + ty / tl * ll * 0.5), 1)
            pygame.draw.line(screen, col, (mx, my), (mx - nx * ll + tx / tl * ll * 0.5, my - ny * ll + ty / tl * ll * 0.5), 1)

def draw_tree(screen, col, w, bx, by, sc, dz, lean, st, ph, p, dance):
    s = sc * dz * p["big"]
    h = 330 * s * (1.0 + 0.08 * dance * st)
    top = (bx + lean * h * 0.35, by - h)
    base_w = 14 * s
    c = bez((bx, by), (bx - lean * h * 0.1, by - h * 0.5), top, 10)
    line(screen, col, [(x - base_w * (1 - i / 10.0) - 2, y) for i, (x, y) in enumerate(c)], w)
    line(screen, col, [(x + base_w * (1 - i / 10.0) + 2, y) for i, (x, y) in enumerate(c)], w)
    pump = 1.0 + 0.12 * dance * st
    blobs = ((0, 0, 62), (-60, 18, 48), (60, 18, 48), (-30, -42, 46), (34, -40, 44))
    for k, (ox, oy, r) in enumerate(blobs):
        wob = math.sin(ph + k) * 4 * dance * s
        pygame.draw.circle(screen, col, (int(top[0] + ox * s * pump), int(top[1] + oy * s * pump + wob)), max(3, int(r * s * pump)), w)

# ---------------------------------------------------------------- draw
def draw(screen, eyesy):
    xres, yres = eyesy.xres, eyesy.yres
    if _S["plants"] is None or _S["size"] != (xres, yres):
        build(xres, yres)
    now = time.time()
    if _S["last"] is None:
        _S["last"] = now
    dt = min(max(now - _S["last"], 1e-3), 0.1)
    _S["last"] = now
    _S["t"] += dt
    t = _S["t"]
    knob_play(eyesy, dt)
    vel, env, mom = _play["vel"], _play["env"], _play["mom"]

    # ---- beat clock: a slow, steady sway (one bob every 4 beats). Kicks only nudge the tempo and add a soft swell;
    # nothing ever snaps, so the motion stays smooth and calm ----
    kick = False
    if getattr(eyesy, "trig", False):
        gap = t - _S["last_trig"]
        if 0.25 < gap < 1.5:
            _S["bpm"] += (60.0 / gap - _S["bpm"]) * 0.05
        _S["bpm"] = clamp(_S["bpm"], 90.0, 180.0)
        _S["last_trig"] = t
        kick = True
    _S["phase"] = (_S["phase"] + dt * _S["bpm"] / 60.0 / 4.0) % 1.0
    if kick or (t - _S["last_trig"] > 1.5 and _S["phase"] < dt * 0.6):
        _S["target"] = 1.0
        if len(_S["ripples"]) < 4:
            _S["ripples"].append({"d": random.uniform(0.25, 0.95), "lane": random.uniform(-0.6, 0.6), "age": 0.0})
    _S["target"] *= math.exp(-dt * 2.0)
    _S["beat"] += (_S["target"] - _S["beat"]) * min(1.0, dt * 2.5)   # eased swell, not a hit
    beat, phase = _S["beat"], _S["phase"]

    # ---- the knobs ----
    raw = (clamp(0.5 + 2.1 * eyesy.knob1 + mom[0] * 1.2, 0.35, 3.0),
           clamp(1.5 * eyesy.knob2 + 0.1 * env[1], 0.0, 1.6),
           mom[1] * 0.9,
           eyesy.knob3,
           mom[2] * 0.8,
           env[2] * 0.6)
    if _S["sm"] is None:
        _S["sm"] = list(raw)
    k = min(1.0, dt * 2.0)                                    # everything glides to where the knobs say
    for i in range(6):
        _S["sm"][i] += (raw[i] - _S["sm"][i]) * k
    size, dance, gust, k3, slosh, surge = _S["sm"]
    flow_speed = 0.15 + 2.6 * k3
    _S["flow"] += dt * flow_speed
    wobble = 0.35 + 0.5 * k3

    base = eyesy.color_picker(eyesy.knob4)
    bg = eyesy.color_picker_bg(eyesy.knob5)
    bg = mix(bg, (0, 0, 0), 0.55)
    bh, bs, bv = colorsys.rgb_to_hsv(base[0] / 255.0, base[1] / 255.0, base[2] / 255.0)
    spread = clamp(abs(mom[3]) * 8.0 + env[3] * 0.4, 0.0, 1.0)
    bs, bv = max(bs, 0.55), max(bv, 0.8)
    water_h = bh + 0.45 + mom[3] * 1.5

    screen.fill(bg)
    hy = yres * 0.36
    H = yres - hy + 12
    cx = xres * 0.5
    sw = yres / 480.0

    def fgcol(d):
        c = hsv(bh + spread * (d - 0.5) * 0.5, bs, bv)
        return mix(bg, c, 0.3 + 0.7 * d)

    def river(d):
        f = d ** 1.7
        y = hy + H * f
        sc = 0.1 + 1.0 * f
        ph_m = d * 5.6 + t * 0.12 + wobble * 0.5 * math.sin(t * 0.3)
        x = cx + sc * xres * 0.26 * (0.55 + 0.5 * wobble) * (math.sin(ph_m) + 0.35 * math.sin(ph_m * 2.3 + 1.0)) + sc * slosh * xres * 0.15
        w = sc * xres * 0.42 * (1.0 + 0.06 * beat * dance + 0.2 * surge)
        return x, y, sc, w

    # ---- moon + far canopy ridge ----
    mx, my = int(xres * 0.8), int(yres * 0.14)
    moon_c = mix(bg, hsv(bh + 0.1, 0.25, 1.0), 0.55 + 0.35 * env[4] + 0.2 * beat)
    pygame.draw.circle(screen, moon_c, (mx, my), int(26 * sw * (1.0 + 0.1 * beat + 0.3 * env[4])), 2)
    pygame.draw.circle(screen, moon_c, (mx + int(8 * sw), my - int(5 * sw)), int(18 * sw), 1)
    ridge = fgcol(0.05)
    step = 34 * sw
    pts = []
    x = -step
    k = 0
    while x < xres + step * 2:
        bob = math.sin(x * 0.012 - phase * 6.283) * 5 * dance * sw + beat * 3 * dance * sw
        for j in range(7):
            a = math.pi - math.pi * j / 6.0
            pts.append((x + step * 0.5 + math.cos(a) * step * 0.55, hy - 8 * sw - bob - math.sin(a) * step * (0.45 + 0.15 * ((k * 7) % 3))))
        x += step
        k += 1
    pygame.draw.lines(screen, ridge, False, pts, 1)

    # ---- the stream ----
    NS = 28
    lbank, rbank, cen = [], [], []
    for i in range(NS + 1):
        d = i / float(NS)
        x, y, sc, w = river(d)
        lbank.append((x - w / 2, y))
        rbank.append((x + w / 2, y))
        cen.append((x, y, sc, w))
    wc = hsv(water_h, 0.75, 1.0)
    pygame.draw.lines(screen, mix(bg, wc, 0.9), False, lbank, 3)
    pygame.draw.lines(screen, mix(bg, wc, 0.9), False, rbank, 3)
    lanes = 5
    for L in range(lanes):
        lane = (L + 0.5) / lanes * 1.7 - 0.85
        for j in range(5):
            u0 = (j / 5.0 + _S["flow"] * 0.12 + L * 0.173) % 1.0
            seg = []
            for q in range(5):
                d = clamp(u0 + q * 0.03)
                x, y, sc, w = river(d)
                seg.append((x + lane * w * 0.5 + math.sin(d * 30 - t * 1.2 + L) * 3 * sc * sw, y))
            if seg[0][1] < hy + 3:
                continue
            line(screen, mix(bg, wc, 0.25 + 0.75 * clamp(u0 * 1.1)), seg, 1 if u0 < 0.45 else 2)
    keep = []
    for rp in _S["ripples"]:                                  # every kick drops a ring on the water
        rp["age"] += dt * 0.9
        if rp["age"] < 2.2:
            keep.append(rp)
            x, y, sc, w = river(rp["d"])
            rr = (6 + 40 * rp["age"]) * sc * sw
            col = mix(bg, wc, (1.0 - rp["age"] / 2.2) * 0.8)
            r = pygame.Rect(0, 0, int(rr * 2), max(2, int(rr * 0.7)))
            r.center = (int(x + rp["lane"] * w * 0.5), int(y))
            pygame.draw.ellipse(screen, col, r, 1)
    _S["ripples"] = keep[-8:]
    for rd, side in ((0.35, 1), (0.55, -1), (0.8, 1)):        # a few stones in the water
        x, y, sc, w = river(rd)
        sx = x + side * w * 0.22
        r = pygame.Rect(0, 0, int(46 * sc * sw), int(22 * sc * sw))
        r.midbottom = (int(sx), int(y))
        pygame.draw.ellipse(screen, fgcol(rd), r, 1)

    # ---- plants, back to front ----
    for p in _S["plants"]:
        d = p["d"]
        x, y, sc, w = river(d)
        px = x + p["side"] * (w / 2 + (0.03 + p["off"]) * sc * xres * 0.4)
        # this plant's place in the bounce wave
        ph = 2 * math.pi * (phase + p["lag"])
        st = math.sin(ph)                                     # +1 = stretching up, -1 = squashed down
        lean = (0.2 * math.sin(t * 0.5 + p["seed"]) * (0.1 + dance) + gust * (0.5 + d * 0.5)) * (1.0 if p["side"] > 0 else 1.0)
        lean = clamp(lean, -0.7, 0.7)
        col = fgcol(min(d, 1.0))
        wd = 1 if sc < 0.35 else (2 if sc < 0.8 else 3)
        dz = size
        k = p["kind"]
        if k == "bulb":
            draw_bulb(screen, col, wd, px, y, sc, dz, lean, st, ph, p, dance)
        elif k == "leaf":
            draw_leafy(screen, col, wd, px, y, sc, dz, lean, st, ph, p, dance)
        elif k == "fern":
            draw_fern(screen, col, wd, px, y, sc, dz, lean, st, ph, p, dance)
        else:
            draw_tree(screen, col, wd, px, y, sc, dz, lean, st, ph, p, dance)

    # ---- hanging vines in front ----
    vc = fgcol(0.95)
    for v in _S["vines"]:
        vx = v["x"] * xres
        ln = v["len"] * yres * (0.6 + 0.6 * size)
        ln *= 0.7
        swing = 0.18 * math.sin(t * 0.6 + v["s"]) * (0.5 + dance) + gust * 0.4
        bounce = 1.0 + 0.07 * dance * math.sin(2 * math.pi * (phase + v["lag"]))
        pts = []
        for i in range(11):
            u = i / 10.0
            pts.append((vx + math.sin(swing) * ln * u * u * 1.2 + math.sin(u * 5 + t * 0.8 + v["s"]) * 4 * sw * u,
                        -4 + ln * bounce * u))
        line(screen, vc, pts, 2)
        for i in (3, 5, 7, 9):
            pygame.draw.circle(screen, vc, (int(pts[i][0] + (6 if i % 2 else -6) * sw), int(pts[i][1])), int(4 * sw) + 1, 1)

    # ---- fireflies ----
    ff = hsv(bh + 0.15, 0.4, 1.0)
    swarm = env[4]
    for f in _S["flies"]:
        f["s"] += dt * f["sp"] * 0.5 * (1.0 + 2.0 * swarm)
        fx = (f["x"] + 0.06 * math.sin(f["s"] * 1.3) + 0.04 * math.sin(t * 0.3 + f["s"])) * xres
        fy = (f["y"] + 0.05 * math.cos(f["s"])) * yres
        blink = 0.5 + 0.5 * math.sin(f["s"] * 1.5)
        c = mix(bg, ff, clamp(0.25 + 0.75 * blink + 0.4 * swarm))
        pygame.draw.circle(screen, c, (int(fx), int(fy)), 2 if blink < 0.8 else 3, 0 if blink > 0.5 else 1)
