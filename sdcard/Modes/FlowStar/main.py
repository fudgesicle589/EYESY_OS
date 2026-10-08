# OGFlowStar
# A rave flow star: the printed fabric star people spin at festivals. Two squares layered at 45 degrees
# make the 8 points, with a black border and a trippy print. It spins, wobbles as if tilted in the hand,
# and travels in loops like a held flow toy. The music pumps the print.
#
# Knob convention (same in every mode):
#   knob1 = size            (how big the star is)
#   knob2 = main motion     (spin: 0.5 = still, right = forward, left = backward)
#   knob3 = extra detail    (the print, morphing smoothly: tunnel > checker lotus > rays > spiral web > cosmos)
#   knob4 = foreground color (hue of the print)
#   knob5 = hand style      (the hand's moves: 0 holds the star steady, then wider and wider loops,
#                            then flower petals and deep leaning flips; the background tints itself to match)
#
# Playing it:
#   flick knob2 -> the star whips round and coasts back down to the set speed
#   knob1       -> the star swells while you turn it, then settles
#   knob4       -> the print colors slam round
#   knob3       -> the print melts from one look into the next; there are no hard cuts
import colorsys
import math
import time
import pygame

L = 300                       # size of the star's own drawing surface; it is scaled up onto the screen
C = L / 2.0
R = L / 2.0 - 2.0             # distance from the middle to a star point
H = R / math.sqrt(2.0)        # half the side of each square
BORDER = 10.0

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))

def hsv(h, s, v):
    h = (h % 1.0) * 6.0
    s = clamp(s)
    v = clamp(v) * 255.0
    i = int(h)
    f = h - i
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    r, g, b = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i % 6]
    return (int(r), int(g), int(b))

_state = {"last": None, "theta": 0.0, "omega": 0.0, "hand": 0.0, "tilt": 0.0, "phase": 0.0, "hue": 0.0, "move": 0.0,
          "look": 0.0, "canvas": None, "size": None, "face": None}
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

def pt(r, b, rot):
    a = b + rot
    return (C + r * math.cos(a), C + r * math.sin(a))

def sqr(b, h):
    """distance from a square's middle to its edge in direction b (the square's own frame)"""
    return h / max(abs(math.cos(b)), abs(math.sin(b)), 1e-6)

def corners(h, rot):
    return [pt(h * math.sqrt(2.0), math.pi / 4 + k * math.pi / 2, rot) for k in range(4)]

# one print, many looks. Each keyframe is:
# (ring contrast, ray contrast, ring count, round->square, ring spacing, spiral twist, color spread, planets, sun)
KEYS = [
    (1.0, 0.0, 13.0, 1.0, 1.5, 0.35, 0.16, 0.0, 0.0),    # blue tunnel of square rings
    (1.0, 1.0,  8.0, 0.0, 0.6, 0.5,  0.75, 0.0, 0.0),    # rainbow checker lotus
    (0.0, 1.0,  6.0, 0.5, 1.0, 0.0,  0.5,  0.0, 0.3),    # sunburst of rays
    (1.0, 0.6, 16.0, 1.0, 1.0, 2.4,  0.4,  0.0, 0.0),    # spiral web
    (0.3, 0.3,  5.0, 0.0, 1.0, 0.0,  0.9,  1.0, 1.0),    # cosmic field with planets and a sun
]

def blend_keys(p):
    """a smooth value between the keyframes; each look holds for a moment before it eases to the next"""
    p = clamp(p, 0.0, len(KEYS) - 1.0001)
    i = int(p)
    t = p - i
    t = t * t * (3 - 2 * t)
    a, b = KEYS[i], KEYS[i + 1]
    return [x + (y - x) * t for x, y in zip(a, b)]

W = 24                                    # rays around the star; their edges sit on the square's diagonals

