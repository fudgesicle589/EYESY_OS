# JellyfishJam
# The Jellyfish Jam episode (season 1): SpongeBob's pet jellyfish discovers the stereo and a laser light show, and
# invites every jellyfish in the sea. The party escalates from one jelly dancing with SpongeBob to a packed
# pineapple. Squidward glares out his window next door; Gary clicks his eyes to keep the beat.
#
# Knobs (the usual convention):
#   knob1 = size           (how big the jellyfish are; flick it and the whole crowd jumps)
#   knob2 = tempo / motion (BPM + laser sweep + dance energy; flick it and the jellies zap each other: electric panic)
#   knob3 = crowd size     (one lonely pet jelly at the far left -> the whole sea; past 3/4 the jellies toss
#                           SpongeBob around the room. Flick it and a wave of fresh jellies pours in the door)
#   knob4 = foreground color (jelly glow + laser colors; flick it and the colors swing around the wheel)
#   knob5 = background color (the room's walls; flick it and the strobe goes off, blackout then flash)
# A kick (or the `0` key on the desktop) fires the strobe, re-syncs everyone to the beat and pops bubbles.
import math
import random
import time
import pygame

W, H = 1280, 720                  # everything is drawn on this base canvas, then scaled to the screen if needed
FLOOR = 585
STX, STY = 640, 478               # stereo top-center (where the lasers come from)
MAXJ = 20

INK = (40, 30, 70)
WHITE = (255, 255, 255)

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))
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

# ---------------------------------------------------------------- state
_S = {}

def frac(v): return v - math.floor(v)

def new_jelly(i, temp=False):
    """jelly 0 is the pet and always stands next to SpongeBob; the rest are placed by a golden-ratio spread"""
    if i == 0:
        bx, by = 560.0, 360.0
    else:
        bx = 90 + frac(i * 0.618 + 0.13) * 1100
        by = 150 + frac(i * 0.382 + 0.31) * 330
    j = {"id": i, "bx": bx, "by": by, "x": bx, "y": by, "ph": random.uniform(0, 6.28),
         "sz": random.uniform(0.8, 1.2) * (1.25 if i == 0 else 1.0), "off": random.choice((0.0, 0.5, 0.25)),
         "hue": random.uniform(-0.04, 0.04), "pulse": 0.0, "temp": temp, "life": 9.0, "state": "in"}
    if temp:
        j["x"], j["y"] = 60.0, random.uniform(380, 520)
        j["bx"], j["by"] = random.uniform(150, 1130), random.uniform(160, 480)
    return j

def reset():
    _S.clear()
    _S.update({"last": None, "t": 0.0, "beat": 0.0, "jel": [new_jelly(i) for i in range(MAXJ)], "zaps": [],
               "bubbles": [], "kick": 0.0, "zapcd": 0.0, "flash": 0.0, "black": 0.0, "cv": None, "bonuscd": 0.0,
               "dark": None, "glow": {}, "shake": 0.0, "stung": 0.0, "lastbeat": 0})

def setup(screen, eyesy):
    reset()

