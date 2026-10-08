# OGMagic8Ball (3D)
# A glossy black Magic 8-Ball from the 2000s, in 3D. The ball is a lit sphere with the white "8" circle on one side
# and the little round window on the other. Behind the window is very dark fluid with the 20-sided die (an
# icosahedron) floating in it. Like the real toy, you cannot see the die at all until one of its faces presses
# against the glass; then that face's answer glows through. Each of the 20 triangular faces carries one of the 20
# classic answers (10 yes, 5 maybe, 5 no), in the real wording, and the die is a real 3D object that tumbles
# unseen in the fluid when shaken. The ball starts with the 8 facing you, then flips over to show its window.
#
# Knobs (this mode's own set, as requested):
#   knob1 = SPIN UP / DOWN      tilts the ball over the top (a full turn across the knob's range)
#   knob2 = SPIN LEFT / RIGHT   turns the ball around (a full turn across the knob's range)
#   knob3 = ZOOM                small ball far away  ->  zoomed right in on the window so you can read the die
#   knob4 = SHAKE               wiggle the knob and the ball shakes hard; the die tumbles in the fluid. Stop and the
#                               die floats up to the window, spinning, and lands on a RANDOM answer
#   knob5 = background color
# Turning knob1 / knob2 QUICKLY also shakes the ball (slow turns just rotate it), so you can jerk the ball around
# like a real one. All knobs are relative to where they sit when the mode loads (the desktop starts them at 0.2).
import math
import random
import time
import pygame
import pygame.gfxdraw

# ---------------------------------------------------------------- the 20 answers, as printed on the die
# (each phrase is split into lines for the triangle: short lines at the narrow top, long ones at the wide bottom)
ANSWERS = (
    ("IT IS", "CERTAIN"),
    ("IT IS", "DECIDEDLY", "SO"),
    ("WITHOUT", "A DOUBT"),
    ("YES", "DEFINITELY"),
    ("YOU MAY", "RELY ON IT"),
    ("AS I SEE", "IT, YES"),
    ("MOST", "LIKELY"),
    ("OUTLOOK", "GOOD"),
    ("YES",),
    ("SIGNS", "POINT", "TO YES"),
    ("REPLY HAZY", "TRY AGAIN"),
    ("ASK AGAIN", "LATER"),
    ("BETTER NOT", "TELL YOU", "NOW"),
    ("CANNOT", "PREDICT", "NOW"),
    ("CONCENTRATE", "AND ASK", "AGAIN"),
    ("DON'T", "COUNT", "ON IT"),
    ("MY REPLY", "IS NO"),
    ("MY SOURCES", "SAY NO"),
    ("OUTLOOK", "NOT SO", "GOOD"),
    ("VERY", "DOUBTFUL"),
)

WIN_A = 0.38              # angular radius of the window (the ball has radius 1)
RIM_A = 0.49              # angular radius of the dark bezel around the window
WIN_D = math.cos(WIN_A)   # the flat window plate sits this far from the ball's center
GAP = 0.012               # the die floats this far behind the glass when it is resting against it
EDGE = 0.64               # edge length of the die (ball radius = 1)
TEX_W, TEX_H = 512, 443   # text texture of one die face

LIQUID_EDGE = (1, 2, 9)
LIQUID_MID = (5, 9, 30)
LIGHT_V = (-0.35, 0.55, 0.76)

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))
def ease(t): t = clamp(t); return t * t * (3 - 2 * t)
def lerp(a, b, t): return a + (b - a) * t
def lerp_c(a, b, t): return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))

# ---------------------------------------------------------------- tiny 3D helpers (x right, y up, z toward the viewer)
def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return ((1, 0, 0), (0, c, -s), (0, s, c))

def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return ((c, 0, s), (0, 1, 0), (-s, 0, c))

def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return ((c, -s, 0), (s, c, 0), (0, 0, 1))

def mm(A, B):
    return tuple(tuple(A[i][0] * B[0][j] + A[i][1] * B[1][j] + A[i][2] * B[2][j] for j in range(3)) for i in range(3))

def mv(R, v):
    return (R[0][0] * v[0] + R[0][1] * v[1] + R[0][2] * v[2],
            R[1][0] * v[0] + R[1][1] * v[1] + R[1][2] * v[2],
            R[2][0] * v[0] + R[2][1] * v[1] + R[2][2] * v[2])