def pattern(face, rot, h2, hue, P, f, n0, twist, glow, level, orbit, wshift):
    rm, wm, nr, sq, e, rtw, hs, om, sun = P
    ri = h2 * 0.8
    dark = (6, 6, 12)
    bright = lambda u2: hsv(hue + hs * (1 - u2), 0.85 - 0.25 * (1 - u2), 0.55 + 0.45 * glow)
    def lerpc(c, v):
        return (int(dark[0] + (c[0] - dark[0]) * v), int(dark[1] + (c[1] - dark[1]) * v), int(dark[2] + (c[2] - dark[2]) * v))
    def at(u, b):
        u2 = u ** e
        return pt(u2 * (ri + (sqr(b, h2) - ri) * sq), b + (rtw + twist) * (1 - u2), rot)
    # the flaps outside the round print fade in as the print stops being square
    if sq < 0.95:
        k = 1.0 - sq
        w = 2 * math.pi / 32
        for i in range(0, 32, 2):
            b0, b1 = i * w, (i + 1) * w
            tri = abs(((i % 8) / 8.0) * 2 - 1)
            col = hsv(hue + 0.55 + 0.22 * tri, 0.8, (0.55 + 0.45 * glow) * k)
            pygame.draw.polygon(face, col, [pt(ri, b0, rot), pt(sqr(b0, h2), b0, rot), pt(sqr(b1, h2), b1, rot), pt(ri, b1, rot)])
    # rings, poured toward the middle
    bands = []
    if rm > 0.02:
        for k in range(int(nr) + 2, 0, -1):
            lo, hi = (k - 1 - f) / nr, (k - f) / nr
            if lo >= 1.0:
                continue
            bands.append((max(lo, 0.0), min(hi, 1.0), (k + n0) % 2))
    else:
        bands.append((0.0, 1.0, 0))
    if wm <= 0.02:
        for lo, hi, rp in bands:
            pts = [at(hi, j * 2 * math.pi / 48) for j in range(48)]
            pygame.draw.polygon(face, lerpc(bright(hi ** e), rm * rp), pts)
    else:
        bands.reverse()                                       # inner to outer
        ang = [i * 2 * math.pi / W for i in range(W + 1)]
        prev = None
        for lo, hi, rp in bands:
            inner = [at(lo, b) for b in ang]
            outer = [at(hi, b) for b in ang]
            col = bright(((lo + hi) / 2) ** e)
            for i in range(W):
                v = abs(rm * rp - wm * ((i + wshift) % 2))
                if v > 0.02:
                    pygame.draw.polygon(face, lerpc(col, v), [inner[i], outer[i], outer[i + 1], inner[i + 1]])
    # planets and a sun grow in as the print turns cosmic
    cen = pt(0, 0, rot)
    if sun > 0.03:
        r = ri * 0.34 * sun * (1 + 0.15 * level)
        for k in range(7):
            t = k / 6.0
            pygame.draw.circle(face, hsv(hue + 0.02 + 0.1 * t, 1.0 - 0.7 * t, 0.7 + 0.3 * t), cen, max(1, int(r * (1 - t * 0.92))))
    if om > 0.05:
        for i in range(8):
            b = i * math.pi / 4 + orbit
            p = pt(ri * 0.68, b, rot)
            hh = hue + 0.35 + i / 8.0 * 0.6
            pygame.draw.circle(face, hsv(hh, 0.7, 0.55 + 0.45 * glow), p, max(1, int(11 * om)))
            pygame.draw.circle(face, hsv(hh, 0.35, 1.0), (p[0] - 3 * om, p[1] - 3 * om), max(1, int(4 * om)))
            q = pt(ri * 0.9, b + math.pi / 8, rot)
            pygame.draw.circle(face, hsv(hue + 0.6 + i / 8.0 * 0.5, 0.8, 0.9), q, max(1, int(6 * om)))

def square(face, rot, hue, P, f, n0, twist, orbit, glow, level, shift):
    h2 = H - BORDER
    pygame.draw.polygon(face, (30, 26, 44), corners(H, rot))            # the dark border, with a lit rim so the points read
    pygame.draw.polygon(face, hsv(hue + 0.5, 0.6, 0.55 + 0.45 * glow), corners(H, rot), 2)
    pygame.draw.polygon(face, (8, 8, 18), corners(h2, rot))
    pattern(face, rot, h2, hue, P, f, n0, twist, glow, level, orbit, shift)

def setup(screen, eyesy):
    _state["canvas"] = None
    _state["face"] = pygame.Surface((L, L), pygame.SRCALPHA)