# ---------------------------------------------------------------- glow sprites
def make_glow(hue):
    sz = 220
    s = pygame.Surface((sz, sz))
    s.fill((0, 0, 0))
    for r in range(110, 3, -6):
        v = int(255 * (1.0 - r / 110.0) ** 2 * 0.75)
        pygame.draw.circle(s, (v, v, v), (sz // 2, sz // 2), r)
    s.fill(hsv(hue, 0.85, 1.0), special_flags=pygame.BLEND_RGB_MULT)
    return s

def glow_sprite(S, hue):
    k = int(hue * 12.0 + 0.5) % 12
    g = S["glow"].get(k)
    if g is None:
        g = S["glow"][k] = make_glow(k / 12.0)
    return g

# ---------------------------------------------------------------- the room
def draw_room(cv, wall, t):
    cv.fill(wall)
    # pineapple-ish diamond pattern on the wall
    pat = mulc(wall, 0.88)
    for xx in range(-40, W + 80, 120):
        pygame.draw.line(cv, pat, (xx, 0), (xx + 360, FLOOR), 2)
        pygame.draw.line(cv, pat, (xx + 360, 0), (xx, FLOOR), 2)
    # floor + baseboard
    pygame.draw.rect(cv, (112, 66, 34), (0, FLOOR, W, H - FLOOR))
    for k in range(6):
        y = FLOOR + 10 + k * 24
        pygame.draw.line(cv, (84, 48, 24), (0, y), (W, y), 3)
    pygame.draw.rect(cv, (150, 90, 44), (0, FLOOR - 12, W, 14))
    # stair doorway on the left
    pygame.draw.rect(cv, (28, 18, 36), (24, 250, 180, FLOOR - 250 - 12))
    pygame.draw.ellipse(cv, (28, 18, 36), (24, 190, 180, 120))
    for k in range(5):
        y = 420 + k * 30
        pygame.draw.line(cv, (70, 50, 80), (24 + k * 16, y), (204, y - 24), 4)
    pygame.draw.arc(cv, (160, 100, 50), (24, 190, 180, 120), 0.0, 3.1416, 6)
    pygame.draw.line(cv, (160, 100, 50), (24, 250), (24, FLOOR - 12), 6)
    pygame.draw.line(cv, (160, 100, 50), (204, 250), (204, FLOOR - 12), 6)
    # framed picture of the best friends
    pygame.draw.rect(cv, (140, 90, 50), (262, 150, 110, 84))
    pygame.draw.rect(cv, (190, 220, 255), (270, 158, 94, 68))
    pygame.draw.circle(cv, (150, 220, 120), (298, 192), 16)
    pygame.draw.circle(cv, (255, 232, 70), (338, 192), 16)
    pygame.draw.arc(cv, INK, (290, 188, 16, 10), 3.5, 5.9, 2)
    pygame.draw.arc(cv, INK, (330, 188, 16, 10), 3.5, 5.9, 2)

def draw_window(cv, t, shake, stung, kick):
    x, y, w, h = 1040, 90, 190, 230
    pygame.draw.rect(cv, (24, 30, 80), (x, y, w, h))
    for k in range(7):
        sx = x + (k * 61) % (w - 6) + 4
        sy = y + (k * 37) % (h // 2)
        pygame.draw.circle(cv, (220, 220, 255), (sx, sy), 2)
    # Squidward in the window, shaken by the bass
    cx = x + w // 2 + math.sin(t * 40.0) * shake * 5
    cy = y + 150 + math.cos(t * 33.0) * shake * 4
    skin = mixc((120, 190, 170), (230, 150, 70), clamp(stung))
    pygame.draw.ellipse(cv, skin, (cx - 52, cy - 88, 104, 120))
    pygame.draw.ellipse(cv, mulc(skin, 0.82), (cx - 18, cy - 30, 36, 62))           # the nose
    for s in (-1, 1):
        ex = cx + s * 24
        pygame.draw.circle(cv, WHITE, (int(ex), int(cy - 40)), 14)
        pygame.draw.circle(cv, (0, 0, 0), (int(ex - s * 2), int(cy - 38)), 4)
        pygame.draw.polygon(cv, skin, [(ex - 16, cy - 56), (ex + 16, cy - 56), (ex + s * 16, cy - 36 + s * 0), (ex - s * 16, cy - 42)])
        pygame.draw.line(cv, INK, (ex - s * 16, cy - 56), (ex + s * 16, cy - 44), 3)
    mh = 6 + int(14 * clamp(stung + kick * 0.5))
    pygame.draw.ellipse(cv, (60, 20, 30), (cx - 20, cy + 22, 40, mh))
    pygame.draw.rect(cv, (210, 215, 235), (cx - 60, cy + 38, 120, 50))              # pajama collar
    for k in range(5):
        pygame.draw.line(cv, (110, 130, 220), (cx - 60 + k * 30, cy + 38), (cx - 60 + k * 30, cy + 88), 4)
    # frame, cross-bars, curtains
    pygame.draw.rect(cv, (150, 95, 50), (x, y, w, h), 8)
    pygame.draw.line(cv, (150, 95, 50), (x + w // 2, y), (x + w // 2, y + h), 4)
    pygame.draw.polygon(cv, (200, 70, 80), [(x - 4, y), (x + 30, y), (x + 12, y + h)])
    pygame.draw.polygon(cv, (200, 70, 80), [(x + w + 4, y), (x + w - 30, y), (x + w - 12, y + h)])

def draw_stereo(cv, t, level, kick, beat):
    x, y = STX, STY
    pygame.draw.rect(cv, (70, 72, 90), (x - 120, y, 240, 110))
    pygame.draw.rect(cv, (30, 30, 40), (x - 120, y, 240, 110), 4)
    pygame.draw.rect(cv, (50, 52, 66), (x - 120, y - 14, 240, 16))
    pygame.draw.arc(cv, (30, 30, 40), (x - 40, y - 36, 80, 50), 0.0, 3.14, 5)       # carrying handle
    for s in (-1, 1):
        r = int(34 + 6 * kick)
        pygame.draw.circle(cv, (24, 24, 30), (x + s * 74, y + 55), r + 6)
        pygame.draw.circle(cv, (90, 94, 118), (x + s * 74, y + 55), r)
        pygame.draw.circle(cv, (40, 42, 56), (x + s * 74, y + 55), int(r * 0.45))
    # equalizer bars
    for k in range(8):
        hh = 8 + 40 * clamp(0.25 + level * 0.7 + 0.35 * abs(math.sin(t * 6.0 + k * 1.3 + beat)) * (0.4 + kick))
        col = hsv(0.33 - 0.33 * k / 7.0, 0.9, 1.0)
        pygame.draw.rect(cv, col, (x - 36 + k * 9, y + 92 - hh, 7, hh))

def draw_lasers(cv, t, beat, hue, power, sweep):
    n = 9
    for i in range(n):
        a = -1.57 + math.sin(t * sweep + i * 0.9) * (0.9 + 0.5 * math.sin(t * 0.37 + i)) + (i - n / 2.0) * 0.16
        col = hsv(hue + (i % 4) * 0.17, 0.9, 1.0)
        ex, ey = STX + math.cos(a) * 1500, STY + math.sin(a) * 1500
        # beams on the beat flare brighter
        glow = mulc(col, 0.35 + 0.35 * power)
        pygame.draw.line(cv, glow, (STX, STY), (ex, ey), 9)
        pygame.draw.line(cv, col, (STX, STY), (ex, ey), 4)
        pygame.draw.line(cv, WHITE, (STX, STY), (ex, ey), 1)
        # a dot where the beam hits the room
        hx = clamp(STX + math.cos(a) * 560, 0, W)
        pygame.draw.circle(cv, col, (int(STX + math.cos(a) * 480), int(STY + math.sin(a) * 480)), 9)

# ---------------------------------------------------------------- jellyfish
def draw_jelly(cv, j, hue, size, t, shimmer, glow_spr):
    x, y = j["x"], j["y"]
    s = size * j["sz"]
    p = j["pulse"]                                   # 0 = relaxed .. 1 = squeezed
    w = 62.0 * s * (1.0 - 0.2 * p)
    h = 56.0 * s * (1.0 + 0.2 * p)
    hh = (hue + j["hue"] + shimmer * math.sin(t * 2.0 + j["id"] * 0.9) * 0.5) % 1.0
    body = hsv(hh, 0.42, 1.0)
    shade = hsv(hh, 0.62, 0.86)
    light = hsv(hh, 0.22, 1.0)
    rim = hsv(hh, 0.75, 0.62)

    # glow halo behind the jelly
    cv.blit(glow_spr, (x - 110, y - 100), special_flags=pygame.BLEND_RGB_ADD)

    n = 5
    for i in range(n):
        tx = x + (i - (n - 1) / 2.0) * w * 0.4
        pts = []
        length = h * (1.5 + 0.2 * (i % 2)) * (1.0 - 0.15 * p)
        for k in range(8):
            u = k / 7.0
            sway = math.sin(t * 3.0 + j["ph"] + i * 0.8 - u * 3.0) * 8.0 * s * u
            pts.append((tx + sway, y + u * length))
        pygame.draw.lines(cv, shade, False, pts, max(2, int(4 * s)))
    for sgn in (-1, 1):
        pts = []
        for k in range(7):
            u = k / 6.0
            pts.append((x + sgn * w * 0.14 + math.sin(t * 2.4 + j["ph"] + u * 3 + sgn) * 7 * s * u, y + u * h * 1.15))
        pygame.draw.lines(cv, light, False, pts, max(3, int(7 * s)))

    def dome(ww, hhh, col, yy):
        pts = []
        for k in range(17):
            a = math.pi * k / 16.0
            pts.append((x + math.cos(a) * ww, yy - math.sin(a) * hhh))
        pts.append((x - ww, yy))
        sc = 7
        for k in range(sc + 1):
            u = k / float(sc)
            pts.append((x - ww + 2 * ww * u, yy + 4 * s * math.sin(u * math.pi * sc)))
        pygame.draw.polygon(cv, col, pts)
    dome(w + 3, h + 3, rim, y)
    dome(w, h, body, y)
    pygame.draw.ellipse(cv, light, (x - w * 0.55, y - h * 0.82, w * 0.7, h * 0.42))
    for sx, sy, sr in ((-0.45, -0.35, 0.14), (0.35, -0.5, 0.11), (0.5, -0.2, 0.09), (-0.1, -0.7, 0.08)):
        pygame.draw.circle(cv, shade, (int(x + sx * w), int(y + sy * h)), max(2, int(sr * w)))
    pygame.draw.arc(cv, rim, (x - w, y - h, 2 * w, 2 * h), 0.2, 2.9, 2)

def draw_zap(cv, a, b, col, life):
    x0, y0, x1, y1 = a["x"], a["y"] - 10, b["x"], b["y"] - 10
    pts = [(x0, y0)]
    n = 9
    rnd = random.Random(int(life * 40) + a["id"] * 7 + b["id"])
    for i in range(1, n):
        u = i / float(n)
        pts.append((lerp(x0, x1, u) + rnd.uniform(-18, 18), lerp(y0, y1, u) + rnd.uniform(-18, 18)))
    pts.append((x1, y1))
    pygame.draw.lines(cv, col, False, pts, 9)
    pygame.draw.lines(cv, (255, 250, 170), False, pts, 5)
    pygame.draw.lines(cv, WHITE, False, pts, 2)

# ---------------------------------------------------------------- SpongeBob, dancing
def draw_bob(cv, x, y, t, B, kick, toss, mouth):
    f = frac(B)
    hop = math.exp(-f * 3.0) * 26 + kick * 8
    y = y - hop
    sway = math.sin(B * math.pi) * 10
    if toss > 0:
        y -= toss * (40 + 170 * abs(math.sin(B * math.pi * 0.5)))
        sway += toss * math.sin(t * 5.0) * 60
    x = x + sway
    sq = 1.0 + 0.06 * math.sin(f * 6.283)
    for s in (-1, 1):
        pygame.draw.line(cv, (250, 225, 80), (x + s * 28, y - 20), (x + s * 28 + s * 6 * math.sin(B * math.pi), y + 36), 7)
        pygame.draw.rect(cv, WHITE, (x + s * 28 - 6, y + 12, 12, 14))
        pygame.draw.rect(cv, (200, 40, 40), (x + s * 28 - 6, y + 22, 12, 4))
        pygame.draw.ellipse(cv, (20, 20, 20), (x + s * 28 - 15 + s * 3, y + 34, 26, 12))
    pygame.draw.rect(cv, (150, 100, 60), (x - 55, y - 40, 110, 30))
    pygame.draw.rect(cv, (110, 70, 40), (x - 55, y - 40, 110, 30), 2)
    pygame.draw.rect(cv, WHITE, (x - 55, y - 62, 110, 24))
    pygame.draw.polygon(cv, (210, 40, 50), [(x, y - 60), (x - 7, y - 48), (x - 5, y - 30), (x + 5, y - 30), (x + 7, y - 48)])
    top = y - 62 - 110 * sq
    # arms flail on the beat
    for s in (-1, 1):
        ph = 0.0 if s < 0 else math.pi
        ang = -1.57 + s * 0.8 + s * math.sin(B * math.pi + ph) * 0.9
        sx, sy = x + s * 55, top + 66
        ex, ey = sx + math.cos(ang) * 62, sy + math.sin(ang) * 62
        pygame.draw.line(cv, (250, 225, 80), (sx, sy), (ex, ey), 8)
        pygame.draw.circle(cv, (250, 225, 80), (int(ex), int(ey)), 8)
    pygame.draw.rect(cv, (255, 232, 70), (x - 55, top, 110, 110 * sq))
    pygame.draw.rect(cv, (200, 170, 30), (x - 55, top, 110, 110 * sq), 3)
    for hx, hy, hr in ((-36, 18, 7), (30, 28, 9), (-20, 80, 6), (40, 70, 5), (-40, 55, 4)):
        pygame.draw.circle(cv, (210, 180, 40), (int(x + hx), int(top + hy * sq)), hr)
    for s in (-1, 1):
        ex, ey = x + s * 18, top + 36
        pygame.draw.circle(cv, WHITE, (int(ex), int(ey)), 17)
        pygame.draw.circle(cv, INK, (int(ex), int(ey)), 17, 2)
        pygame.draw.circle(cv, (70, 150, 255), (int(ex + 2), int(ey + 1)), 7)
        pygame.draw.circle(cv, (0, 0, 0), (int(ex + 2), int(ey + 1)), 3)
        for k in range(3):
            pygame.draw.line(cv, INK, (ex, ey - 17), (ex + (k - 1) * 8, ey - 25), 2)
    pygame.draw.circle(cv, (255, 160, 90), (int(x - 38), int(top + 62)), 8)
    pygame.draw.circle(cv, (255, 160, 90), (int(x + 38), int(top + 62)), 8)
    mh = 8 + 18 * mouth
    pygame.draw.ellipse(cv, (120, 30, 40), (x - 24, top + 60, 48, mh))
    pygame.draw.rect(cv, WHITE, (x - 12, top + 60, 11, 8))
    pygame.draw.rect(cv, WHITE, (x + 1, top + 60, 11, 8))
    pygame.draw.arc(cv, INK, (x - 30, top + 48, 60, 36), 3.6, 5.8, 3)

def draw_gary(cv, x, y, B, kick):
    f = frac(B * 2.0)
    c = math.exp(-f * 7.0)                           # 1 right at the click, then eyes spring apart
    pygame.draw.ellipse(cv, (130, 170, 225), (x - 70, y - 30, 160, 36))
    pygame.draw.circle(cv, (235, 130, 150), (int(x - 10), int(y - 52)), 48)
    pygame.draw.circle(cv, (190, 90, 120), (int(x - 10), int(y - 52)), 48, 3)
    pygame.draw.arc(cv, (190, 90, 120), (x - 40, y - 82, 60, 60), 0.5, 5.0, 3)
    pygame.draw.arc(cv, (190, 90, 120), (x - 26, y - 68, 32, 32), 1.0, 5.4, 3)
    for s in (-1, 1):
        bx = x + 78
        ex = bx + s * (18 - 15 * c)
        pygame.draw.line(cv, (130, 170, 225), (bx, y - 24), (ex, y - 72), 6)
        pygame.draw.circle(cv, WHITE, (int(ex), int(y - 78)), 12)
        pygame.draw.circle(cv, INK, (int(ex), int(y - 78)), 12, 2)
        pygame.draw.circle(cv, (0, 0, 0), (int(ex - s * 2), int(y - 76)), 4)
    if c > 0.5:                                      # the click
        cx = x + 78
        for k in range(5):
            a = -1.57 + (k - 2) * 0.6
            pygame.draw.line(cv, (255, 250, 160), (cx + math.cos(a) * 20, y - 80 + math.sin(a) * 20),
                             (cx + math.cos(a) * 34, y - 80 + math.sin(a) * 34), 3)

# ---------------------------------------------------------------- main
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

    size = (0.6 + k1 * 1.0) * (1.0 + 0.45 * env[0])
    bpm = 80.0 + k2 * 90.0
    count = 1 + int(k3 * 18.99)

    try:
        level = clamp(max(abs(v) for v in eyesy.audio_in[:100]) / 30000.0)
    except Exception:
        level = 0.0
    kicked = level > 0.35 and S["kick"] < 0.5
    S["kick"] = max(S["kick"] * math.exp(-dt * 6.0), level)
    if getattr(eyesy, "trig", False):
        S["kick"] = 1.0
        kicked = True
    kick = S["kick"]

    # beat clock: free-runs at the knob tempo, snaps to the real kick when there is one
    S["beat"] += dt * bpm / 60.0
    if kicked:
        S["beat"] = math.floor(S["beat"]) + 1.0
        S["flash"] = 1.0
        S["shake"] = 1.0
    B = S["beat"]

    # knob5 flick = strobe storm: black, white, black, white
    S["black"] = max(S["black"] * math.exp(-dt * 2.5), env[4])
    strobe_on = S["black"] > 0.25
    if strobe_on:
        S["flash"] = max(S["flash"], 1.0 if int(t * 14.0) % 2 == 0 else 0.0)
    S["flash"] *= math.exp(-dt * 7.0)
    S["shake"] *= math.exp(-dt * 5.0)
    S["stung"] *= math.exp(-dt * 1.6)

    # ---- colors ----
    fg = eyesy.color_picker(eyesy.knob4)
    mx_, mn_ = max(fg), min(fg)
    if mx_ - mn_ < 12:
        hue = 0.93
    elif mx_ == fg[0]:
        hue = ((fg[1] - fg[2]) / float(mx_ - mn_) / 6.0) % 1.0
    elif mx_ == fg[1]:
        hue = ((fg[2] - fg[0]) / float(mx_ - mn_) / 6.0 + 1.0 / 3.0) % 1.0
    else:
        hue = ((fg[0] - fg[1]) / float(mx_ - mn_) / 6.0 + 2.0 / 3.0) % 1.0
    hue += mom[3] * 1.2 + env[3] * 0.1 * math.sin(t * 9.0)
    shimmer = env[3] * 0.5
    bg = eyesy.color_picker_bg(eyesy.knob5)
    wall = mixc(bg, (255, 175, 70), 0.78)

    native = (xres, yres) == (W, H)
    if native:
        cv = screen
    else:
        if S["cv"] is None:
            S["cv"] = pygame.Surface((W, H))
        cv = S["cv"]

    # ---- room, windowed neighbor, then darkness so the lasers pop ----
    if eyesy.auto_clear:                                       # screen-clear off: the old picture stays and new things pile on top
        draw_room(cv, wall, t)
        draw_window(cv, t, S["shake"], S["stung"], kick)
        if S["dark"] is None:
            S["dark"] = pygame.Surface((W, H))
            S["dark"].fill((6, 4, 20))
        S["dark"].set_alpha(int(clamp(0.52 - 0.4 * S["flash"] - 0.2 * kick) * 255))
        cv.blit(S["dark"], (0, 0))

    power = clamp(0.4 + kick * 0.6)
    draw_lasers(cv, t, B, hue, power, 0.6 + k2 * 2.2 + env[1] * 1.5)
    draw_stereo(cv, t, level, kick, B)

    # ---- bubbles pop out of the stereo on every kick ----
    if kicked:
        for _ in range(6):
            S["bubbles"].append({"x": STX + random.uniform(-100, 100), "y": STY - 20, "vx": random.uniform(-40, 40),
                                 "vy": random.uniform(-220, -110), "r": random.uniform(5, 14), "life": random.uniform(1.0, 2.0)})

    # ---- bonus jellies pour in the doorway when knob3 is flicked ----
    S["bonuscd"] -= dt
    if env[2] > 0.6 and S["bonuscd"] <= 0.0:
        S["bonuscd"] = 0.3
        S["jel"].append(new_jelly(random.randint(200, 900), temp=True))

    # ---- zaps (knob2 flick = electric panic) ----
    S["zapcd"] -= dt
    storm = env[1] > 0.5
    active = S["jel"][:count] + S["jel"][MAXJ:]
    if len(active) > 1 and (storm and S["zapcd"] <= 0.0 or kicked and random.random() < 0.4):
        S["zapcd"] = 0.12
        a = random.choice(active)
        b = min((o for o in active if o is not a), key=lambda o: (o["x"] - a["x"]) ** 2 + (o["y"] - a["y"]) ** 2)
        S["zaps"].append([a, b, 0.0])
        a["pulse"] = 1.0
        b["pulse"] = 1.0
        S["stung"] = min(1.0, S["stung"] + 0.2)

    # ---- jellies: dance on the beat ----
    sweepx = 0.6 + k2
    for j in S["jel"]:
        f = frac(B + j["off"])
        hop = math.exp(-f * 3.0) * (28.0 + 40.0 * k2)
        j["pulse"] = max(math.exp(-f * 4.0) * 0.9, j["pulse"] * math.exp(-dt * 6.0), kick * 0.5)
        j["x"] = j["bx"] + math.sin(t * 0.8 * sweepx + j["ph"]) * (18.0 + 22.0 * k2)
        j["y"] = j["by"] + math.sin(t * 1.3 + j["ph"]) * 10.0 - hop
        if j["temp"]:
            if j["state"] == "in":
                j["bx"] += 0.0
                j["x"] = lerp(j["x"], j["bx"], 0.0)
                j["life"] -= dt
                if j["life"] < 0:
                    j["state"] = "out"
            if j["state"] == "in" and j.get("arrive", 0.0) < 1.0:
                j["arrive"] = min(1.0, j.get("arrive", 0.0) + dt * 0.8)
                j["x"] = lerp(60.0, j["bx"], j["arrive"])
            if j["state"] == "out":
                j["gone"] = j.get("gone", 0.0) + dt * 0.8
                j["x"] = lerp(j["bx"], -120.0, min(1.0, j["gone"]))
    S["jel"] = [j for j in S["jel"] if not (j["temp"] and j["state"] == "out" and j.get("gone", 0.0) >= 1.0)]

    # SpongeBob goes behind the crowd when there are a lot of jellies
    toss = clamp((k3 - 0.72) / 0.28)
    mouth = clamp(kick + 0.3 * abs(math.sin(B * math.pi)) + toss * 0.4)

    # back to front: jellies above the floor line, then Gary and SpongeBob
    vis = S["jel"][:count] + S["jel"][MAXJ:]
    for j in sorted(vis, key=lambda q: q["y"]):
        draw_jelly(cv, j, hue, size, t, shimmer, glow_spr=glow_sprite(S, hue + j["hue"]))

    for z in S["zaps"]:
        z[2] += dt
        draw_zap(cv, z[0], z[1], hsv(hue + 0.55, 0.6, 1.0), z[2])
    S["zaps"] = [z for z in S["zaps"] if z[2] < 0.22]

    draw_gary(cv, 930, 655, B, kick)
    draw_bob(cv, 420, 650, t, B, kick, toss, mouth)

    # bubbles
    for b in S["bubbles"]:
        b["life"] -= dt
        b["x"] += (b["vx"] + math.sin(t * 6 + b["y"] * 0.04) * 25) * dt
        b["y"] += b["vy"] * dt
        pygame.draw.circle(cv, (200, 230, 255), (int(b["x"]), int(b["y"])), int(b["r"]), 2)
        pygame.draw.circle(cv, WHITE, (int(b["x"] - b["r"] * 0.3), int(b["y"] - b["r"] * 0.3)), max(1, int(b["r"] * 0.2)))
    S["bubbles"] = [b for b in S["bubbles"] if b["life"] > 0]

    # strobe flash over everything
    if S["flash"] > 0.04:
        ov = S.get("flashov")
        if ov is None:
            ov = S["flashov"] = pygame.Surface((W, H))
            ov.fill((255, 255, 255))
        ov.set_alpha(int(clamp(S["flash"]) * 0.7 * 255))
        cv.blit(ov, (0, 0))

    if not native:
        pygame.transform.smoothscale(cv, (xres, yres), screen)
