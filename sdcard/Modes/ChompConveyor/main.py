# OGChompConveyor
# A conveyor belt carries a crowd of little lilac guys (round bodies, blue stripe, black button nose) toward a
# comically evil monster. Its jaw heaves open, fire roars inside its mouth, the guys get sucked in, and CHOMP.
# The guys have feelings: they wave happily far away and panic as they near the teeth.
# Tap the `0` key on the desktop (or hit a kick on the device) to make the monster chomp on the beat.
#
# Knobs (the usual convention):
#   knob1 = size           (how big the little guys are; flick it and they all jump in fright)
#   knob2 = conveyor + chomp speed  (belt speed AND how fast the jaw works; turn it fast and it revs up, a frenzy)
#   knob3 = how many       (crowd density on the belt AND how many guys get swallowed per chomp, 1 to 6;
#                           flick it and extra guys rain down onto the belt)
#   knob4 = foreground color (the monster's hide; flick it and the fire flares and the colors swing round)
#   knob5 = background color (flick it and the whole factory shakes)
import math
import random
import time
import pygame

W, H = 1280, 720                  # everything is drawn on this base canvas, then scaled to the screen if needed
BY = 600.0                        # belt top = where the guys' feet are
GATE = 690.0                      # the belt ends here, right under the monster's snout
HX, HY = 1130.0, 400.0            # jaw hinge
TIPX, TIPY = 688.0, 354.0         # closed jaw tip
LEN = math.hypot(TIPX - HX, TIPY - HY)
PHI0 = math.atan2(TIPY - HY, TIPX - HX)      # direction from hinge to tip when closed
THETA = math.radians(38.0)                   # how far the jaw drops when wide open
THROAT = (960.0, 450.0)
FLY = 0.28

BODY = (206, 196, 222)
BODY_HI = (232, 226, 242)
STRIPE = (138, 142, 232)
INK = (26, 18, 34)

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))
def ease(t): return t * t * (3 - 2 * t)
def lerp(a, b, t): return a + (b - a) * t
def mulc(c, k): return (int(clamp(c[0] * k, 0, 255)), int(clamp(c[1] * k, 0, 255)), int(clamp(c[2] * k, 0, 255)))
def mixc(a, b, t): return (int(lerp(a[0], b[0], t)), int(lerp(a[1], b[1], t)), int(lerp(a[2], b[2], t)))

def hsv(h, s, v):
    """hue/saturation/value (0..1) to an (r, g, b) tuple"""
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

# ---------------------------------------------------------------- jaw geometry
def jaw_pt(u, v, phi):
    """a point u along the jaw from the hinge toward the tip, v below that line (jaw angle phi)"""
    return (HX + u * math.cos(phi) + v * math.sin(phi), HY + u * math.sin(phi) - v * math.cos(phi))

def jaw_open(p):
    """jaw openness 0..1 over one chomp cycle p in 0..1: heave open, hold, SNAP shut, chew"""
    if p < 0.50:
        x = p / 0.50
        return 1.0 - (1.0 - x) ** 3
    if p < 0.68:
        return 1.0
    if p < 0.76:
        x = (p - 0.68) / 0.08
        return 1.0 - x * x
    q = (p - 0.76) / 0.24
    return 0.09 * max(0.0, math.sin(q * math.pi * 3.0)) * (1.0 - q)

# ---------------------------------------------------------------- state
_S = {}

def reset():
    _S.clear()
    _S.update({"last": None, "t": 0.0, "p": 0.3, "launched": 0, "snapped": False, "lt": 0.0, "guys": [],
               "parts": [], "shake": 0.0, "flare": 0.0, "kick": 0.0, "boff": 0.0, "pop": None, "dropcd": 0.0,
               "smokecd": 0.0, "eaten": 0, "cv": None, "scr": None, "glow": None, "glow_size": None,
               "fonts": {}, "texts": {}, "sprites": {}, "gulp": 0.0, "bob": 0.0})
    g = 95.0
    x = GATE - 0.12 * g
    while x > 0:
        _S["guys"].append(new_guy(x))
        x -= g * 1.4

