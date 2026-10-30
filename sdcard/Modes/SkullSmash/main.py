# OGSkullSmash (3D, "breaking the frame")
# A chrome robot skull floating in a neon truss tunnel, with two heavy metal fists that come OUT OF THE SCREEN
# and hammer the floor in front of it. The 3D effect needs no glasses: it is the classic "false frame" pop-out
# illusion. The tunnel lives inside a smaller window with a thick black border around it, and anything that comes
# toward you (the fists and the flying debris) is drawn OVER that border, so it looks like it has broken out of
# the screen and is sticking out toward the viewer. Everything inside is a real 3D scene (a tiny software
# renderer: perspective camera, lit chrome faces, a floor with a shadow under each fist).
#
# Weight: a hand lifts slowly and open (fingers spread, palm to camera), but when you drop it, it FALLS under
# gravity, swinging forward toward you while its fingers curl into a fist. The pinky side of the fist (opposite the thumb) hits the
# floor like a hammer, it freezes for a beat, squashes, and the floor ripples out from the impact, cracks, throws
# debris at you, and the camera and head jolt.
#
# Knobs (this mode's own set, as requested):
#   knob1 = LEFT HAND   height. Turn up to raise it, flick down to POUND. At the bottom the fist is on the floor.
#   knob2 = RIGHT HAND  same, for the right hand. Pound them together, one then the other, or roll them.
#   knob3 = HEAD MOVE   raises and lowers the floating head (it has weight: it lags, overshoots and nods as it moves,
#                       so flick it for a head-bang).
#   knob4 = MOUTH       opens the jaw (0 = shut). SNAP it shut and the jaw chomps and jolts the head. Wiggle it fast
#                       and the teeth gnash. The jaw also opens a little on every kick / loud hit by itself
#                       (the 0 key is a kick on the desktop).
#   knob5 = color       the chrome of the skull and fists. The neon tunnel and floor cycle slowly through every color
#                       on their own.
# (At rest the knobs sit at 0.2: hands hovering low, jaw barely open.)
import colorsys
import math
import random
import time
import pygame

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))
def ease(t): return t * t * (3 - 2 * t)

def hsv(h, s, v):
    """hue/saturation/value (0..1) to an (r, g, b) tuple, written out by hand because it is called a lot per frame"""
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
    (a00, a01, a02), (a10, a11, a12), (a20, a21, a22) = A
    (b00, b01, b02), (b10, b11, b12), (b20, b21, b22) = B
    return ((a00 * b00 + a01 * b10 + a02 * b20, a00 * b01 + a01 * b11 + a02 * b21, a00 * b02 + a01 * b12 + a02 * b22),
            (a10 * b00 + a11 * b10 + a12 * b20, a10 * b01 + a11 * b11 + a12 * b21, a10 * b02 + a11 * b12 + a12 * b22),
            (a20 * b00 + a21 * b10 + a22 * b20, a20 * b01 + a21 * b11 + a22 * b21, a20 * b02 + a21 * b12 + a22 * b22))

def mv(R, v):
    return (R[0][0] * v[0] + R[0][1] * v[1] + R[0][2] * v[2],
            R[1][0] * v[0] + R[1][1] * v[1] + R[1][2] * v[2],
            R[2][0] * v[0] + R[2][1] * v[1] + R[2][2] * v[2])

IDENT = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
LIGHT = (-0.35, 0.75, 0.56)
_l = math.sqrt(sum(c * c for c in LIGHT))
LIGHT = tuple(c / _l for c in LIGHT)

BOX_FACES = ((4, 5, 6, 7), (0, 3, 2, 1), (1, 2, 6, 5), (0, 4, 7, 3), (3, 7, 6, 2), (0, 1, 5, 4))
BOX_NORMALS = ((0, 0, 1), (0, 0, -1), (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0))
BOX_CORNERS = ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))

HAND_LIFT = 1.15                 # how far the lowest part of a hand rises above the floor at full height
CAM = (0.0, 1.15, 4.3)
PITCH = 0.13
ZERO_PLANE = 4.3                 # distance that sits exactly on the screen; nearer things pop out of it
SIN_P, COS_P = math.sin(PITCH), math.cos(PITCH)

# ---------------------------------------------------------------- the skull, built once as local meshes (head units, y up)
def _loft(rings):
    """rings: lists of 3D points, same length. Returns (verts, faces) with every face wound outward."""
    n = len(rings[0])
    verts = [p for ring in rings for p in ring]
    faces = []
    for r in range(len(rings) - 1):
        for j in range(n):
            a, b = r * n + j, r * n + (j + 1) % n
            faces.append((a, b, b + n, a + n))
    faces.append(tuple(range(n - 1, -1, -1)))
    faces.append(tuple(range((len(rings) - 1) * n, len(rings) * n)))
    cen = [sum(p[k] for p in verts) / len(verts) for k in range(3)]
    out = []
    for f in faces:                                             # wind every face so its normal points away from the centre
        p0, p1, p2 = verts[f[0]], verts[f[1]], verts[f[2]]
        ux, uy, uz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
        vx, vy, vz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
        n_ = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
        fc = [sum(verts[i][k] for i in f) / len(f) for k in range(3)]
        if sum(n_[k] * (fc[k] - cen[k]) for k in range(3)) < 0:
            f = tuple(reversed(f))
        out.append(f)
    return verts, out