def draw(screen, eyesy):
    xres, yres = eyesy.xres, eyesy.yres
    now = time.time()
    dt = 1 / 30.0 if _state["last"] is None else min(now - _state["last"], 0.1)
    _state["last"] = now
    vel, env, mom = _play["vel"], _play["env"], _play["mom"]
    knob_play(eyesy, dt)
    if _state["face"] is None:
        _state["face"] = pygame.Surface((L, L), pygame.SRCALPHA)
    if _state["canvas"] is None or _state["size"] != (xres, yres):
        _state["canvas"] = pygame.Surface((xres, yres))
        _state["size"] = (xres, yres)

    try:
        level = clamp(max(abs(v) for v in eyesy.audio_in[:100]) / 30000.0)
    except Exception:
        level = 0.0

    # spin: knob2 sets the speed, a flick adds a burst that coasts back down
    target = (eyesy.knob2 - 0.5) * 2.0
    target = 0.0 if abs(target) < 0.04 else target
    _state["omega"] += (target * 10.0 + mom[1] * 70.0 - _state["omega"]) * min(1.0, dt * 3.0)
    _state["theta"] += _state["omega"] * dt
    spinning = abs(_state["omega"])
    # knob5 is the hand: it glides between holding still, loops, flower petals and big leaning flips
    _state["move"] += (clamp(eyesy.knob5 + mom[4] * 2.0) - _state["move"]) * min(1.0, dt * 3.0)
    mv = _state["move"]
    _state["hand"] += dt * (0.4 + mv * 0.8 + spinning * 0.12)    # the hand circles faster when it moves more
    _state["tilt"] += dt * (0.5 + mv * 1.2 + spinning * 0.1)     # the star leans toward and away from you
    _state["phase"] += dt * (0.6 + level * 2.0 + spinning * 0.1)  # the print flows
    _state["hue"] += mom[3] * 2.0 + dt * 0.02

    fg = eyesy.color_picker(eyesy.knob4)
    hue = colorsys.rgb_to_hsv(fg[0] / 255.0, fg[1] / 255.0, fg[2] / 255.0)[0] + _state["hue"]
    bg = hsv(hue + 0.55, 0.7, 0.05 + 0.08 * level)               # a dark glow in a color that sits opposite the print
    # knob3 slides along the keyframes; the look chases it, so even a quick twist glides rather than cuts
    _state["look"] += (eyesy.knob3 * (len(KEYS) - 1) - _state["look"]) * min(1.0, dt * 3.0)
    P = blend_keys(_state["look"])

    glow = 0.5 + level * 0.5 + env[1] * 0.2
    f = _state["phase"] % 1.0
    n0 = int(_state["phase"])
    twist = 0.35 * math.sin(_state["tilt"] * 0.5) + _state["omega"] * 0.04
    orbit = _state["theta"] * 0.6 + _state["phase"]

    face = _state["face"]
    face.fill((0, 0, 0, 0))
    square(face, 0.0, hue + 0.08, P, f, n0 + 1, twist, orbit, glow, level, n0)          # underneath
    square(face, math.pi / 4, hue, P, f, n0, twist, -orbit, glow, level, n0 + 1)         # on top
    for k in range(4):                                                                       # the quilted seams
        a = k * math.pi / 4
        pygame.draw.line(face, (0, 0, 0), pt(H * 0.8, a, 0), pt(-H * 0.8, a, 0), 1)

    size = min(xres, yres)
    scale = size * (0.26 + eyesy.knob1 * 0.3 + abs(mom[0]) * 0.8) / R
    img = pygame.transform.rotozoom(face, -math.degrees(_state["theta"]), scale)
    w, h = img.get_size()
    deep = 0.03 + 0.32 * mv                                      # how far the star leans over
    lean = 1.0 - deep * (0.5 - 0.5 * math.cos(_state["tilt"]))
    img = pygame.transform.smoothscale(img, (max(2, int(w * lean)), max(2, int(h * (1.0 - 0.5 * deep * (0.5 - 0.5 * math.sin(_state["tilt"] * 0.7)))))))
    loop = size * 0.17 * mv ** 1.5 + size * 0.015      # a steady hold at 0, wide loops at the top
    petal = size * 0.08 * clamp((mv - 0.4) * 2.0)                # past the middle the loops grow flower petals
    a = _state["hand"]
    px = xres / 2.0 + loop * math.cos(a) + petal * math.cos(a * 3)
    py = yres / 2.0 + loop * math.sin(a) + petal * math.sin(a * 3)

    canvas = _state["canvas"]
    ghost = pygame.Surface((xres, yres))
    ghost.fill(bg)
    ghost.set_alpha(200)                                        # a short smear of the star behind it
    canvas.blit(ghost, (0, 0))
    canvas.blit(img, img.get_rect(center=(int(px), int(py))))
    screen.blit(canvas, (0, 0))