def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def norm(a):
    l = math.sqrt(dot(a, a)) or 1.0
    return (a[0] / l, a[1] / l, a[2] / l)

_l = math.sqrt(dot(LIGHT_V, LIGHT_V))
LIGHT_V = tuple(c / _l for c in LIGHT_V)

# ---------------------------------------------------------------- quaternions (w, x, y, z) for the tumbling die
def qmul(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return (w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2)

def qnorm(q):
    l = math.sqrt(q[0] ** 2 + q[1] ** 2 + q[2] ** 2 + q[3] ** 2) or 1.0
    return (q[0] / l, q[1] / l, q[2] / l, q[3] / l)

def qaxis(axis, ang):
    s = math.sin(ang / 2)
    return (math.cos(ang / 2), axis[0] * s, axis[1] * s, axis[2] * s)

def qmat(q):
    w, x, y, z = q
    return ((1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
            (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
            (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)))

def qfrom_mat(m):
    tr = m[0][0] + m[1][1] + m[2][2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        q = (0.25 * s, (m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s)
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2
        q = ((m[2][1] - m[1][2]) / s, 0.25 * s, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s)
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2
        q = ((m[0][2] - m[2][0]) / s, (m[0][1] + m[1][0]) / s, 0.25 * s, (m[1][2] + m[2][1]) / s)
    else:
        s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2
        q = ((m[1][0] - m[0][1]) / s, (m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, 0.25 * s)
    return qnorm(q)

def qslerp(a, b, t):
    d = a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3]
    if d < 0:
        b = (-b[0], -b[1], -b[2], -b[3])
        d = -d
    if d > 0.9995:
        return qnorm(tuple(a[i] + (b[i] - a[i]) * t for i in range(4)))
    th = math.acos(d)
    s = math.sin(th)
    wa, wb = math.sin((1 - t) * th) / s, math.sin(t * th) / s
    return tuple(a[i] * wa + b[i] * wb for i in range(4))

def random_unit(rng):
    while True:
        v = (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))
        l = dot(v, v)
        if 0.05 < l <= 1.0:
            l = math.sqrt(l)
            return (v[0] / l, v[1] / l, v[2] / l)

# ---------------------------------------------------------------- the die: icosahedron + one text texture per face
PHI = (1 + 5 ** 0.5) / 2
_RAW = ((-1, PHI, 0), (1, PHI, 0), (-1, -PHI, 0), (1, -PHI, 0), (0, -1, PHI), (0, 1, PHI),
        (0, -1, -PHI), (0, 1, -PHI), (PHI, 0, -1), (PHI, 0, 1), (-PHI, 0, -1), (-PHI, 0, 1))
_TRIS = ((0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
         (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1))
VERTS = [tuple(c * EDGE / 2.0 for c in v) for v in _RAW]       # the raw edge length is 2

_FONTS = {}
FACES = []
_S = {}
_cs = [(math.cos(6.2831853 * i / 64), math.sin(6.2831853 * i / 64)) for i in range(64)]
_clock = time.time

def get_font(sz):
    f = _FONTS.get(sz)
    if f is None:
        try:
            f = pygame.font.SysFont("arial,helvetica,dejavusans", sz, bold=True)
        except Exception:
            f = pygame.font.Font(None, sz)
        _FONTS[sz] = f
    return f

def make_text_texture(lines):
    """the phrase, centred in an upright triangle (apex at the top), as light-blue raised letters with a dark shadow"""
    n = len(lines)
    fs = 18
    for fs in range(130, 17, -2):
        f = get_font(fs)
        lh = int(f.get_height() * 0.86)
        top = 0.64 * TEX_H - lh * n / 2.0
        if top + lh * n > TEX_H - 6:
            continue
        if all(f.size(l)[0] <= TEX_W * (top + i * lh + lh * 0.45) / TEX_H - 10 for i, l in enumerate(lines)):
            break
    f = get_font(fs)
    lh = int(f.get_height() * 0.86)
    top = 0.64 * TEX_H - lh * n / 2.0
    tex = pygame.Surface((TEX_W, TEX_H), pygame.SRCALPHA)
    for i, l in enumerate(lines):
        w = f.size(l)[0]
        x = (TEX_W - w) // 2
        y = int(top + i * lh - (f.get_height() - lh) / 2.0)
        tex.blit(f.render(l, True, (2, 6, 44)), (x + 3, y + 3))
        tex.blit(f.render(l, True, (206, 222, 255)), (x, y))
    return tex

def build_die():
    del FACES[:]
    for k, (a, b, c) in enumerate(_TRIS):
        va, vb, vc = VERTS[a], VERTS[b], VERTS[c]
        center = ((va[0] + vb[0] + vc[0]) / 3.0, (va[1] + vb[1] + vc[1]) / 3.0, (va[2] + vb[2] + vc[2]) / 3.0)
        n = norm(center)
        r = sub(vc, vb)
        mid = ((vb[0] + vc[0]) / 2.0, (vb[1] + vc[1]) / 2.0, (vb[2] + vc[2]) / 2.0)
        up = sub(va, mid)
        if dot(cross(r, up), n) < 0:            # make "text right" x "text up" point out of the die
            b, c = c, b
            r = sub(VERTS[c], VERTS[b])
        rn, un = norm(r), norm(up)
        rest = (rn, un, n)                       # the rotation that turns this face to face the window, text upright
        FACES.append({"ia": a, "ib": b, "ic": c, "n": n, "c": center, "rest_q": qfrom_mat(rest),
                      "tex": make_text_texture(ANSWERS[k])})

def warp(tex, a, b, c, d):
    """draw tex through the 2x2 matrix [[a, b], [c, d]] (texture x, y -> screen x, y). Any 2x2 matrix is
    rotate * scale * rotate (an SVD), and pygame can do exactly those three things."""
    e, f, g, h = (a + d) / 2.0, (a - d) / 2.0, (c + b) / 2.0, (c - b) / 2.0
    q, r = math.hypot(e, h), math.hypot(f, g)
    s1, s2 = q + r, q - r
    a1, a2 = math.atan2(g, f), math.atan2(h, e)
    theta, phi = (a2 - a1) / 2.0, (a2 + a1) / 2.0
    if s2 < 0:                                   # mirrored (a back face): never drawn
        return None
    s2 = max(s2, 0.02)
    p = min(1.0, max(s1, s2))                   # shrink the texture first when it will end up small: much cheaper to rotate
    if p < 0.999:
        tex = pygame.transform.smoothscale(tex, (max(2, int(tex.get_width() * p)), max(2, int(tex.get_height() * p))))
        s1, s2 = s1 / p, s2 / p
    t = tex
    if abs(theta) > 0.005:
        t = pygame.transform.rotozoom(t, -math.degrees(theta), 1.0)
    w, hh = t.get_size()
    nw, nh = int(w * s1), int(hh * s2)
    if nw < 2 or nh < 2 or nw > 3000 or nh > 3000:
        return None
    t = pygame.transform.smoothscale(t, (nw, nh))
    if abs(phi) > 0.005:
        t = pygame.transform.rotozoom(t, -math.degrees(phi), 1.0)
    return t

def draw_body(surf, cx, cy, R, ncirc=40):
    """the glossy black sphere: nested circles, shifted toward the light, from a faint bright rim to a dark core to a soft glow"""
    for i in range(ncirc + 1):
        u = i / float(ncirc)
        if u < 0.1:
            col = lerp_c((26, 27, 36), (8, 8, 11), u / 0.1)
        else:
            col = lerp_c((8, 8, 11), (50, 52, 64), ((u - 0.1) / 0.9) ** 1.7)
        pygame.draw.circle(surf, col, (int(cx - 0.34 * R * u), int(cy - 0.40 * R * u)), max(1, int(R * (1.0 - 0.93 * u))))

def build_body(size=512):
    big = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
    draw_body(big, size, size, size - 1, 60)
    return pygame.transform.smoothscale(big, (size, size))

# ---------------------------------------------------------------- the soft white highlight on the glossy ball
def build_gloss(size=400):
    g = pygame.Surface((size, size), pygame.SRCALPHA)
    h = size / 2.0

    def blob(cx, cy, rx, ry, ang, amax, steps=22):
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        for i in range(steps):
            t = i / float(steps - 1)
            w, hh = rx * 2 * (1 - t * 0.92), ry * 2 * (1 - t * 0.92)
            pygame.draw.ellipse(s, (255, 255, 255, int(amax * t * t)), (size / 2 - w / 2, size / 2 - hh / 2, w, hh))
        s = pygame.transform.rotate(s, ang)
        g.blit(s, (cx - s.get_width() / 2.0, cy - s.get_height() / 2.0))

    blob(h - 0.40 * h, h - 0.52 * h, 0.40 * h, 0.17 * h, 35, 120)         # big soft window reflection
    blob(h - 0.46 * h, h - 0.56 * h, 0.11 * h, 0.05 * h, 35, 255, 12)     # tiny hot specular
    blob(h + 0.45 * h, h + 0.55 * h, 0.30 * h, 0.07 * h, 42, 36)          # faint bounce light bottom right
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (size // 2, size // 2), size // 2 - 1)
    g.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return g

# ---------------------------------------------------------------- state
def reset_state():
    rng = random.Random()
    _S.clear()
    _S.update({
        "rng": rng, "t": 0.0, "last": None, "k0": None, "kp": None,
        "pitch": 0.0, "yaw": 0.0, "vpitch": 0.0, "vyaw": 0.0,
        "vs12": 0.0, "vs4": 0.0, "E": 0.0,
        "mode": "rest", "face": rng.randrange(20), "settle_t": 0.0,
        "q": None, "omega": (0.0, 0.0, 0.0), "omega_t": (0.0, 0.0, 0.0), "omega_next": 0.0,
        "dep": WIN_D - 0.45, "wob_axis": random_unit(rng), "ph": [rng.uniform(0, 6.28) for _ in range(6)],
        "parts": [], "gloss": None,
    })
    _S["target"] = landing(_S["face"], rng)
    _S["q"] = _S["target"]
    for _ in range(34):
        _S["parts"].append(new_particle(rng))

def landing(face, rng):
    """the die's resting orientation: the chosen face against the glass, turned a random amount around the window axis
    (so the text lands at any angle, like a real die, instead of always upright)"""
    return qnorm(qmul(qaxis((0.0, 0.0, 1.0), rng.uniform(0.0, 6.2831853)), FACES[face]["rest_q"]))

def new_particle(rng):
    while True:
        x, y = rng.uniform(-1, 1), rng.uniform(-1, 1)
        if x * x + y * y < 1:
            break
    return {"x": x, "y": y, "z": rng.uniform(0.05, 0.85), "vx": 0.0, "vy": 0.0, "s": rng.uniform(0.7, 1.8)}

def setup(screen, eyesy):
    pygame.font.init()
    build_die()
    reset_state()

# ---------------------------------------------------------------- draw
def draw(screen, eyesy):
    if not FACES:
        build_die()
    if not _S:
        reset_state()
    S = _S
    xres, yres = eyesy.xres, eyesy.yres
    now = _clock()
    if S["last"] is None:
        S["last"] = now
    dt = min(max(now - S["last"], 1e-3), 0.05)
    S["last"] = now
    S["t"] += dt
    t = S["t"]
    rng = S["rng"]

    knobs = (eyesy.knob1, eyesy.knob2, eyesy.knob3, eyesy.knob4, eyesy.knob5)
    if S["k0"] is None:
        S["k0"] = knobs
        S["kp"] = knobs
    k0, kp = S["k0"], S["kp"]
    S["kp"] = knobs

    # ---- knob speed -> shake energy. Slow turns just rotate the ball; fast jerks and knob4 wiggles shake it ----
    v12 = (abs(knobs[0] - kp[0]) + abs(knobs[1] - kp[1])) / dt
    v4 = abs(knobs[3] - kp[3]) / dt
    S["vs12"] += (v12 - S["vs12"]) * (1 - math.exp(-dt * 10))
    S["vs4"] += (v4 - S["vs4"]) * (1 - math.exp(-dt * 10))
    target = max(clamp((S["vs12"] - 1.6) / 2.4), clamp(S["vs4"] * 0.9))
    E = max(target, S["E"] * math.exp(-dt * 2.0))
    S["E"] = E

    # ---- ball rotation: the knobs set a target angle, the heavy ball swings after it on a spring ----
    tgt_pitch = -(knobs[0] - k0[0]) * 6.2831853
    tgt_yaw = (knobs[1] - k0[1]) * 6.2831853
    for _ in range(2):
        h = dt / 2.0
        S["vpitch"] += (90.0 * (tgt_pitch - S["pitch"]) - 13.0 * S["vpitch"]) * h
        S["vyaw"] += (90.0 * (tgt_yaw - S["yaw"]) - 13.0 * S["vyaw"]) * h
        S["pitch"] += S["vpitch"] * h
        S["yaw"] += S["vyaw"] * h
    flip = 3.14159265 * (1.0 - ease((t - 1.3) / 1.6))       # intro: start showing the 8, then roll over to the window
    pitch = S["pitch"] + flip
    roll = E * 0.07 * math.sin(t * 29.0)
    Rb = mm(rot_z(roll), mm(rot_x(pitch), rot_y(S["yaw"])))

    zoom = 0.6 * (10.0 ** clamp(knobs[2]))
    R = 0.44 * yres * zoom
    cx = xres / 2.0 + E * 0.045 * R * (math.sin(t * 31.0 + 1.0) + 0.6 * math.sin(t * 47.0 + 2.0))
    cy = yres / 2.0 + E * 0.060 * R * (math.sin(t * 27.0) + 0.5 * math.sin(t * 53.0 + 1.0))

    # ---- the die inside ----
    update_die(dt, t, E, rng)

    # ---- background ----
    bg = eyesy.color_picker_bg(knobs[4])
    bg = (int(bg[0]), int(bg[1]), int(bg[2]))
    screen.fill(bg)
    if R * 1.4 < yres:
        sh = tuple(int(c * 0.45) for c in bg)
        for i in range(6):
            k = 1.0 - i * 0.1
            w, hh = R * 1.55 * k, R * 0.26 * k
            pygame.draw.ellipse(screen, lerp_c(bg, sh, (i + 1) / 6.0), (cx - w / 2, cy + R * 1.10 - hh / 2, w, hh))

    def proj(p):
        v = mv(Rb, p)
        return (cx + R * v[0], cy - R * v[1], v[2])

    def cap_poly(d, e1, e2, beta, n=64):
        cb, sb = math.cos(beta), math.sin(beta)
        pts, vis = [], 0
        for ca, sa in _cs:
            p = (cb * d[0] + sb * (ca * e1[0] + sa * e2[0]), cb * d[1] + sb * (ca * e1[1] + sa * e2[1]),
                 cb * d[2] + sb * (ca * e1[2] + sa * e2[2]))
            x, y, z = proj(p)
            if z < 0:                           # behind the ball: slide the point onto the visible edge
                dx, dy = x - cx, y - cy
                l = math.hypot(dx, dy) or 1.0
                x, y = cx + dx / l * R, cy + dy / l * R
            else:
                vis += 1
            pts.append((x, y))
        return pts, vis

    # ---- the black ball ----
    if R > 0.55 * yres:                         # big: crop the visible part of a cached sprite instead of filling huge circles
        if S.get("body") is None:
            S["body"] = build_body()
        dest = pygame.Rect(int(cx - R), int(cy - R), int(2 * R), int(2 * R)).clip(pygame.Rect(0, 0, xres, yres))
        if dest.w > 1 and dest.h > 1:
            bs = S["body"].get_width()
            k = bs / (2.0 * R)
            sx0, sy0 = (dest.x - (cx - R)) * k, (dest.y - (cy - R)) * k
            src = pygame.Rect(int(sx0), int(sy0), max(1, int(dest.w * k)), max(1, int(dest.h * k))).clip(S["body"].get_rect())
            if src.w > 0 and src.h > 0:
                screen.blit(pygame.transform.smoothscale(S["body"].subsurface(src), dest.size), dest.topleft)
    else:
        draw_body(screen, cx, cy, R)
        if R > 4:
            pygame.gfxdraw.aacircle(screen, int(cx), int(cy), int(R), (26, 27, 36))

    # ---- the seam where the two halves of the shell meet (a circle halfway between the 8 and the window) ----
    segs = []
    for i in range(97):
        a = 6.2831853 * i / 96
        segs.append(proj((math.cos(a), math.sin(a), 0.0)))
    wide = max(1, int(R / 260))
    for i in range(96):
        x0, y0, z0 = segs[i]
        x1, y1, z1 = segs[i + 1]
        if z0 > 0.02 and z1 > 0.02:
            pygame.draw.line(screen, (3, 3, 5), (x0, y0), (x1, y1), wide + 1)
            pygame.draw.line(screen, (44, 46, 58), (x0 + 1, y0 + 1), (x1 + 1, y1 + 1), 1)

    # ---- the white circle with the 8 ----
    d8, e1_8, e2_8 = (0.0, 0.0, -1.0), (-1.0, 0.0, 0.0), (0.0, 1.0, 0.0)
    if mv(Rb, d8)[2] > -math.sin(0.5):
        pts, vis = cap_poly(d8, e1_8, e2_8, 0.47)
        if vis:
            pygame.draw.polygon(screen, (196, 196, 194), pts)
            pts, vis = cap_poly(d8, e1_8, e2_8, 0.445)
            pygame.draw.polygon(screen, (242, 242, 238), pts)
            for cu, cv, rx, ry in ((0.0, 0.165, 0.118, 0.135), (0.0, -0.14, 0.150, 0.150)):
                for i in range(80):
                    a = 6.2831853 * i / 80
                    u, v = cu + rx * math.cos(a), cv + ry * math.sin(a)
                    p = norm((d8[0] + u * e1_8[0] + v * e2_8[0], d8[1] + u * e1_8[1] + v * e2_8[1], d8[2] + u * e1_8[2] + v * e2_8[2]))
                    x, y, z = proj(p)
                    if z > 0.03:
                        pygame.draw.circle(screen, (10, 10, 12), (int(x), int(y)), max(1, int(0.046 * R * min(1.0, z + 0.15))))

    # ---- the window: dark bezel, then the glass with the fluid and die behind it ----
    dw, e1w, e2w = (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)
    nzw = mv(Rb, dw)[2]
    if nzw > -math.sin(RIM_A):
        pts, vis = cap_poly(dw, e1w, e2w, RIM_A)
        if vis:
            pygame.draw.polygon(screen, (30, 31, 38), pts)
            pygame.draw.lines(screen, (84, 86, 100), True, pts, max(1, int(R / 200)))
    if nzw > 0.03:
        draw_window(screen, S, Rb, proj, cap_poly, dw, e1w, e2w, cx, cy, R, xres, yres, t, E, dt)

    # ---- glossy highlight over everything ----
    if R < 900:
        gsz = int(2 * R)
        if gsz > 8:
            if S["gloss"] is None:
                S["gloss"] = build_gloss()
            g = pygame.transform.smoothscale(S["gloss"], (gsz, gsz))
            screen.blit(g, (int(cx - R), int(cy - R)))

def update_die(dt, t, E, rng):
    S = _S
    q = S["q"]
    S["settle_t"] += dt
    if S["mode"] != "tumble" and E > 0.10:
        S["mode"] = "tumble"
        S["omega_next"] = 0.0
    elif S["mode"] == "tumble" and E < 0.06:                    # the shaking stopped: pick a random answer and float up to it
        S["mode"] = "settle"
        S["settle_t"] = 0.0
        S["face"] = rng.randrange(20)
        S["target"] = landing(S["face"], rng)
        S["wob_axis"] = random_unit(rng)

    if S["mode"] == "tumble":
        S["omega_next"] -= dt
        if S["omega_next"] <= 0:
            mag = 4.0 + 13.0 * min(1.0, E * 1.5)
            S["omega_t"] = tuple(c * mag for c in random_unit(rng))
            S["omega_next"] = rng.uniform(0.10, 0.28)
        om, ot = S["omega"], S["omega_t"]
        k = 1 - math.exp(-dt * 5.0)
        S["omega"] = (om[0] + (ot[0] - om[0]) * k, om[1] + (ot[1] - om[1]) * k, om[2] + (ot[2] - om[2]) * k)
    else:
        f = math.exp(-dt * 3.5)
        om = S["omega"]
        S["omega"] = (om[0] * f, om[1] * f, om[2] * f)
    om = S["omega"]
    sp = math.sqrt(dot(om, om))
    if sp > 1e-4:
        q = qnorm(qmul(qaxis((om[0] / sp, om[1] / sp, om[2] / sp), sp * dt), q))
    if S["mode"] == "settle":
        qt = S["target"]
        st = S["settle_t"]
        q = qslerp(q, qt, 1 - math.exp(-dt * (2.2 + 4.5 * min(st, 1.5))))
        d = abs(sum(q[i] * qt[i] for i in range(4)))
        if st > 0.9 and d > 0.99995:
            S["mode"] = "rest"
            q = qt
    S["q"] = q

def draw_window(screen, S, Rb, proj, cap_poly, dw, e1w, e2w, cx, cy, R, xres, yres, t, E, dt):
    pts, vis = cap_poly(dw, e1w, e2w, WIN_A, 64)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    rect = pygame.Rect(int(min(xs)) - 2, int(min(ys)) - 2, int(max(xs) - min(xs)) + 5, int(max(ys) - min(ys)) + 5)
    rect = rect.clip(pygame.Rect(0, 0, xres, yres))
    if rect.w < 3 or rect.h < 3:
        return
    ox, oy = rect.x, rect.y
    poly = [(x - ox, y - oy) for x, y in pts]
    wc = (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))
    tmp = pygame.Surface(rect.size, pygame.SRCALPHA)

    # the blue fluid, glowing brighter toward the middle
    pygame.draw.polygon(tmp, LIQUID_EDGE, poly)
    for i in range(1, 9):
        k = 1.0 - i / 9.0
        col = lerp_c(LIQUID_EDGE, LIQUID_MID, (i / 9.0) ** 1.2)
        pygame.draw.polygon(tmp, col, [(wc[0] + (x - wc[0]) * k, wc[1] + (y - wc[1]) * k) for x, y in poly])

    # ---- die geometry in ball space ----
    q = S["q"]
    st = S["settle_t"]
    rest_like = S["mode"] != "tumble"
    qd = q
    if S["mode"] == "settle":                       # a little wobble as it lands
        qd = qnorm(qmul(qaxis(S["wob_axis"], 0.22 * math.exp(-st * 2.6) * math.sin(st * 15.0)), q))
    elif S["mode"] == "rest":
        qd = qnorm(qmul(qaxis((0.6, 0.8, 0.0), 0.018 * math.sin(t * 1.3)), q))
    Rd = qmat(qd)
    rv = [mv(Rd, v) for v in VERTS]
    hmax = max(v[2] for v in rv)                    # how far the die reaches toward the glass
    want = WIN_D - 0.02 if rest_like else 0.08 + 0.28 * (1.0 - min(1.0, E * 2.0))
    S["dep"] += (want - S["dep"]) * (1 - math.exp(-dt * (3.0 if want > S["dep"] else 6.0)))
    dep = min(S["dep"], WIN_D - GAP - hmax - (0.012 * math.sin(t * 1.9) + 0.012 if S["mode"] == "rest" else 0.0))
    amp = clamp(E * 2.0) * 0.2
    ph = S["ph"]
    lx = amp * math.sin(t * 2.7 + ph[0]) * math.cos(t * 1.1 + ph[1])
    ly = amp * math.sin(t * 2.1 + ph[2]) * math.cos(t * 1.4 + ph[3])
    if S["mode"] == "rest":
        lx, ly = 0.008 * math.sin(t * 0.8 + ph[0]), 0.008 * math.sin(t * 0.7 + ph[2])
    cl = (lx, ly, dep)                              # die center in ball space
    Rbd = mm(Rb, Rd)
    cv = mv(Rb, cl)
    sv = []
    for v in VERTS:
        w = mv(Rbd, v)
        sv.append((cx + R * (w[0] + cv[0]) - ox, cy - R * (w[1] + cv[1]) - oy, w[2] + cv[2], dot(mv(Rd, v), (0, 0, 1)) + dep))

    # ---- floating specks in the fluid (they swirl when the ball is shaken) ----
    d_v = mv(Rb, (0.0, 0.0, 1.0))
    e1_v = mv(Rb, (1.0, 0.0, 0.0))
    e2_v = mv(Rb, (0.0, 1.0, 0.0))
    dtt = dt
    sw = math.sin(WIN_A)
    for p in S["parts"]:
        p["vx"] += (random.random() - 0.5) * E * 26.0 * dtt
        p["vy"] += (random.random() - 0.5) * E * 26.0 * dtt + 0.012 * dtt
        p["vx"] *= math.exp(-dtt * 2.0)
        p["vy"] *= math.exp(-dtt * 2.0)
        p["x"] += p["vx"] * dtt
        p["y"] += p["vy"] * dtt
        if p["x"] * p["x"] + p["y"] * p["y"] > 1.0:
            p["x"], p["y"] = -p["x"] * 0.95, -p["y"] * 0.95
        px = (p["x"] * sw * e1_v[0] + p["y"] * sw * e2_v[0] - p["z"] * d_v[0] + WIN_D * d_v[0])
        py = (p["x"] * sw * e1_v[1] + p["y"] * sw * e2_v[1] - p["z"] * d_v[1] + WIN_D * d_v[1])
        sx, sy = cx + R * px - ox, cy - R * py - oy
        col = lerp_c((70, 100, 190), LIQUID_MID, clamp(p["z"] * 1.6))
        pygame.draw.circle(tmp, col, (int(sx), int(sy)), max(1, int(p["s"] * R / 240.0)))

    # ---- die faces, far ones first ----
    order = []
    for fi, f in enumerate(FACES):
        nv = mv(Rbd, f["n"])
        if nv[2] <= 0.0:
            continue
        order.append((sv[f["ia"]][2] + sv[f["ib"]][2] + sv[f["ic"]][2], fi, nv))
    order.sort()
    for _z, fi, nv in order:
        f = FACES[fi]
        A, B, C = sv[f["ia"]], sv[f["ib"]], sv[f["ic"]]
        behind = max(0.0, WIN_D - (A[3] + B[3] + C[3]) / 3.0)
        fog = min(0.985, clamp((behind - 0.05) / 0.08) ** 0.7)      # the fluid is nearly black: only what touches the glass shows
        lit = 0.62 + 0.5 * max(0.0, dot(nv, LIGHT_V))
        base = (int(min(255, 17 * lit * 1.7)), int(min(255, 28 * lit * 1.7)), int(min(255, 120 * lit)))
        col = lerp_c(base, LIQUID_MID, fog)
        tri = [(A[0], A[1]), (B[0], B[1]), (C[0], C[1])]
        pygame.draw.polygon(tmp, col, tri)
        pygame.draw.lines(tmp, lerp_c((70, 112, 235), LIQUID_MID, fog), True, tri, max(1, int(R / 170)))
        fx0, fx1 = min(A[0], B[0], C[0]), max(A[0], B[0], C[0])
        fy0, fy1 = min(A[1], B[1], C[1]), max(A[1], B[1], C[1])
        if nv[2] > 0.1 and fog < 0.97 and fx1 > 0 and fy1 > 0 and fx0 < rect.w and fy0 < rect.h:
            Sx, Sy = float(TEX_W), float(TEX_H)
            u = ((C[0] - B[0]) / Sx, (C[1] - B[1]) / Sx)
            v = (((B[0] + C[0]) / 2.0 - A[0]) / Sy, ((B[1] + C[1]) / 2.0 - A[1]) / Sy)
            w = warp(f["tex"], u[0], v[0], u[1], v[1])
            if w is not None:
                w.set_alpha(int(255 * (1.0 - fog) ** 2.5))
                # texture centre (S/2, H/2) is the apex + (H/2) * v
                ccx, ccy = A[0] + v[0] * Sy / 2.0, A[1] + v[1] * Sy / 2.0
                tmp.blit(w, (int(ccx - w.get_width() / 2.0), int(ccy - w.get_height() / 2.0)))

    # ---- reflection on the glass ----
    gl = pygame.Surface(rect.size, pygame.SRCALPHA)
    r1 = (e1_v[0] * R * sw, -e1_v[1] * R * sw)
    r2 = (e2_v[0] * R * sw, -e2_v[1] * R * sw)
    band = [(-1.2, 0.35), (-0.2, 1.2), (0.25, 1.2), (-1.2, -0.25)]
    pygame.draw.polygon(gl, (255, 255, 255, 20), [(wc[0] + a * r1[0] + b * r2[0], wc[1] + a * r1[1] + b * r2[1]) for a, b in band])
    band2 = [(0.1, -1.2), (1.2, 0.2), (1.2, -0.15), (0.45, -1.2)]
    pygame.draw.polygon(gl, (255, 255, 255, 12), [(wc[0] + a * r1[0] + b * r2[0], wc[1] + a * r1[1] + b * r2[1]) for a, b in band2])
    tmp.blit(gl, (0, 0))

    # cut everything to the window shape
    mask = pygame.Surface(rect.size, pygame.SRCALPHA)
    mask.fill((0, 0, 0, 0))
    pygame.draw.polygon(mask, (255, 255, 255, 255), poly)
    tmp.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    screen.blit(tmp, rect.topleft)
    pygame.draw.lines(screen, (6, 7, 12), True, pts, max(2, int(R / 90)))
    pygame.draw.lines(screen, (70, 76, 100), True, pts, 1)