def new_guy(x, fall=False):
    q = {"x": x, "fy": BY, "state": "belt", "ph": random.random() * 6.28, "sj": random.uniform(0.9, 1.1),
         "vy": 0.0, "sq": 0.0, "t": 0.0, "dur": FLY, "sx": 0.0, "sy": 0.0, "spin": random.choice((-1, 1)) * random.uniform(1.2, 2.6),
         "tx": 0.0, "ty": 0.0}
    if fall:
        q["state"] = "fall"
        q["fy"] = -60.0
    return q

def setup(screen, eyesy):
    reset()

# ---------------------------------------------------------------- the little guys
def draw_guy(surf, cx, fy, g, fear, t, ph, walk=1.0, sq=0.0, scream=False):
    """one little guy standing with his feet at fy; g = his height in pixels"""
    sqy = 1.0 - sq * 0.2
    sqx = 1.0 + sq * 0.14
    bw = 0.72 * g * sqx
    bh = 0.78 * g * sqy
    bottom = fy - 0.16 * g
    top = bottom - bh
    r = int(0.27 * g)
    # shadow
    pygame.draw.ellipse(surf, (22, 22, 30), (cx - 0.42 * g, fy - 0.03 * g, 0.84 * g, 0.12 * g))
    # legs
    for s in (-1, 1):
        sw = math.sin(t * 9.0 + ph + (0 if s < 0 else math.pi)) * 0.035 * g * walk
        pygame.draw.ellipse(surf, BODY, (cx + s * 0.15 * g - 0.095 * g, fy - 0.2 * g + sw, 0.19 * g, 0.22 * g))
    # arms (behind the body)
    shoulder_y = top + 0.40 * bh
    arm_w = max(2, int(0.13 * g))
    L = 0.3 * g
    for s in (-1, 1):
        if scream or fear > 0.55:
            a = math.radians(150 + 28 * math.sin(t * 17.0 + ph * (2 if s > 0 else 3)))
        elif s > 0:
            a = math.radians(125 + 28 * math.sin(t * 6.0 + ph))             # the happy wave
        else:
            a = math.radians(32 + 8 * math.sin(t * 2.0 + ph))
        a += fear * math.radians(12) * math.sin(t * 20.0 + ph) * 0.4
        p1 = (cx + s * bw * 0.42, shoulder_y)
        p2 = (p1[0] + s * math.sin(a) * L, p1[1] + math.cos(a) * L)
        pygame.draw.line(surf, BODY, p1, p2, arm_w)
        pygame.draw.circle(surf, BODY, (int(p2[0]), int(p2[1])), arm_w // 2)
    # body
    pygame.draw.rect(surf, BODY, (cx - bw / 2, top, bw, bh), border_radius=r)
    pygame.draw.ellipse(surf, BODY_HI, (cx - bw * 0.36, top + 0.04 * bh, bw * 0.3, bh * 0.12))
    pygame.draw.rect(surf, STRIPE, (cx - bw / 2, top + 0.43 * bh, bw, 0.2 * bh))
    # face
    ey = top + 0.19 * g
    ex = 0.15 * g
    if scream or fear > 0.4:
        for s in (-1, 1):
            pygame.draw.circle(surf, (250, 250, 255), (int(cx + s * ex), int(ey)), max(2, int(0.06 * g)))
            pygame.draw.circle(surf, INK, (int(cx + s * ex), int(ey)), max(1, int(0.032 * g)))
    else:
        for s in (-1, 1):
            pygame.draw.circle(surf, INK, (int(cx + s * ex), int(ey)), max(1, int(0.03 * g)))
    pygame.draw.ellipse(surf, INK, (cx - 0.075 * g, top + 0.215 * g, 0.15 * g, 0.1 * g))
    my = top + 0.34 * g
    if scream or fear > 0.4:
        mh = (0.08 + 0.07 * (1.0 if scream else fear)) * g
        pygame.draw.ellipse(surf, INK, (cx - 0.05 * g, my - 0.03 * g, 0.1 * g, mh))
    else:
        pygame.draw.arc(surf, INK, (cx - 0.07 * g, my - 0.07 * g, 0.14 * g, 0.1 * g), math.pi * 1.1, math.pi * 1.9, max(1, int(0.015 * g)))
    if fear > 0.5 and not scream:                                     # sweat
        k = (t * 2.0 + ph) % 1.0
        pygame.draw.circle(surf, (150, 210, 255), (int(cx + bw * 0.5 + 0.06 * g), int(top + 0.1 * g + k * 0.15 * g)), max(2, int(0.035 * g)))

def scream_sprite(g):
    key = int(g)
    sp = _S["sprites"].get(key)
    if sp is None:
        n = int(g * 1.5)
        sp = pygame.Surface((n, n), pygame.SRCALPHA)
        draw_guy(sp, n / 2.0, n / 2.0 + g * 0.48, g, 1.0, 0.0, 0.0, 0.0, 0.0, True)
        if len(_S["sprites"]) > 12:
            _S["sprites"].clear()
        _S["sprites"][key] = sp
    return sp

# ---------------------------------------------------------------- particles
def emit(kind, x, y, vx, vy, life, size, col=None, grav=0.0):
    if len(_S["parts"]) < 260:
        _S["parts"].append({"k": kind, "x": x, "y": y, "vx": vx, "vy": vy, "life": life, "max": life, "size": size,
                            "col": col, "grav": grav, "a": random.random() * 6.28, "w": random.uniform(-9, 9)})

def update_parts(dt):
    out = []
    for q in _S["parts"]:
        q["life"] -= dt
        if q["life"] <= 0:
            continue
        q["x"] += q["vx"] * dt
        q["y"] += q["vy"] * dt
        q["vy"] += q["grav"] * dt
        q["a"] += q["w"] * dt
        out.append(q)
    _S["parts"] = out

def draw_parts(cv, bg):
    for q in _S["parts"]:
        f = q["life"] / q["max"]
        x, y = int(q["x"]), int(q["y"])
        if q["k"] == "ember":
            col = mixc((255, 60, 10), (255, 220, 90), f)
            col = mixc(bg, col, clamp(f * 1.6))
            pygame.draw.circle(cv, col, (x, y), max(1, int(q["size"] * (0.4 + 0.6 * f))))
        elif q["k"] == "fire":
            col = mixc((200, 30, 10), (255, 200, 60), f)
            col = mixc(bg, col, clamp(f * 1.8))
            pygame.draw.circle(cv, col, (x, y), max(1, int(q["size"] * (0.5 + 0.7 * f))))
        elif q["k"] == "smoke":
            col = mixc(bg, (96, 94, 108), clamp(f * 1.2) * 0.8)
            pygame.draw.circle(cv, col, (x, y), max(1, int(q["size"] * (1.7 - f))))
        else:                                                            # bits of lilac guy
            s = max(2, int(q["size"] * (0.4 + 0.6 * f)))
            c, sn = math.cos(q["a"]), math.sin(q["a"])
            pts = [(x + (dx * c - dy * sn) * s, y + (dx * sn + dy * c) * s) for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            pygame.draw.polygon(cv, q["col"], pts)

# ---------------------------------------------------------------- monster parts
def flame(cv, bx, by, w, h, lean, col, t, seed):
    n = 9
    left, right = [], []
    for i in range(n + 1):
        s = i / n
        wob = 0.1 * h * math.sin(t * 13.0 + s * 5.0 + seed) * s
        half = w * (1.0 - s) ** 0.8
        cxs = bx + lean * s * s * h + wob
        y = by - h * s
        left.append((cxs - half, y))
        right.append((cxs + half, y))
    pygame.draw.polygon(cv, col, left + right[::-1])

def draw_fire(cv, phi, t, power):
    gaps = 0
    for i, u in enumerate((120, 175, 230, 285, 340, 395, 450)):
        bx, by = jaw_pt(u, -4, phi)
        gap = u * math.sin(THETA * _S["open"])
        n1 = 0.75 + 0.25 * math.sin(t * 9.0 + i * 1.7) + 0.2 * math.sin(t * 17.0 + i * 3.1)
        h = min((50 + 200 * power) * max(0.25, n1), gap * 1.5 + 14)
        w = (16 + 20 * power) * (0.8 + 0.2 * math.sin(t * 7 + i))
        lean = 0.12 * math.sin(t * 3.0 + i) - 0.12
        flame(cv, bx, by, w, h, lean, (225, 40, 12), t, i)
        flame(cv, bx, by, w * 0.72, h * 0.8, lean, (255, 130, 20), t, i + 7)
        flame(cv, bx, by, w * 0.46, h * 0.58, lean, (255, 225, 80), t, i + 3)
        flame(cv, bx, by, w * 0.22, h * 0.34, lean, (255, 250, 200), t, i + 5)

def make_glow(size):
    """soft orange light spilling out of the mouth, in 8 brightness steps, for additive blitting"""
    levels = []
    for lv in range(1, 9):
        base = pygame.Surface((64, 64))
        for rr in range(32, 0, -1):
            k = (1.0 - rr / 32.0) ** 1.6 * lv / 8.0
            pygame.draw.circle(base, (int(255 * k * 0.55), int(120 * k * 0.55), int(25 * k * 0.55)), (32, 32), rr)
        levels.append(pygame.transform.smoothscale(base, (size, size)))
    return levels

def draw_monster(cv, t, eyesy, hue, theta_open, power, ox, oy, target, bg):
    phi = PHI0 - THETA * theta_open
    body = hsv(hue, 0.62, 0.72)
    dark = mulc(body, 0.5)
    light = mixc(body, (255, 255, 255), 0.3)

    def P(x, y): return (x + ox, y + oy)
    def PL(pts): return [(x + ox, y + oy) for x, y in pts]
    def J(u, v, ph): return P(*jaw_pt(u, v, ph))

    # shadow and neck / body behind the jaws
    pygame.draw.ellipse(cv, mulc(bg, 0.45), (780, BY + 70, 560, 50))
    pygame.draw.polygon(cv, dark, PL([(1090, 380), (1290, 400), (1290, 730), (930, 730), (960, 560), (1010, 470)]))
    pygame.draw.polygon(cv, mulc(body, 0.75), PL([(1180, 470), (1290, 460), (1290, 730), (1060, 730)]))
    # belly spikes / collar
    for i in range(5):
        bx = 1000 + i * 55
        pygame.draw.polygon(cv, (230, 225, 205), PL([(bx, 640 - i * 6), (bx + 24, 640 - i * 6), (bx + 12, 592 - i * 6)]))
    # horns and back spikes (behind the head)
    pygame.draw.polygon(cv, (232, 226, 200), PL([(860, 190), (820, 40), (905, 150)]))
    pygame.draw.polygon(cv, (232, 226, 200), PL([(975, 150), (1010, 10), (1060, 150)]))
    pygame.draw.polygon(cv, (180, 170, 150), PL([(840, 100), (820, 40), (870, 130)]))
    for i, (sx_, sy_) in enumerate(((1100, 150), (1150, 175), (1200, 205), (1245, 245))):
        pygame.draw.polygon(cv, light, PL([(sx_ - 26, sy_ + 8), (sx_ + 6, sy_ - 58 + i * 6), (sx_ + 30, sy_ + 34)]))

    # mouth interior and fire
    top_tip = jaw_pt(LEN, 0, PHI0)
    low_tip = jaw_pt(LEN, 0, phi)
    pygame.draw.polygon(cv, (58, 6, 16), PL([(HX + 20, HY - 40), top_tip, low_tip, (HX + 20, HY + 40)]))
    pygame.draw.ellipse(cv, (22, 0, 8), (HX - 330 + ox, HY - 90 + oy, 300, 150 + 100 * theta_open))
    draw_fire(cv, phi, t, power)

    # little guys flying down its throat (behind the lower jaw)
    for q in _S["guys"]:
        if q["state"] == "fly":
            s = clamp(q["t"])
            x = lerp(q["sx"], q["tx"], ease(s))
            y = lerp(q["sy"], q["ty"], ease(s)) - 130.0 * 4 * s * (1 - s)
            gg = _S["g"] * (1.0 - 0.6 * s) * q["sj"]
            sp = scream_sprite(_S["g"])
            sp = pygame.transform.rotozoom(sp, math.degrees(q["spin"] * s), gg / _S["g"])
            cv.blit(sp, sp.get_rect(center=P(x, y)))

    # lower jaw
    jaw = [(-40, -10), (LEN, -10), (LEN + 24, 26), (LEN + 6, 100), (LEN - 90, 158), (140, 190), (-40, 150)]
    pygame.draw.polygon(cv, mulc(body, 0.62), [J(u, v, phi) for u, v in jaw])
    pygame.draw.polygon(cv, dark, [J(u, v, phi) for u, v in jaw], 4)
    # tongue
    tong = [(110, -4)] + [(110 + k * 30, -5 - 12 * math.sin(k * 0.9 + t * 3)) for k in range(1, 11)] + [(LEN - 110, 4), (LEN - 150, 26), (110, 26)]
    pygame.draw.polygon(cv, (214, 58, 92), [J(u, v, phi) for u, v in tong])
    # lower teeth (a pair of big tusks at the front)
    lteeth = [(LEN - 22, 66, 15), (LEN - 82, 30, 12), (LEN - 134, 38, 12), (LEN - 190, 28, 11), (LEN - 246, 34, 12),
              (LEN - 304, 26, 11), (LEN - 360, 30, 11)]
    for u, ln, hw in lteeth:
        pts = [J(u - hw, -4, phi), J(u + hw, -4, phi), J(u + 3, -4 - ln, phi)]
        pygame.draw.polygon(cv, (244, 240, 222), pts)
        pygame.draw.polygon(cv, (120, 110, 90), pts, 2)

    # head
    head = [(TIPX, TIPY + 2), (668, 322), (686, 286), (738, 262), (786, 214), (856, 168), (960, 140), (1080, 150),
            (1180, 190), (1290, 262), (1290, 440), (1180, 432), (HX, HY)]
    pygame.draw.polygon(cv, body, PL(head))
    pygame.draw.polygon(cv, dark, PL(head), 4)
    # snout shading and scars
    pygame.draw.polygon(cv, light, PL([(700, 292), (760, 270), (800, 226), (770, 300), (720, 320)]))
    for a_, b_ in (((1010, 300), (1062, 372)), ((1030, 290), (1082, 360)), ((1050, 282), (1100, 350))):
        pygame.draw.line(cv, dark, P(*a_), P(*b_), 5)
    # nostril
    pygame.draw.ellipse(cv, (30, 6, 14), (P(690, 304)[0], P(690, 304)[1], 26, 16))
    # evil eye + brow
    ex, ey = 858.0, 268.0
    pygame.draw.ellipse(cv, (255, 232, 70), (ex - 56 + ox, ey - 34 + oy, 112, 68))
    pygame.draw.ellipse(cv, (200, 60, 20), (ex - 56 + ox, ey - 34 + oy, 112, 68), 4)
    dx, dy = target[0] - ex, target[1] - ey
    d = math.hypot(dx, dy) + 1e-6
    px, py = ex + dx / d * 24, ey + dy / d * 10
    pygame.draw.ellipse(cv, (30, 0, 0), (px - 8 + ox, py - 28 + oy, 16, 56))
    pygame.draw.circle(cv, (255, 255, 255), (int(px - 2 + ox), int(py - 12 + oy)), 3)
    brow = [(752, 262), (780, 234), (940, 196), (958, 232), (940, 246), (800, 296)]
    pygame.draw.polygon(cv, (40, 8, 22), PL(brow))
    pygame.draw.polygon(cv, light, PL([(790, 236), (938, 202), (940, 212), (800, 248)]))
    # upper teeth hanging from the lip
    uteeth = [(LEN - 12, 74, 17), (LEN - 62, 36, 14), (LEN - 112, 44, 13), (LEN - 168, 32, 12), (LEN - 222, 40, 13),
              (LEN - 280, 30, 12), (LEN - 336, 36, 12), (LEN - 392, 26, 11)]
    for u, ln, hw in uteeth:
        pts = [J(u - hw, 4, PHI0), J(u + hw, 4, PHI0), J(u - 2, ln, PHI0)]
        pygame.draw.polygon(cv, (244, 240, 222), pts)
        pygame.draw.polygon(cv, (120, 110, 90), pts, 2)
    pygame.draw.line(cv, dark, P(TIPX, TIPY), P(HX, HY), 5)
    return phi

# ---------------------------------------------------------------- scene
def draw_belt(cv, boff, bg):
    floor = mulc(bg, 0.55)
    pygame.draw.rect(cv, floor, (0, BY + 60, W, H - BY - 60))
    pygame.draw.line(cv, mulc(bg, 0.9), (0, BY + 60), (W, BY + 60), 3)
    for x in range(0, W, 160):
        pygame.draw.line(cv, mulc(bg, 0.8), (x, 0), (x, BY + 60), 2)
    for lx in (90, 340, 590):                                           # legs
        pygame.draw.rect(cv, (58, 64, 84), (lx - 14, BY + 46, 28, 140))
        pygame.draw.rect(cv, (82, 90, 112), (lx - 14, BY + 46, 8, 140))
        pygame.draw.rect(cv, (58, 64, 84), (lx - 46, BY + 180, 92, 12))
    end = GATE + 62
    pygame.draw.rect(cv, (38, 38, 48), (-40, BY, end + 40, 46), border_radius=22)
    off = boff % 38.0
    x = -38.0 + off
    while x < end - 20:
        pygame.draw.line(cv, (66, 66, 82), (x, BY + 6), (x + 14, BY + 40), 3)
        x += 38.0
    pygame.draw.line(cv, (120, 120, 142), (-40, BY + 1), (end - 20, BY + 1), 3)
    # hazard stripe along the frame
    hz = boff % 48.0
    x = -48.0 + hz
    while x < end - 20:
        pygame.draw.polygon(cv, (240, 200, 30), [(x, BY + 46), (x + 24, BY + 46), (x + 12, BY + 58), (x - 12, BY + 58)])
        x += 48.0
    pygame.draw.rect(cv, (30, 30, 36), (-40, BY + 56, end + 40, 4))

def get_font(size):
    f = _S["fonts"].get(size)
    if f is None:
        try:
            pygame.font.init()
            f = pygame.font.Font(None, size)
        except Exception:
            f = False
        _S["fonts"][size] = f
    return f

def text_sprite(word):
    sp = _S["texts"].get(word)
    if sp is None:
        f = get_font(110)
        if not f:
            return None
        face = f.render(word, True, (255, 240, 90))
        edge = f.render(word, True, (150, 20, 20))
        sp = pygame.Surface((face.get_width() + 12, face.get_height() + 12), pygame.SRCALPHA)
        for ox_, oy_ in ((0, 6), (12, 6), (6, 0), (6, 12), (1, 1), (11, 11), (1, 11), (11, 1)):
            sp.blit(edge, (ox_, oy_))
        sp.blit(face, (6, 6))
        _S["texts"][word] = sp
    return sp

def on_chomp(eaten, g):
    S = _S
    S["shake"] = 1.0
    S["flare"] = min(1.0, S["flare"] + 0.35)
    S["gulp"] = 1.0
    word = "CLACK!" if eaten == 0 else ("CHOMP!" if eaten < 3 else "CRUNCH!")
    S["pop"] = {"w": word, "t": 0.0, "rot": random.uniform(-14, 14), "x": random.uniform(620, 760), "y": random.uniform(190, 250)}
    mx, my = jaw_pt(LEN - 30, -10, PHI0)
    for _ in range(10 + 6 * eaten):
        emit("ember", mx, my, random.uniform(-520, -90), random.uniform(-380, 60), random.uniform(0.4, 0.9), random.uniform(3, 7), None, 500)
    for _ in range(6 * eaten):
        emit("bit", mx, my + 20, random.uniform(-380, -60), random.uniform(-420, -60), random.uniform(0.6, 1.1), g * 0.07,
             random.choice((BODY, BODY, STRIPE)), 1100)

def draw(screen, eyesy):
    S = _S
    if not S:
        reset()
    xres, yres = eyesy.xres, eyesy.yres
    now = time.time()
    if S["last"] is None:
        S["last"] = now
    dt = max(0.0001, min(now - S["last"], 0.1))
    S["last"] = now
    S["t"] += dt
    t = S["t"]
    vel, env, mom = knob_play(eyesy, dt)

    k1, k2, k3 = eyesy.knob1, eyesy.knob2, eyesy.knob3
    g = 50.0 + k1 * 90.0
    S["g"] = g
    speed = 1.0 + env[1] * 0.9
    belt_v = (12.0 + k2 * 290.0) * speed
    rate = (0.22 + k2 * 1.55) * speed
    nmax = 1 + int(k3 * 5.99)
    gap = g * (1.95 - k3 * 1.0)
    minsp = g * 0.82

    try:
        level = clamp(max(abs(v) for v in eyesy.audio_in[:100]) / 30000.0)
    except Exception:
        level = 0.0
    S["kick"] = max(S["kick"] * math.exp(-dt * 6.0), level)
    if getattr(eyesy, "trig", False):
        S["kick"] = 1.0
        if S["p"] > 0.85:
            S["p"] = 0.0
            S["launched"] = 0
            S["snapped"] = False
    for key, r in (("shake", 5.0), ("flare", 1.6), ("gulp", 3.0)):
        S[key] *= math.exp(-dt * r)
    S["flare"] = max(S["flare"], env[3] * 0.9)

    # ---- chomp cycle ----
    S["p"] += rate * dt
    if S["p"] >= 1.0:
        S["p"] -= 1.0
        S["launched"] = 0
        S["snapped"] = False
    p = S["p"]
    op = jaw_open(p)
    S["open"] = op
    S["boff"] += belt_v * dt

    guys = S["guys"]
    belt = [q for q in guys if q["state"] == "belt"]

    # launch guys into the mouth while it is open
    if 0.1 < p < 0.66 and op > 0.45 and S["launched"] < nmax:
        S["lt"] -= dt
        if S["lt"] <= 0.0:
            cands = [q for q in belt if q["x"] > GATE - g * 3.0]
            if cands:
                q = max(cands, key=lambda c: c["x"])
                q["state"] = "fly"
                q["t"] = 0.0
                q["sx"], q["sy"] = q["x"], q["fy"] - 0.5 * g
                q["tx"], q["ty"] = THROAT[0] + random.uniform(-50, 70), THROAT[1] + random.uniform(-40, 40)
                dist = math.hypot(q["tx"] - q["sx"], q["ty"] - q["sy"])
                q["dur"] = 0.2 + dist * 0.0003
                S["launched"] += 1
                S["lt"] = 0.09
            else:
                S["lt"] = 0.05

    # the snap
    if not S["snapped"] and p >= 0.72:
        S["snapped"] = True
        eaten = 0
        for q in guys:
            if q["state"] == "fly":
                q["state"] = "gone"
                eaten += 1
        S["eaten"] += eaten
        on_chomp(eaten, g)
        S["flare"] = min(1.0, S["flare"] + 0.25 * eaten)

    # flying guys land in the throat
    for q in guys:
        if q["state"] == "fly":
            q["t"] += dt / q["dur"]
            if q["t"] >= 1.0:
                q["state"] = "gone"
                S["eaten"] += 1
                S["flare"] = min(1.0, S["flare"] + 0.2)
                for _ in range(5):
                    emit("ember", THROAT[0], THROAT[1], random.uniform(-250, 100), random.uniform(-400, -100), 0.7, random.uniform(3, 6), None, 400)

    # falling guys (raining down when knob3 is flicked)
    for q in guys:
        if q["state"] == "fall":
            q["vy"] += 2400.0 * dt
            q["fy"] += q["vy"] * dt
            if q["fy"] >= BY:
                q["fy"] = BY
                q["vy"] = 0.0
                q["sq"] = 1.0
                q["state"] = "belt"
        q["sq"] *= math.exp(-dt * 12.0)

    S["dropcd"] -= dt
    if env[2] > 0.45 and S["dropcd"] <= 0.0 and len(guys) < 45:
        S["dropcd"] = 0.11
        guys.append(new_guy(random.uniform(80, GATE - 3 * g), True))

    # belt movement: guys queue up behind the monster
    belt = sorted([q for q in guys if q["state"] == "belt"], key=lambda q: -q["x"])
    lim = GATE - 0.12 * g
    for q in belt:
        nx = q["x"] + belt_v * dt
        if nx > lim:
            nx = max(lim, q["x"] - 600.0 * dt)
        q["x"] = nx
        lim = nx - minsp
    if len(guys) < 45 and (not belt or belt[-1]["x"] > -60.0 + gap):
        guys.append(new_guy(-60.0))
    S["guys"] = guys = [q for q in guys if q["state"] != "gone"]
    belt = sorted([q for q in guys if q["state"] in ("belt", "fall")], key=lambda q: q["x"])

    # ---- colors ----
    fg = eyesy.color_picker(eyesy.knob4)
    mx_, mn_ = max(fg), min(fg)
    if mx_ == mn_:
        hue = 0.0
    elif mx_ == fg[0]:
        hue = ((fg[1] - fg[2]) / (mx_ - mn_) / 6.0) % 1.0
    elif mx_ == fg[1]:
        hue = ((fg[2] - fg[0]) / (mx_ - mn_) / 6.0 + 1.0 / 3.0) % 1.0
    else:
        hue = ((fg[0] - fg[1]) / (mx_ - mn_) / 6.0 + 2.0 / 3.0) % 1.0
    hue += mom[3] * 1.5
    bg = eyesy.color_picker_bg(eyesy.knob5)
    bg = mixc(bg, (0, 0, 0), 0.35)

    power = clamp(0.5 + level * 0.3 + S["kick"] * 0.1 + S["flare"] * 0.5 + 0.08 * math.sin(t * 5.0))

    # ---- canvas ----
    native = (xres, yres) == (W, H)
    if native:
        cv = screen
    else:
        if S["cv"] is None:
            S["cv"] = pygame.Surface((W, H))
        cv = S["cv"]
    if eyesy.auto_clear:                                       # screen-clear off: the old picture stays and new things pile on top
        cv.fill(bg)
        draw_belt(cv, S["boff"], bg)

    # the guys on the belt
    bounce = max(S["kick"] * 7.0, env[0] * 38.0)
    for q in belt:
        fear = clamp(1.0 - (GATE - q["x"]) / 700.0) ** 1.2
        fear = max(fear, env[0] * 0.8)
        jit = fear * 2.0 * math.sin(t * 40.0 + q["ph"])
        hop = abs(math.sin(t * 9.0 + q["ph"])) * bounce if q["state"] == "belt" else 0.0
        draw_guy(cv, q["x"] + jit, q["fy"] - hop, g * q["sj"], fear, t, q["ph"], 1.0 if belt_v > 60 else 0.3, q["sq"])

    # the monster
    sh = S["shake"]
    ox = random.uniform(-1, 1) * (14 * sh + 6 * env[4]) + 4 * S["gulp"]
    oy = random.uniform(-1, 1) * (10 * sh + 6 * env[4]) + (3.0 * math.sin(t * 14.0) if op < 0.12 else 0.0)
    target = (GATE, BY - 60)
    front = [q for q in belt if q["state"] == "belt"]
    if front:
        f = max(front, key=lambda c: c["x"])
        target = (f["x"], f["fy"] - 0.5 * g)
    draw_monster(cv, t, eyesy, hue, op, power, ox, oy, target, bg)

    # smoke from the nostril, fire breath on a flare
    S["smokecd"] -= dt
    if S["smokecd"] <= 0.0:
        S["smokecd"] = 0.12
        emit("smoke", 700 + ox, 305 + oy, random.uniform(-60, -20), random.uniform(-90, -50), 1.4, 8)
    if S["flare"] > 0.45:
        mx, my = jaw_pt(LEN - 50, -30, PHI0 - THETA * op)
        for _ in range(2):
            emit("fire", mx, my, random.uniform(-520, -250), random.uniform(-150, 40), random.uniform(0.3, 0.6), random.uniform(8, 16), None, -80)
    update_parts(dt)
    draw_parts(cv, bg)

    # light spilling from the mouth
    if S["glow"] is None or S["glow_size"] != 1:
        S["glow"] = make_glow(560)
        S["glow_size"] = 1
    lv = int(clamp(power * (0.4 + 0.6 * op) + 0.1, 0, 0.999) * 8)
    gx, gy = jaw_pt(300, -60, PHI0 - THETA * op * 0.5)
    cv.blit(S["glow"][lv], (gx - 280 + ox, gy - 280 + oy), special_flags=pygame.BLEND_RGB_ADD)

    # comic word
    pop = S["pop"]
    if pop:
        pop["t"] += dt
        if pop["t"] > 0.7:
            S["pop"] = None
        else:
            sp = text_sprite(pop["w"])
            if sp:
                k = pop["t"] / 0.7
                s = (1.4 - 0.4 * math.exp(-k * 8.0)) * (1.0 - clamp((k - 0.7) / 0.3) * 0.5) * 0.9
                sp = pygame.transform.rotozoom(sp, pop["rot"], max(0.1, s))
                cv.blit(sp, sp.get_rect(center=(pop["x"], pop["y"] - 40 * k)))

    if not native:
        pygame.transform.smoothscale(cv, (xres, yres), screen)