def _ring(poly, scale, z, cx=0.0, cy=0.0):
    return [(cx + (x - cx) * scale, cy + (y - cy) * scale, z) for x, y in poly]

def _with_normals(mesh):
    """add each face's normal and centre (local space) so they are not recomputed every frame"""
    verts, faces = mesh
    norms, cens = [], []
    for f in faces:
        p0, p1, p2 = verts[f[0]], verts[f[1]], verts[f[2]]
        ux, uy, uz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
        vx, vy, vz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
        n = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
        ln = math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]) or 1.0
        norms.append((n[0] / ln, n[1] / ln, n[2] / ln))
        k = 1.0 / len(f)
        cens.append((sum(verts[i][0] for i in f) * k, sum(verts[i][1] for i in f) * k, sum(verts[i][2] for i in f) * k))
    return verts, faces, norms, cens

# little trig tables for the round decals and rings
def _circle(n, a=1.0):
    return [math.cos(k * math.pi * a / (n / 2)) for k in range(n)], [math.sin(k * math.pi * a / (n / 2)) for k in range(n)]
COS10, SIN10 = _circle(10)
COS12, SIN12 = _circle(12)
COS8, SIN8 = _circle(8)
RING_C, RING_S = _circle(28)
SH_C, SH_S = _circle(16)
FLOOR_X = [float(i) for i in range(-6, 7, 2)]
FLOOR_ZS = [3.8 - k * 1.2 for k in range(16)]

def _depth(op): return op[0]
def _first(item): return item[0]

SKULL = {}
def build_skull():
    S = 1.1
    cran = [(-0.12, -0.57), (0.12, -0.57), (0.36, -0.46), (0.46, -0.16), (0.40, 0.08),
            (0.28, 0.20), (-0.28, 0.20), (-0.40, 0.08), (-0.46, -0.16), (-0.36, -0.46)]
    cran = [(x * S, -y * S) for x, y in cran]                   # y up
    cc = (0.0, 0.18 * S)
    rings = [_ring(cran, 0.82, 0.31 * S, *cc), _ring(cran, 1.0, 0.12 * S, *cc),
             _ring(cran, 1.0, -0.20 * S, *cc), _ring(cran, 0.72, -0.33 * S, *cc)]
    SKULL["cran"] = _with_normals(_loft(rings))
    jaw = [(-0.31, 0.30), (0.31, 0.30), (0.30, 0.42), (0.17, 0.57), (-0.17, 0.57), (-0.30, 0.42)]
    jaw = [(x * S, -y * S) for x, y in jaw]
    jc = (0.0, -0.42 * -S)
    jc = (0.0, -0.435 * S)
    SKULL["jaw"] = _with_normals(_loft([_ring(jaw, 0.86, 0.25 * S, *jc), _ring(jaw, 1.0, 0.16 * S, *jc), _ring(jaw, 1.0, -0.14 * S, *jc), _ring(jaw, 0.8, -0.24 * S, *jc)]))
    pods = []
    for s in (-1, 1):
        a = [(s * 0.43 * S, 0.14 * S + 0.105 * S * math.cos(k * math.pi / 4), 0.105 * S * math.sin(k * math.pi / 4)) for k in range(8)]
        b = [(s * 0.58 * S, 0.14 * S + 0.105 * S * math.cos(k * math.pi / 4), 0.105 * S * math.sin(k * math.pi / 4)) for k in range(8)]
        pods.append(_with_normals(_loft([a, b])))
    SKULL["pods"] = pods
    SKULL["S"] = S

# ---------------------------------------------------------------- state
def new_hand():
    return {"H": 0.14, "V": 0.0, "hold": 0.0, "squash": 0.0, "flash": 0.0, "power": 0.0}

GRAVITY = 24.0
RISE_K, RISE_C = 70.0, 13.0
JAW_G = 60.0

_S = {"last": None, "beat": 0.0, "hands": [new_hand(), new_hand()], "J": 0.1, "JV": 0.0, "kick": 0.0, "shake": 0.0,
      "flash": 0.0, "shocks": [], "debris": [], "cracks": [], "t": 0.0, "stars": None, "size": None, "phase": 0.0,
      "lens": 0.0, "hue": 0.0, "hy": 1.25, "hv": 0.0, "pk": None, "v3": 0.0, "v4": 0.0, "rng": random.Random(7), "small": None, "big": None, "gtick": 0, "fdt": 0.03, "lod": 0, "turn": 0.0}

def setup(screen, eyesy):
    build_skull()

def hand_pos(h, H):
    """where hand h is in the world at height H: it rises straight up beside the head, and falls down and FORWARD, out of the screen"""
    side = -1 if h == 0 else 1
    return (side * (1.0 - 0.2 * (1.0 - H)), 0.28 + 1.15 * H, 0.9 * H + 1.55 * max(0.0, 1.0 - H) ** 1.3)

def impact(h, power):
    hand = _S["hands"][h]
    hand["hold"] = 0.04 + 0.05 * power                          # a frozen moment on impact: that is what sells the weight
    hand["squash"] = power
    hand["flash"] = 1.0
    hand["power"] = power
    x, _y, z = hand_pos(h, 0.0)
    _S["shake"] = max(_S["shake"], 0.4 + 0.9 * power)
    _S["kick"] = max(_S["kick"], 0.4 + 0.5 * power)
    _S["flash"] = max(_S["flash"], 0.4 * power)
    _S["turn"] = (-1 if h == 0 else 1) * power
    _S["shocks"].append({"x": x, "z": z, "age": 0.0, "power": power})
    rng = _S["rng"]
    for _ in range(7):
        _S["cracks"].append({"x": x, "z": z, "a": rng.uniform(0, 6.283), "len": rng.uniform(0.3, 0.8) * (0.5 + power), "age": 0.0})
    for _ in range(8 + int(16 * power)):
        a = rng.uniform(0, 6.283)
        sp = rng.uniform(0.6, 2.6) * (0.5 + power)
        _S["debris"].append({"p": [x + math.cos(a) * 0.15, 0.1, z + math.sin(a) * 0.15],
                             "v": [math.cos(a) * sp * 0.6, rng.uniform(2.0, 5.0) * (0.5 + power), math.sin(a) * sp * 1.1 + 1.0],
                             "life": rng.uniform(0.7, 1.4), "s": rng.uniform(0.02, 0.045)})
    del _S["cracks"][:-24]
    del _S["debris"][:-70]


# ---------------------------------------------------------------- hand geometry, cached per (side, curl): it only changes when a hand's height does
_HAND_CACHE = {}

def hand_spec(side, curl):
    """the 15 boxes of a hand in hand space: (axis0, axis1, axis2, centre, hx, hy, hz), with curl quantised to 0.01"""
    key = (side, int(curl * 100 + 0.5))
    spec = _HAND_CACHE.get(key)
    if spec is not None:
        return spec
    curl = key[1] / 100.0
    spec = []

    def add(Rl, cl, hx, hy, hz):
        spec.append(((Rl[0][0], Rl[1][0], Rl[2][0]), (Rl[0][1], Rl[1][1], Rl[2][1]), (Rl[0][2], Rl[1][2], Rl[2][2]), cl, hx, hy, hz))

    add(IDENT, (0, 0, 0), 0.115, 0.115, 0.06)                           # palm (no wrist: just the hand)
    fingers = [(-0.075 * side, 0.11, 0.18 * side, 1.0, 0.026), (-0.025 * side, 0.115, 0.05 * side, 1.12, 0.027),
               (0.025 * side, 0.11, -0.08 * side, 1.0, 0.026), (0.075 * side, 0.095, -0.24 * side, 0.8, 0.024)]
    seg_len = (0.11, 0.08, 0.065)
    curls = (1.05, 1.25, 1.0)
    for bx, by, splay, ls, fw in fingers:
        cum = 0.0
        px, py, pz = bx, by, 0.0
        Rs = rot_z(splay)
        for i in range(3):
            cum += curl * curls[i]
            Rl = mm(Rs, rot_x(cum))
            ln = seg_len[i] * ls
            d = mv(Rl, (0, ln, 0))
            add(Rl, (px + d[0] * 0.5, py + d[1] * 0.5, pz + d[2] * 0.5), fw * 0.8 * (1.0 - 0.1 * i), ln * 0.5, fw * 0.8)
            px, py, pz = px + d[0], py + d[1], pz + d[2]
    px, py, pz = -0.12 * side, -0.02, 0.0                               # thumb
    cum = 0.0
    for i in range(2):
        cum += curl * 0.9
        Rl = mm(rot_z(side * (0.95 - 0.5 * curl)), rot_x(cum))
        ln = (0.09, 0.07)[i]
        d = mv(Rl, (0, ln, 0))
        add(Rl, (px + d[0] * 0.5, py + d[1] * 0.5, pz + d[2] * 0.5), 0.03, ln * 0.5, 0.03)
        px, py, pz = px + d[0], py + d[1], pz + d[2]
    _HAND_CACHE[key] = spec
    return spec

# box face f has its normal along axis FACE_AX[f][0] (sign FACE_AX[f][1]); the corners are BOX_FACES[f] of BOX_CORNERS
FACE_AX = ((2, 1), (2, -1), (0, 1), (0, -1), (1, 1), (1, -1))
GLOW = 8                                                         # the glow is drawn 1/8 size and scaled up (it is blurry anyway)

# ---------------------------------------------------------------- draw
def draw(screen, eyesy):
    if not SKULL:
        build_skull()
    xres, yres = eyesy.xres, eyesy.yres
    now = time.time()
    if _S["last"] is None:
        _S["last"] = now
    dt = min(max(now - _S["last"], 1e-3), 0.1)
    _S["last"] = now
    _S["t"] += dt
    t = _S["t"]

    # slow frames (a Pi) drop to a cheaper look: no glow pass, no outlines on the small parts, a coarser floor grid
    _S["fdt"] += (dt - _S["fdt"]) * 0.1
    if _S["lod"] == 0 and _S["fdt"] > 0.055:
        _S["lod"] = 1
    elif _S["lod"] == 1 and _S["fdt"] < 0.03:
        _S["lod"] = 0
    lod = _S["lod"]

    if getattr(eyesy, "trig", False):
        _S["beat"] = 1.0
    _S["beat"] *= math.exp(-dt * 6.0)
    beat = _S["beat"]
    try:
        level = clamp(max(abs(v) for v in eyesy.audio_in[:100]) / 30000.0)
    except Exception:
        level = 0.0
    for k, r in (("kick", 7.0), ("shake", 6.0), ("flash", 5.0), ("turn", 2.5)):
        _S[k] *= math.exp(-dt * r)

    # ---- hand physics: knob = the height the hand is held at; the hand itself has weight ----
    knobs = (eyesy.knob1, eyesy.knob2)
    for h, hand in enumerate(_S["hands"]):
        hand["flash"] *= math.exp(-dt * 4.0)
        hand["squash"] *= math.exp(-dt * 8.0)
        if hand["hold"] > 0.0:
            hand["hold"] -= dt
            continue
        target = clamp((knobs[h] - 0.1) * 1.4, 0.0, 1.1)
        floor_hit = knobs[h] <= 0.1
        steps = 6
        ds = dt / steps
        H, V = hand["H"], hand["V"]
        for _ in range(steps):
            if H > target + 0.004:
                V = max(V - GRAVITY * ds, -9.0)                 # let go: it falls
            else:
                V += (RISE_K * (target - H) - RISE_C * V) * ds
            H += V * ds
            if H <= target and V < 0.0:                         # arrived while falling
                H = target
                if floor_hit and V < -0.9:
                    impact(h, clamp(-V / 6.0, 0.18, 1.0))
                    V = 0.0
                    break
                V = -V * 0.2
        hand["H"], hand["V"] = H, V

    # ---- head: the knob sets how open the jaw is; the jaw itself is heavy and snaps shut ----
    pk = _S["pk"]
    for key, name in (("v3", "knob3"), ("v4", "knob4")):
        raw = 0.0 if pk is None else (getattr(eyesy, name) - pk[name]) / dt
        _S[key] += (raw - _S[key]) * min(1.0, dt * 15.0)
    _S["pk"] = {"knob3": eyesy.knob3, "knob4": eyesy.knob4}
    tj = clamp((eyesy.knob4 - 0.1) * 1.3)
    gnash = 0.2 * (0.5 + 0.5 * math.sin(t * 40.0)) * clamp(abs(_S["v4"]) * 2.0)      # wiggle the knob fast: the teeth chatter
    tj_eff = max(tj + gnash, level * 0.55, beat * 0.30)
    J, JV = _S["J"], _S["JV"]
    for _ in range(4):
        ds = dt / 4
        if J > tj_eff + 0.003:
            JV = max(JV - JAW_G * ds, -9.0)
        else:
            JV += (260.0 * (tj_eff - J) - 24.0 * JV) * ds
        J += JV * ds
        if J <= tj_eff and JV < 0.0:
            J = tj_eff
            if JV < -1.8 and tj_eff < 0.2:                      # CHOMP
                p = clamp(-JV / 7.0, 0.25, 1.0)
                _S["kick"] = max(_S["kick"], 0.5 + 0.5 * p)
                _S["shake"] = max(_S["shake"], 0.3 + 0.5 * p)
                _S["flash"] = max(_S["flash"], 0.6 * p)
                _S["lens"] = max(_S["lens"], p)
            JV = -JV * 0.15
    J = clamp(J, 0.0, 1.05)
    _S["J"], _S["JV"] = J, JV
    _S["lens"] *= math.exp(-dt * 4.0)
    kick, flash, shake = _S["kick"], _S["flash"], _S["shake"]

    # ---- colors ----
    fg = eyesy.color_picker(eyesy.knob5)
    h0 = colorsys.rgb_to_hsv(fg[0] / 255.0, fg[1] / 255.0, fg[2] / 255.0)[0]
    _S["hue"] = (_S["hue"] + dt * 0.035) % 1.0                  # the stage slowly cycles through every color (about 30 s)
    hst = _S["hue"]
    stage = hsv(hst, 0.9, 0.9)
    accent = hsv(hst, 0.85, 1.0)

    # ---- camera ----
    F = yres * 1.25
    cxs, cys = xres / 2.0, yres / 2.0
    camx = CAM[0] + math.sin(t * 61.0) * shake * 0.035
    camy = CAM[1] + math.cos(t * 53.0) * shake * 0.035
    camz = CAM[2]

    def chrome_color(n, hue, hot=0.0):
        d = n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2]
        d = d if d > 0.0 else 0.0
        spec = d ** 14
        env = 0.5 + 0.5 * n[1]
        return hsv(hue - 0.32 * env + 0.07 * n[0], 0.88 - 0.7 * spec, clamp(0.24 + 0.66 * d + 0.6 * spec + 0.28 * hot))

    def P2(x, y, z):
        """world point -> screen (x, y)"""
        dx, dy, dz = x - camx, y - camy, z - camz
        dep = -dy * SIN_P - dz * COS_P
        if dep < 0.15: dep = 0.15
        k = F / dep
        return (cxs + k * dx, cys - k * (dy * COS_P - dz * SIN_P))

    def emit_box(ops, c, A, N, colfn, edge):
        """queue the camera-facing faces of an oriented box. c: centre, A: its 3 half-extent vectors, N: the 3 unit axes.
        Faces turned away are skipped before anything is lit or projected."""
        cx_, cy_, cz_ = c
        A0, A1, A2 = A
        pc = None
        for fi in range(6):
            k, sg = FACE_AX[fi]
            a, n = A[k], N[k]
            fx, fy, fz = cx_ + sg * a[0], cy_ + sg * a[1], cz_ + sg * a[2]
            nx, ny, nz = sg * n[0], sg * n[1], sg * n[2]
            if nx * (camx - fx) + ny * (camy - fy) + nz * (camz - fz) <= 0.0:
                continue
            if pc is None:
                pc = [None] * 8
            poly = []
            for ci in BOX_FACES[fi]:
                p = pc[ci]
                if p is None:
                    sx, sy, sz = BOX_CORNERS[ci]
                    p = pc[ci] = P2(cx_ + sx * A0[0] + sy * A1[0] + sz * A2[0],
                                    cy_ + sx * A0[1] + sy * A1[1] + sz * A2[1],
                                    cz_ + sx * A0[2] + sy * A1[2] + sz * A2[2])
                poly.append(p)
            ops.append((-(fy - camy) * SIN_P - (fz - camz) * COS_P, poly, colfn((nx, ny, nz)), edge))

    # ============================== build the draw lists (world space, once) ==============================
    groups = []                                                  # each: (ops, sort)
    def new_group(sort=True):
        ops = []
        groups.append((ops, sort))
        return ops

    # ---- skull ----
    S = SKULL["S"]
    yaw = 0.16 * math.sin(t * 0.55) + _S["turn"] * 0.22
    hy, hv = _S["hy"], _S["hv"]                                   # knob3 sets the height; the head is heavy, so it lags and overshoots
    target_y = 0.9 + eyesy.knob3 * 0.8
    for _ in range(4):
        hv += (90.0 * (target_y - hy) - 11.0 * hv) * (dt / 4)
        hy += hv * (dt / 4)
    _S["hy"], _S["hv"] = hy, hv
    nod = kick * 0.09 + 0.02 * math.sin(t * 0.8) + clamp(hv * 0.07, -0.35, 0.35)     # nods as it rises and falls
    Rh = mm(rot_x(nod), rot_y(yaw))
    Th = (0.0, hy + math.sin(t * 1.3) * 0.03 - kick * 0.05, -0.15)
    jaw_dy = -J * 0.2 * S
    (r00, r01, r02), (r10, r11, r12), (r20, r21, r22) = Rh
    tx_, ty_, tz_ = Th
    Nh = (tuple(r[0] for r in Rh), tuple(r[1] for r in Rh), tuple(r[2] for r in Rh))   # head axes in world space

    def hw(x, y, z):                                              # a point in head units -> world
        x *= S; y *= S; z *= S
        return (r00 * x + r01 * y + r02 * z + tx_, r10 * x + r11 * y + r12 * z + ty_, r20 * x + r21 * y + r22 * z + tz_)

    def hproj(x, y, z):
        return P2(*hw(x, y, z))

    def emit_mesh(ops, mesh, hue, hot, dy=0.0):
        verts, faces, norms, cens = mesh
        pv = [None] * len(verts)
        edge = hsv(hue, 0.5, 0.45 + 0.4 * hot)
        for f, ln, lc in zip(faces, norms, cens):
            cx_, cy_, cz_ = lc[0], lc[1] + dy, lc[2]
            cen = (r00 * cx_ + r01 * cy_ + r02 * cz_ + tx_, r10 * cx_ + r11 * cy_ + r12 * cz_ + ty_, r20 * cx_ + r21 * cy_ + r22 * cz_ + tz_)
            n = (r00 * ln[0] + r01 * ln[1] + r02 * ln[2], r10 * ln[0] + r11 * ln[1] + r12 * ln[2], r20 * ln[0] + r21 * ln[1] + r22 * ln[2])
            if n[0] * (camx - cen[0]) + n[1] * (camy - cen[1]) + n[2] * (camz - cen[2]) <= 0.0:
                continue
            poly = []
            for i in f:
                p = pv[i]
                if p is None:
                    x, y, z = verts[i]
                    y += dy
                    p = pv[i] = P2(r00 * x + r01 * y + r02 * z + tx_, r10 * x + r11 * y + r12 * z + ty_, r20 * x + r21 * y + r22 * z + tz_)
                poly.append(p)
            ops.append((-(cen[1] - camy) * SIN_P - (cen[2] - camz) * COS_P, poly, chrome_color(n, hue, hot), edge))

    def emit_decal(ops, lpts, color, edge, hint):
        """a flat polygon on the head, lpts in head units; hint is the head-space direction it faces"""
        p0 = hw(*lpts[0])
        n = (r00 * hint[0] + r01 * hint[1] + r02 * hint[2], r10 * hint[0] + r11 * hint[1] + r12 * hint[2], r20 * hint[0] + r21 * hint[1] + r22 * hint[2])
        if n[0] * (camx - p0[0]) + n[1] * (camy - p0[1]) + n[2] * (camz - p0[2]) <= 0.0:
            return
        ops.append((0.0, [hproj(x, y, z) for x, y, z in lpts], color, edge))

    tooth_edge = None if lod else (40, 30, 60)
    def tooth_color(n):
        return hsv(h0, 0.1, 0.45 + 0.5 * max(0.0, n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2]))

    def teeth(ops, yc, zc):
        A = (tuple(c * 0.025 * S for c in Nh[0]), tuple(c * 0.036 * S for c in Nh[1]), tuple(c * 0.03 * S for c in Nh[2]))
        for i in range(7):
            c = hw(-0.21 + i * 0.06 + 0.025, yc, zc)
            emit_box(ops, c, A, Nh, tooth_color, tooth_edge)

    ops = new_group()                                             # pods
    for s in range(2):
        emit_mesh(ops, SKULL["pods"][s], h0, kick)
    ops = new_group(False)                                        # pod faces
    for s in (-1, 1):
        emit_decal(ops, [(s * 0.585, 0.14 + 0.085 * COS10[k], 0.085 * SIN10[k]) for k in range(10)],
                   chrome_color((s, 0, 0), h0 - 0.1, kick), hsv(h0, 0.6, 0.8), (s, 0, 0))
        emit_decal(ops, [(s * 0.595, 0.14 + 0.045 * COS10[k], 0.045 * SIN10[k]) for k in range(10)],
                   hsv(hst, 0.4, 1.0), hsv(hst, 0.9, 1.0), (s, 0, 0))
    ops = new_group(False)                                        # mouth cavity
    mouth_b = -0.30 - J * 0.2
    emit_decal(ops, [(-0.27, -0.12, 0.10), (0.27, -0.12, 0.10), (0.27, mouth_b, 0.10), (-0.27, mouth_b, 0.10)],
               (8, 0, 18), hsv(hst, 0.9, 0.25 + 0.3 * J), (0, 0, 1))
    ops = new_group()                                             # lower jaw
    emit_mesh(ops, SKULL["jaw"], h0, kick, jaw_dy)
    ops = new_group()                                             # lower teeth ride on the jaw
    teeth(ops, -0.27 - J * 0.2, 0.2)
    ops = new_group()                                             # cranium
    emit_mesh(ops, SKULL["cran"], h0, kick)
    ops = new_group()                                             # upper teeth
    teeth(ops, -0.232, 0.17)
    ops = new_group(False)                                        # decals on the front: visor and the lens
    zf = 0.312
    vis = [(-0.29, 0.40), (0.29, 0.40), (0.35, 0.22), (0.29, 0.06), (0.11, -0.06), (-0.11, -0.06), (-0.29, 0.06), (-0.35, 0.22)]
    emit_decal(ops, [(x, y, zf) for x, y in vis], (5, 0, 12), hsv(hst, 0.8, 1.0), (0, 0, 1))
    flare = clamp(kick + _S["lens"] * 0.6 + level * 0.8)
    for r, z_, col in ((0.175, 0.318, hsv(h0, 0.8, 0.18)), (0.15, 0.326, hsv(h0 - 0.1, 0.5, 0.85)), (0.115, 0.334, hsv(h0, 0.85, 0.2)),
                       (0.088, 0.342, hsv(h0 - 0.25, 0.4, 0.95)), (0.055 + 0.02 * flare, 0.350, hsv(hst, 0.8, 1.0)),
                       (0.026 + 0.015 * flare, 0.358, hsv(hst, 0.1, 1.0))):
        emit_decal(ops, [(r * COS12[k], 0.20 + r * SIN12[k], z_) for k in range(12)], col, hsv(h0, 0.4, 0.9) if r > 0.1 else col, (0, 0, 1))
    for s in (-1, 1):
        emit_decal(ops, [(s * 0.26 + 0.02 * COS8[k], 0.20 + 0.02 * SIN8[k], 0.318) for k in range(8)], hsv(hst, 0.4, 1.0), hsv(hst, 0.9, 1.0), (0, 0, 1))
    skull_groups = groups[:]
    del groups[:]

    # ---- hands ----
    hand_groups = []
    for h, hand in enumerate(_S["hands"]):
        side = -1 if h == 0 else 1
        H = hand["H"]
        T = hand_pos(h, H)
        curl = 0.35 + 0.65 * clamp(1.0 - H * 2.2)                       # always a clenched claw at least; a tight fist at the floor
        # The hand points AT THE VIEWER, knuckles first, like a punch thrown at the camera: its length runs toward us,
        # the pinky side is down, the thumb side is up and the palm faces in toward the skull. So we see knuckles, not palm.
        # Raised, the fingers tip a little up; slamming, they level out and lean into the floor.
        lean = -0.4 * (1.0 - curl) / 0.65 + 0.15 + clamp(-hand["V"] * 0.03, 0.0, 0.2)
        Rf = ((0, 0, -side), (-side, 0, 0), (0, 1, 0))
        sq = hand["squash"]
        Rb = mm(rot_x(lean), Rf)
        hot = hand["flash"]
        hue = h0 + 0.03 * side
        HS = 1.8
        sc = (1.0 + 0.18 * sq) * HS
        sy_ = 1.0 - 0.15 * sq
        edge = None if lod else hsv(hue, 0.5, 0.45 + 0.4 * hot)

        boxes = []
        lowest = 1e9
        zsum = 0.0
        for c0, c1, c2, cl, hx, hy_, hz in hand_spec(side, curl):
            n0, n1, n2 = mv(Rb, c0), mv(Rb, c1), mv(Rb, c2)
            cw = mv(Rb, cl)
            k0, k1, k2 = hx * sc, hy_ * sy_, hz * sc
            A = ((n0[0] * k0, n0[1] * k0, n0[2] * k0), (n1[0] * k1, n1[1] * k1, n1[2] * k1), (n2[0] * k2, n2[1] * k2, n2[2] * k2))
            cy_ = cw[1] * sy_ * HS
            cz_ = cw[2] * sc + T[2]
            low = cy_ - (abs(A[0][1]) + abs(A[1][1]) + abs(A[2][1]))
            if low < lowest:
                lowest = low
            zsum += cz_
            boxes.append(((cw[0] * sc + T[0], cy_, cz_), A, (n0, n1, n2)))
        dy = HAND_LIFT * H - lowest                                     # rest the LOWEST point of the fist on the floor at H = 0
        ops = []
        colfn = lambda n, hue=hue, hot=hot: chrome_color(n, hue, hot)
        for c, A, N in boxes:
            emit_box(ops, (c[0], c[1] + dy, c[2]), A, N, colfn, edge)
        ops.sort(key=_depth, reverse=True)
        hand_groups.append((zsum / len(boxes), ops))
    hand_groups.sort(key=_first, reverse=False)                         # far hand (smaller z) first

    for ops, srt in skull_groups:
        if srt:
            ops.sort(key=_depth, reverse=True)

    # ============================== the stage and the floor ==============================
    phase = _S["phase"] = (_S["phase"] + dt * (0.18 + 0.6 * level + 1.0 * beat + 0.9 * kick)) % 1.0
    ZSP = 2.2
    live = []
    for sh in _S["shocks"]:
        sh["age"] += dt
        if sh["age"] < 1.6:
            live.append(sh)
    _S["shocks"] = live

    def ripple(x, z):
        y = 0.0
        for sh in live:
            d = math.hypot(x - sh["x"], z - sh["z"])
            r = sh["age"] * 3.0
            y += 0.34 * sh["power"] * math.exp(-sh["age"] * 2.0) * math.exp(-((d - r) / 0.55) ** 2)
        return y

    floor_x = FLOOR_X
    floor_zs = FLOOR_ZS
    off = phase * 1.2
    xz = [3.8 - k * 1.2 - off for k in range(15)]
    xz = [zz for zz in xz if zz < 3.8]

    cracks = []
    for c in _S["cracks"]:
        c["age"] += dt
        if c["age"] < 2.0:
            cracks.append(c)
    _S["cracks"] = cracks

    debris = []
    for d in _S["debris"]:
        d["life"] -= dt
        if d["life"] <= 0:
            continue
        d["v"][1] -= 12.0 * dt
        for k in range(3):
            d["p"][k] += d["v"][k] * dt
        if d["p"][1] < 0.03:
            d["p"][1] = 0.03
            d["v"][1] = -d["v"][1] * 0.4
        debris.append(d)
    _S["debris"] = debris

    gs = GLOW
    if _S["size"] != (xres, yres):
        _S["size"] = (xres, yres)
        _S["small"] = pygame.Surface((xres // gs + 2, yres // gs + 2))
        _S["big"] = None
        rng = random.Random(3)
        _S["stars"] = [(int(rng.random() * xres), int(rng.random() * yres * 0.5), rng.random() * 6.28) for _ in range(60)]
    small = _S["small"]
    _S["gtick"] += 1
    glow = lod == 0 and (_S["gtick"] & 1 == 0 or _S["big"] is None)     # glow is rebuilt every other frame and re-used in between
    if glow:
        small.fill((0, 0, 0))
    floor_col = hsv(hst, 0.8, 0.07 + 0.06 * flash)
    gk = 1.0 / gs

    def scaled(c, k):
        return (int(c[0] * k), int(c[1] * k), int(c[2] * k))

    def proj(p):
        dx, dy, dz = p[0] - camx, p[1] - camy, p[2] - camz
        dep = -dy * SIN_P - dz * COS_P
        if dep < 0.15: dep = 0.15
        return (cxs + F * dx / dep, cys - F * (dy * COS_P - dz * SIN_P) / dep, dep)

    line_ = pygame.draw.line
    poly_ = pygame.draw.polygon

    def line(a, b, col, w=1):
        line_(screen, col, (a[0], a[1]), (b[0], b[1]), w)

    def draw_ops(ops):
        for _d, poly, col, edge in ops:
            poly_(screen, col, poly)
            if edge is not None:
                poly_(screen, edge, poly, 1)

    # ---- the window: everything inside it is the "screen"; the thick black border around it is the false frame ----
    wx, wy = int(xres * 0.07), int(yres * 0.05)
    win = pygame.Rect(wx, wy, xres - 2 * wx, int(yres * 0.77))
    screen.fill((7, 6, 10))
    screen.set_clip(win)
    screen.fill((0, 0, 0), win)
    for sx, sy, ph in _S["stars"]:
        b = int(80 + 80 * math.sin(t * 2 + ph))
        screen.set_at((sx, sy), (b, b, b))
    corners = [proj(p) for p in ((-16, 0, 4.0), (16, 0, 4.0), (16, 0, -18), (-16, 0, -18))]
    poly_(screen, floor_col, [(c[0], c[1]) for c in corners])
    for k in range(10):                                          # truss frames rushing toward the camera
        z = 3.0 - (k + phase) * ZSP
        pts = [proj(p) for p in ((-4.6, 0, z), (4.6, 0, z), (4.6, 4.9, z), (-4.6, 4.9, z))]
        dep = pts[0][2]
        fade = clamp(1.25 - dep / 22.0)
        col = scaled(stage, fade)
        poly = [(p[0], p[1]) for p in pts]
        poly_(screen, col, poly, 2 if dep < 14 else 1)
        if glow and dep < 16:
            poly_(small, scaled(stage, fade * 0.25), [(x * gk, y * gk) for x, y in poly], 1)
        if k % 2 == 0:                                           # LED strips on the walls
            for xs in (-4.6, 4.6):
                a, b = proj((xs, 0.0, z)), proj((xs, 4.9, z))
                line(a, b, col, max(2, int(F * 0.04 / max(a[2], 0.5))))
    for xs in (-4.6, 4.6):                                       # rails along the walls and ceiling
        for ys in (0.0, 4.9):
            line(proj((xs, ys, 3.5)), proj((xs, ys, -22.0)), stage)
    if not live:                                                 # floor grid, flat: every row has one depth, so it is all straight lines
        rows = []
        for z in floor_zs:
            dep = max(0.15, camy * SIN_P - (z - camz) * COS_P)
            rows.append((F / dep, cys - F * (-camy * COS_P - (z - camz) * SIN_P) / dep, dep))
        step = 4 if lod else 2
        for r in range(0, len(rows) - 1, step):
            ka, sa, da = rows[r]
            kb, sb, _db = rows[min(r + step, len(rows) - 1)]
            col = scaled(stage, clamp(1.1 - da / 20.0) * 0.8)
            for x in floor_x:
                line_(screen, col, (cxs + ka * (x - camx), sa), (cxs + kb * (x - camx), sb), 1)
        for zz in (xz[::2] if lod else xz):
            dep = max(0.15, camy * SIN_P - (zz - camz) * COS_P)
            k = F / dep
            sy = cys - F * (-camy * COS_P - (zz - camz) * SIN_P) / dep
            line_(screen, scaled(stage, clamp(1.1 - dep / 20.0) * 0.8), (cxs + k * (-6.0 - camx), sy), (cxs + k * (6.0 - camx), sy), 1)
    else:                                                        # rippling where fists landed
        zlines = [[(x, ripple(x, z), z) for z in floor_zs] for x in floor_x]
        xlines = [[(x, ripple(x, zz), zz) for x in floor_x] for zz in xz]
        for ln_ in zlines + xlines:
            pv = [proj(p) for p in ln_]
            for a, b in zip(pv, pv[1:]):
                line(a, b, scaled(stage, clamp(1.1 - a[2] / 20.0) * 0.8))
    for c in cracks:                                             # cracks in the floor
        fade = clamp(1.0 - c["age"] / 2.0)
        prev = (c["x"], 0.01, c["z"])
        a = c["a"]
        ln = c["len"] * min(1.0, c["age"] * 12.0)
        ccol = (int(255 * fade), int(235 * fade), int(250 * fade))
        gcol = (int(96 * fade), int(72 * fade), int(108 * fade))
        for i in range(1, 7):
            a += math.sin(i * 12.9 + c["a"] * 5) * 0.5
            nxt = (prev[0] + math.cos(a) * ln / 6, 0.01, prev[2] + math.sin(a) * ln / 6)
            p0, p1 = proj(prev), proj(nxt)
            line(p0, p1, ccol, 2)
            if glow:
                line_(small, gcol, (p0[0] * gk, p0[1] * gk), (p1[0] * gk, p1[1] * gk), 1)
            prev = nxt
    for sh in live:                                              # shock rings spreading over the floor
        r = 0.15 + sh["age"] * 3.0
        fade = clamp(1.0 - sh["age"] / 1.6)
        ring = [proj((sh["x"] + RING_C[k] * r, 0.02, sh["z"] + RING_S[k] * r * 0.9)) for k in range(28)]
        poly = [(p[0], p[1]) for p in ring]
        poly_(screen, scaled(accent, fade), poly, 3)
        if glow:
            poly_(small, scaled(accent, fade * 0.85), [(x * gk, y * gk) for x, y in poly], 1)
    for h in range(2):                                           # contact shadow under each fist: the closer, the tighter and darker
        H = _S["hands"][h]["H"]
        x, _y, z = hand_pos(h, H)
        r = 0.26 + 0.30 * clamp(H * 1.4)
        pts = [P2(x + SH_C[k] * r * 1.3, 0.015, z + SH_S[k] * r) for k in range(16)]
        poly_(screen, scaled(floor_col, 0.05 + 0.5 * clamp(H * 1.4)), pts)
    for ops, _srt in skull_groups:
        draw_ops(ops)
    if glow:
        sw, sh_ = small.get_size()
        gx0, gy0 = wx // gs, wy // gs
        sub = small.subsurface(pygame.Rect(gx0, gy0, min(win.w // gs + 2, sw - gx0), min(win.h // gs + 2, sh_ - gy0)))
        _S["big"] = pygame.transform.smoothscale(sub, (sub.get_width() * gs, sub.get_height() * gs))
    elif lod:
        _S["big"] = None
    if _S["big"] is not None:
        screen.blit(_S["big"], (wx // gs * gs, wy // gs * gs), special_flags=pygame.BLEND_RGB_ADD)
    if flash > 0.05:                                             # whole-window flash on a hard hit
        screen.fill((int(40 * flash), int(40 * flash), int(46 * flash)), special_flags=pygame.BLEND_RGB_ADD)
    screen.set_clip(None)
    pygame.draw.rect(screen, scaled(stage, 0.5), win.inflate(4, 4), 2)      # the visible edge of the false frame

    # ---- in front of the frame: the fists and debris are drawn OVER the border, so they break out of the screen ----
    for _z, ops in hand_groups:
        draw_ops(ops)
    for d in debris:
        p = proj(d["p"])
        sz = max(2, min(26, int(F * d["s"] / p[2])))
        col = hsv(h0 - 0.2, 0.3, clamp(d["life"] * 1.2))
        pygame.draw.rect(screen, col, (int(p[0] - sz / 2), int(p[1] - sz / 2), sz, sz))
