# Dancing alien, in 3D: an original green alien built from shaded meshes (ellipsoids and capsules)
# that sways, steps and strikes poses. It sits on a turntable, so you can spin it around its feet.
# No background is drawn; the screen is just whatever the bg color is.
#
# Knob convention (same in every mode):
#   knob1 = size
#   knob2 = rotation         (turntable spin around the alien's feet, a full 360 degrees)
#   knob3 = animation speed  (the male alien's dance tempo)
#   knob4 = foreground color (the alien's skin)
#   knob5 = the ladies' twerk speed (this mode has no background scene, so this knob is free)
import math
import time
import pygame

# ---- adaptive quality: if this pattern runs slowly (say, on a Raspberry Pi) it quietly draws less detail ----
_lod = {"q": 1.0, "avg": 0.0, "t0": 0.0}
LOD_BUDGET = 0.016                                             # seconds of drawing per frame to stay under
_ds = 1.0                                                      # mesh detail scale, set from the quality every frame

def lod_start():
    _lod["t0"] = time.perf_counter()

def lod_end():
    dt = time.perf_counter() - _lod["t0"]
    _lod["avg"] = _lod["avg"] * 0.9 + dt * 0.1 if _lod["avg"] else dt
    if _lod["avg"] > LOD_BUDGET:
        _lod["q"] = max(0.2, _lod["q"] - 0.04)
    elif _lod["avg"] < LOD_BUDGET * 0.55:
        _lod["q"] = min(1.0, _lod["q"] + 0.01)

# ============================== small vector helpers ==============================

def add(a, b): return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def mul(a, s): return (a[0]*s, a[1]*s, a[2]*s)
def dot(a, b): return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def length(v): return math.sqrt(dot(v, v))
def norm(v):
    l = length(v) or 1.0
    return (v[0]/l, v[1]/l, v[2]/l)
def lerp(a, b, t): return a + (b - a) * t
def lerp3(a, b, t): return (a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t, a[2]+(b[2]-a[2])*t)
def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))

# ============================== mesh builders ==============================
# a mesh is (vertices, vertex normals, faces, face brightness multipliers)

_TRIG = {}
_FACES_E = {}
_FACES_C = {}
_ONES = {}

def _trig(n):
    t = _TRIG.get(n)
    if t is None:
        t = ([math.cos(2 * math.pi * k / n) for k in range(n)], [math.sin(2 * math.pi * k / n) for k in range(n)])
        _TRIG[n] = t
    return t

def _ones(n):
    o = _ONES.get(n)
    if o is None:
        o = _ONES[n] = [1.0] * n
    return o

def ellipsoid(center, right, up, fwd, rx, ry, rz, lat=9, lon=14, squash=0.0, stripe=None):
    lat = max(4, int(lat * _ds + 0.5))
    lon = max(6, int(lon * _ds + 0.5))
    cth, sth = _trig(lon)
    cx_, cy_, cz_ = center
    r0, r1, r2 = right
    u0, u1, u2 = up
    f0, f1, f2 = fwd
    irx2, iry2, irz2 = 1.0 / (rx * rx), 1.0 / (ry * ry), 1.0 / (rz * rz)
    sqrt, pi = math.sqrt, math.pi
    verts, norms = [], []
    va, na = verts.append, norms.append
    for i in range(lat + 1):
        phi = pi * i / lat
        y = ry * math.cos(phi)
        ring = math.sin(phi)
        s = 1.0 - squash * (1.0 - y / ry) / 2.0            # egg shape: narrower toward the chin
        for j in range(lon):
            x, z = rx * ring * cth[j] * s, rz * ring * sth[j] * s
            nx, ny, nz = x * irx2, y * iry2, z * irz2
            l = sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            nx /= l; ny /= l; nz /= l
            va((cx_ + r0 * x + u0 * y + f0 * z, cy_ + r1 * x + u1 * y + f1 * z, cz_ + r2 * x + u2 * y + f2 * z))
            na((r0 * nx + u0 * ny + f0 * nz, r1 * nx + u1 * ny + f1 * nz, r2 * nx + u2 * ny + f2 * nz))
    faces = _FACES_E.get((lat, lon))
    if faces is None:
        faces = _FACES_E[(lat, lon)] = [(i * lon + j, i * lon + (j + 1) % lon, (i + 1) * lon + (j + 1) % lon, (i + 1) * lon + j)
                                        for i in range(lat) for j in range(lon)]
    if stripe and lat >= 8:
        mult = [stripe(i, j) for i in range(lat) for j in range(lon)]
    else:
        mult = _ones(len(faces))
    return verts, norms, faces, mult

_CAPS = {3: [(1.0, 0.0), (math.sin(math.radians(55)), math.cos(math.radians(55))), (math.sin(math.radians(25)), math.cos(math.radians(25)))],
         2: [(1.0, 0.0), (math.sin(math.radians(40)), math.cos(math.radians(40)))],
         1: [(1.0, 0.0)]}

def capsule(p0, p1, r0, r1, sides=8):
    sides = max(4, int(sides * _ds + 0.5))
    ca_, sa_ = _trig(sides)
    x0, y0, z0 = p0
    x1, y1, z1 = p1
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    L = math.sqrt(dx * dx + dy * dy + dz * dz) or 1e-6
    dx /= L; dy /= L; dz /= L
    if abs(dz) < 0.9:                                          # any axis that is not parallel to the limb
        ux, uy, uz = dy, -dx, 0.0
    else:
        ux, uy, uz = 0.0, dz, -dy
    ul = math.sqrt(ux * ux + uy * uy + uz * uz) or 1.0
    ux /= ul; uy /= ul; uz /= ul
    vx, vy, vz = dy * uz - dz * uy, dz * ux - dx * uz, dx * uy - dy * ux
    caps = _CAPS[3 if _ds > 0.85 else (2 if _ds > 0.65 else 1)]
    rings = []                                                 # (centre, radius, sphere centre used for the normals)
    for sn, cs in caps:
        rings.append((x0 - dx * r0 * sn, y0 - dy * r0 * sn, z0 - dz * r0 * sn, r0 * cs, x0, y0, z0, r0))
    rings.append((x0, y0, z0, r0, x0, y0, z0, r0))
    rings.append((x1, y1, z1, r1, x1, y1, z1, r1))
    for sn, cs in reversed(caps):
        rings.append((x1 + dx * r1 * sn, y1 + dy * r1 * sn, z1 + dz * r1 * sn, r1 * cs, x1, y1, z1, r1))
    verts, norms = [], []
    va, na = verts.append, norms.append
    for cx_, cy_, cz_, r, nx_, ny_, nz_, rs in rings:
        inv = 1.0 / (rs if rs > 1e-6 else 1e-6)
        for k in range(sides):
            ox = (ux * ca_[k] + vx * sa_[k]) * r
            oy = (uy * ca_[k] + vy * sa_[k]) * r
            oz = (uz * ca_[k] + vz * sa_[k]) * r
            px, py, pz = cx_ + ox, cy_ + oy, cz_ + oz
            va((px, py, pz))
            na(((px - nx_) * inv, (py - ny_) * inv, (pz - nz_) * inv))
    nr = len(rings)
    faces = _FACES_C.get((nr, sides))
    if faces is None:
        faces = _FACES_C[(nr, sides)] = [(i * sides + k, i * sides + (k + 1) % sides, (i + 1) * sides + (k + 1) % sides, (i + 1) * sides + k)
                                         for i in range(nr - 1) for k in range(sides)]
    return verts, norms, faces, _ones(len(faces))

def ik3(root, target, l1, l2, pole):
    """two-bone solver in 3D: returns (mid joint, end point); the mid joint bends toward `pole`"""
    d = sub(target, root)
    dist = length(d)
    reach = l1 + l2 - 1e-3
    if dist > reach:
        d = mul(d, reach / dist)
        dist = reach
        target = add(root, d)
    dist = max(dist, 0.3)
    e = mul(d, 1.0 / (length(d) or 1.0))
    a = math.acos(clamp((l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist), -1, 1))
    q = sub(pole, mul(e, dot(pole, e)))
    q = norm(q) if length(q) > 1e-6 else (0.0, 1.0, 0.0)
    mid = add(root, add(mul(e, l1 * math.cos(a)), mul(q, l1 * math.sin(a))))
    return mid, target

# ============================== dance ==============================

L_THIGH, L_SHIN = 2.0, 2.05
L_UPPER, L_FORE = 1.45, 1.5
FLOOR = -3.75

# arm poses: wrist target relative to the shoulder (x is outward) and the direction the elbow points
POSES = {
    "HIP_OUT":   ((0.55, -2.15, 0.15), (1.0, -0.1, -0.9)),    # hand on the hip, elbow flared back and out
    "HIP_BACK":  ((0.95, -2.30, -0.35), (0.9, 0.2, -1.0)),    # hand on the hip, elbow pulled well back
    "CHIN":      ((-0.25, 0.65, 0.70), (0.3, -1.0, -0.1)),    # hand up at the chin
    "CHEST":     ((-0.30, -1.15, 0.65), (0.3, -1.0, 0.2)),    # hand resting on the belly
    "HANG":      ((0.35, -2.75, 0.10), (0.6, -0.5, -0.7)),    # arm hanging, elbow tucked in
    "OUT_LOW":   ((2.15, -1.95, 0.10), (0.0, -0.7, -0.8)),    # arm out to the side and down, elbow bent
    "OUT_HORIZ": ((2.65, -0.95, 0.05), (0.0, -1.0, -0.4)),    # arm out to the side
    "OUT_DOWN":  ((1.55, -2.55, 0.05), (0.3, -0.8, -0.5)),    # arm out on a diagonal
    "BENT_OUT":  ((1.35, -1.85, 0.10), (0.6, -0.6, -0.8)),    # elbow out, hand near the hip
}

# The dance, read off the reference loop (54 frames, one key every 3 frames).
# Arms: the alien's left arm (screen right) cycles hip / belly / chin; the right arm (screen left)
# is held out low, comes up to horizontal twice, and swings out on a diagonal mid-loop.
ARM_L = [(0, "HIP_OUT"), (3, "CHEST"), (6, "CHIN"), (9, "CHEST"), (12, "HIP_BACK"), (15, "HIP_OUT"), (18, "HIP_OUT"),
         (21, "HANG"), (24, "HANG"), (27, "HANG"), (30, "HANG"), (33, "OUT_DOWN"), (36, "HIP_OUT"), (39, "HIP_OUT"),
         (42, "HIP_BACK"), (45, "HIP_OUT"), (48, "CHIN"), (51, "CHEST")]
ARM_R = [(0, "BENT_OUT"), (3, "OUT_LOW"), (6, "OUT_LOW"), (9, "OUT_LOW"), (12, "OUT_HORIZ"), (15, "OUT_HORIZ"), (18, "OUT_LOW"),
         (21, "OUT_LOW"), (24, "OUT_LOW"), (27, "OUT_LOW"), (30, "OUT_LOW"), (33, "OUT_DOWN"), (36, "OUT_LOW"), (39, "OUT_HORIZ"),
         (42, "OUT_LOW"), (45, "OUT_LOW"), (48, "OUT_LOW"), (51, "OUT_LOW")]
# torso (side lean, forward hunch, twist)
TORSO = [(0, (-0.04, 0.02, 0.0)), (3, (-0.05, 0.0, 0.10)), (6, (-0.06, -0.02, 0.18)), (9, (0.0, 0.02, 0.10)),
         (12, (0.10, 0.14, -0.10)), (15, (0.08, 0.10, -0.12)), (18, (0.03, 0.05, -0.05)), (21, (-0.08, 0.0, 0.15)),
         (24, (-0.06, 0.0, 0.12)), (27, (0.0, 0.0, 0.05)), (30, (0.04, 0.0, -0.05)), (33, (-0.12, 0.02, 0.20)),
         (36, (0.05, 0.08, -0.05)), (39, (0.09, 0.12, -0.10)), (42, (0.10, 0.30, -0.05)), (45, (0.03, 0.05, 0.05)),
         (48, (-0.05, -0.02, 0.10)), (51, (-0.02, 0.03, 0.0))]
# head (roll, nod forward, turn)
HEAD = [(0, (0.0, 0.0, 0.0)), (3, (0.05, -0.12, 0.10)), (6, (0.10, -0.28, 0.20)), (9, (0.05, -0.20, 0.15)),
        (12, (-0.10, 0.30, -0.10)), (15, (-0.10, 0.15, -0.10)), (18, (-0.05, 0.05, 0.0)), (21, (0.10, -0.10, 0.35)),
        (24, (0.05, -0.05, 0.25)), (27, (0.0, 0.0, 0.0)), (30, (-0.05, 0.0, -0.10)), (33, (0.15, -0.10, 0.40)),
        (36, (0.0, 0.10, 0.0)), (39, (-0.10, 0.18, -0.10)), (42, (-0.05, 0.50, 0.0)), (45, (0.0, -0.10, 0.10)),
        (48, (0.10, -0.18, 0.20)), (51, (0.0, 0.0, 0.0))]
# feet: ((x, lift, forward) for the screen-left foot, the same for the screen-right foot); shuffles and crossings
FEET = [(0, ((-1.0, 0.15, 0.0), (1.0, 0.0, 0.0))), (3, ((-0.9, 0.0, 0.0), (0.9, 0.30, 0.25))),
        (6, ((-0.9, 0.0, 0.0), (0.6, 0.45, -0.35))), (9, ((-0.9, 0.0, 0.0), (0.9, 0.0, 0.0))),
        (12, ((-1.15, 0.0, 0.0), (1.15, 0.0, 0.0))), (15, ((-0.6, 0.0, 0.0), (0.6, 0.30, 0.30))),
        (18, ((-0.3, 0.0, 0.2), (0.5, 0.40, -0.10))), (21, ((-1.0, 0.15, 0.3), (0.5, 0.0, 0.0))),
        (24, ((-0.6, 0.30, 0.25), (0.5, 0.0, 0.0))), (27, ((0.35, 0.35, 0.4), (0.45, 0.0, 0.0))),
        (30, ((-0.2, 0.0, 0.2), (0.55, 0.50, 0.30))), (33, ((-1.0, 0.0, 0.0), (1.0, 0.20, 0.20))),
        (36, ((-0.7, 0.0, 0.0), (0.9, 0.30, 0.0))), (39, ((-0.2, 0.20, 0.3), (0.7, 0.0, 0.0))),
        (42, ((-1.2, 0.0, 0.0), (1.2, 0.0, 0.0))), (45, ((-1.0, 0.0, 0.0), (1.0, 0.0, 0.0))),
        (48, ((-1.2, 0.10, 0.0), (1.1, 0.0, 0.0))), (51, ((-0.9, 0.25, 0.2), (0.8, 0.0, 0.0)))]
# how far the knees are bent (the pelvis drops)
CROUCH = [(0, -0.05), (3, -0.05), (6, 0.0), (9, -0.10), (12, -0.30), (15, -0.15), (18, -0.10), (21, -0.10), (24, 0.0),
          (27, -0.05), (30, 0.0), (33, -0.05), (36, -0.15), (39, -0.20), (42, -0.40), (45, -0.20), (48, -0.30), (51, -0.15)]

LOOP_FRAMES = 54.0

def ease(t): return t * t * (3 - 2 * t)

def mix_val(a, b, t):
    if isinstance(a, tuple):
        return tuple(mix_val(x, y, t) for x, y in zip(a, b))
    return a + (b - a) * t

def keyed(table, frame):
    """value of a keyframe table at a (fractional) frame of the loop; wraps around, eased between keys"""
    ks = table + [(LOOP_FRAMES + table[0][0], table[0][1])]
    f = frame % LOOP_FRAMES
    if f < ks[0][0]:
        f += LOOP_FRAMES
    for i in range(len(ks) - 1):
        (fa, va), (fb, vb) = ks[i], ks[i + 1]
        if fa <= f < fb:
            return mix_val(va, vb, ease((f - fa) / (fb - fa)))
    return ks[0][1]

def keyed_pose(table, frame):
    named = [(f, POSES[name]) for f, name in table]
    return keyed(named, frame)

def rot_x(v, a): c, s_ = math.cos(a), math.sin(a); return (v[0], v[1]*c - v[2]*s_, v[1]*s_ + v[2]*c)
def rot_y(v, a): c, s_ = math.cos(a), math.sin(a); return (v[0]*c + v[2]*s_, v[1], -v[0]*s_ + v[2]*c)
def rot_z(v, a): c, s_ = math.cos(a), math.sin(a); return (v[0]*c - v[1]*s_, v[0]*s_ + v[1]*c, v[2])

_state = {"last": None, "phase": 0.0, "lady_phase": 0.0}

def setup(screen, eyesy):
    pass

def place(mesh, dx, yaw, scale=1.0):
    """put a character in the scene: scale it about its feet, turn it about the vertical, slide it sideways"""
    verts, norms, faces, mult = mesh
    cy_, sy_ = math.cos(yaw), math.sin(yaw)
    nv, nn = [], []
    for (x, y, z) in verts:
        x, y, z = x * scale, FLOOR + (y - FLOOR) * scale, z * scale
        nv.append((x * cy_ + z * sy_ + dx, y, -x * sy_ + z * cy_))
    for (x, y, z) in norms:
        nn.append((x * cy_ + z * sy_, y, -x * sy_ + z * cy_))
    return nv, nn, faces, mult

def male_meshes(ph):
    # ---- skeleton (x right, y up, z toward the viewer when the alien faces forward) ----
    frame = (ph / (2 * math.pi) % 1.0) * LOOP_FRAMES
    lean, hunch, twist = keyed(TORSO, frame)
    h_roll, h_pitch, h_yaw = keyed(HEAD, frame)
    (lx, llift, lz), (rx, rlift, rz) = keyed(FEET, frame)
    crouch = keyed(CROUCH, frame) + 0.04 * math.cos(4 * ph)          # a small bounce on every step

    pelvis = (-0.5 * (rlift - llift) + 0.10 * math.sin(2 * ph), crouch, 0.05 * math.sin(2 * ph + 1.0))
    up_t = norm((math.sin(lean), math.cos(lean) * math.cos(hunch), math.sin(hunch)))
    chest = add(pelvis, mul(up_t, 2.15))
    fwd_t = norm((math.sin(twist), 0.0, math.cos(twist)))
    fwd_t = norm(sub(fwd_t, mul(up_t, dot(fwd_t, up_t))))
    right_t = cross(up_t, fwd_t)

    neck = add(chest, mul(up_t, 0.75))
    def hrot(v): return rot_y(rot_x(rot_z(v, h_roll), h_pitch), h_yaw)
    h_right, h_up, h_fwd = hrot((1.0, 0.0, 0.0)), hrot((0.0, 1.0, 0.0)), hrot((0.0, 0.0, 1.0))
    head_c = add(neck, mul(h_up, 1.45))

    shoulders = {s: add(chest, add(mul(right_t, s * 0.85), mul(up_t, 0.12))) for s in (-1, 1)}
    hips = {s: add(pelvis, (s * 0.42, 0.0, 0.0)) for s in (-1, 1)}

    legs = {}
    for side, (fx, lift, fz) in ((-1, (lx, llift, lz)), (1, (rx, rlift, rz))):
        foot_t = (fx * 0.8, FLOOR + lift, fz)                 # the reference keeps its feet fairly close together
        knee, ankle = ik3(hips[side], foot_t, L_THIGH, L_SHIN, (side * 0.5, 0.0, 1.0))
        dirf = norm((side * 0.5, -0.1, 1.0))
        toe = add(ankle, mul(dirf, 0.85))
        heel = sub(ankle, mul(dirf, 0.12))
        legs[side] = (hips[side], knee, ankle, toe, heel)

    arms = {}
    for side, table in ((-1, ARM_R), (1, ARM_L)):
        tgt, pole = keyed_pose(table, frame)
        sh = shoulders[side]
        wrist_t = add(sh, add(add(mul(right_t, side * tgt[0]), mul(up_t, tgt[1])), mul(fwd_t, tgt[2])))
        elbow, wrist = ik3(sh, wrist_t, L_UPPER, L_FORE,
                           add(add(mul(right_t, side * pole[0]), mul(up_t, pole[1])), mul(fwd_t, pole[2])))
        arms[side] = (sh, elbow, wrist)

    # ---- meshes ----
    meshes = []                                              # (mesh, material)
    def M(mesh, mat): meshes.append((mesh, mat))

    world_axes = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    def rib(i, j):                                           # faint rib bands on the front of the chest
        return 0.80 if i in (3, 5) and 1 <= j <= 6 else 1.0
    M(ellipsoid(add(pelvis, mul(up_t, 1.55)), right_t, up_t, fwd_t, 0.66, 0.95, 0.40, 9, 14, 0.0, rib), "skin")
    M(ellipsoid(add(pelvis, mul(up_t, 0.75)), right_t, up_t, fwd_t, 0.50, 0.85, 0.36, 8, 12), "skin")
    M(ellipsoid(pelvis, right_t, up_t, fwd_t, 0.58, 0.44, 0.40, 8, 12), "skin")
    M(capsule(shoulders[-1], shoulders[1], 0.30, 0.30, 8), "skin")
    M(capsule(add(chest, mul(up_t, 0.4)), sub(head_c, mul(h_up, 1.0)), 0.27, 0.25, 8), "skin")
    M(ellipsoid(head_c, h_right, h_up, h_fwd, 1.15, 1.45, 1.10, 11, 18, 0.28), "skin")

    def surface_z(x, y):                                     # where the head surface is in front of (x, y)
        s = 1.0 - 0.28 * (1.0 - y / 1.45) / 2.0
        return 1.10 * s * math.sqrt(max(0.02, 1.0 - (y / 1.45) ** 2 - (x / (1.15 * s)) ** 2))
    for side in (-1, 1):
        ex, ey = side * 0.62, -0.02
        ez = surface_z(ex, ey) - 0.03
        tilt = side * -0.50
        e_right = add(mul(h_right, math.cos(tilt)), mul(h_up, math.sin(tilt)))
        e_up = sub(mul(h_up, math.cos(tilt)), mul(h_right, math.sin(tilt)))
        c = add(head_c, add(add(mul(h_right, ex), mul(h_up, ey)), mul(h_fwd, ez)))
        M(ellipsoid(c, e_right, e_up, h_fwd, 0.46, 0.36, 0.16, 8, 14), "eye")
    # a wide smile: a curve that turns up at the corners, with small dimples at the ends
    def smile_point(x):
        y = -0.90 + 0.20 * (x / 0.52) ** 2
        return add(head_c, add(add(mul(h_right, x), mul(h_up, y)), mul(h_fwd, surface_z(x, y) - 0.005)))
    SM = 8 if _ds > 0.7 else 4
    xs = [-0.52 + 1.04 * i / SM for i in range(SM + 1)]
    for i in range(SM):
        M(capsule(smile_point(xs[i]), smile_point(xs[i + 1]), 0.036, 0.036, 5), "dark")
    for x in (-0.58, 0.58):
        M(capsule(smile_point(x), add(smile_point(x), mul(h_fwd, 0.01)), 0.03, 0.03, 5), "dark")
    for side in (-1, 1):
        n = add(head_c, add(add(mul(h_right, side * 0.10), mul(h_up, -0.52)), mul(h_fwd, surface_z(side * 0.10, -0.52))))
        M(capsule(n, add(n, mul(h_fwd, 0.02)), 0.035, 0.035, 5), "dark")

    for side in (-1, 1):
        sh, elbow, wrist = arms[side]
        M(capsule(sh, elbow, 0.26, 0.20, 8), "skin")
        M(capsule(elbow, wrist, 0.20, 0.15, 8), "skin")
        fore = norm(sub(wrist, elbow))
        hand_dir = norm(add(fore, (0.0, -0.55, 0.0)))               # the hand hangs a little, like a relaxed wrist
        side_v = norm(cross(hand_dir, (0.0, 0.0, 1.0)))
        for f in ((-0.4, 0.0, 0.4) if _ds > 0.7 else (0.0,)):
            tip = add(wrist, mul(norm(add(hand_dir, mul(side_v, f))), 0.62))
            M(capsule(wrist, tip, 0.09, 0.05, 6), "skin")
        hip, knee, ankle, toe, heel = legs[side]
        M(capsule(hip, knee, 0.34, 0.26, 8), "skin")
        M(capsule(knee, ankle, 0.26, 0.18, 8), "skin")
        M(capsule(heel, toe, 0.20, 0.14, 8), "skin")

    return meshes

# ---- the lady aliens: bent over and twerking to the same tempo as the male alien's dance ----
def basis(pitch, lean=0.0, twist=0.0):
    up = norm((math.sin(lean), math.cos(lean) * math.cos(pitch), math.sin(pitch)))
    f0 = norm((math.sin(twist), 0.0, math.cos(twist)))
    fwd = norm(sub(f0, mul(up, dot(f0, up))))
    return cross(up, fwd), up, fwd

def ray_ellipsoid(o, d, c, r):
    """far intersection of a ray with an axis-aligned ellipsoid, or None"""
    A = sum((d[k] / r[k]) ** 2 for k in range(3))
    B = 2 * sum((o[k] - c[k]) * d[k] / (r[k] ** 2) for k in range(3))
    C = sum(((o[k] - c[k]) / r[k]) ** 2 for k in range(3)) - 1.0
    disc = B * B - 4 * A * C
    if disc < 0:
        return None
    return (-B + math.sqrt(disc)) / (2 * A)

def lady_meshes(ph):
    shake = 12 * ph                                            # the twerk: twelve shakes per dance loop
    hunch = 0.62                                               # bent over at the waist
    pelvis = (0.0, -0.55 + 0.05 * math.cos(2 * shake), -0.45)
    R_p, U_p, F_p = basis(0.20, 0.06 * math.sin(shake))        # hips: nearly upright, rocking side to side
    R_t, U_t, F_t = basis(hunch, 0.03 * math.sin(shake + 1.0), 0.05 * math.sin(2 * ph))
    R_m, U_m, F_m = basis((0.20 + hunch) / 2)
    chest = add(pelvis, mul(U_m, 2.10))

    h_roll, h_pitch, h_yaw = 0.06 * math.sin(2 * ph), -0.75 * hunch + 0.05 * math.sin(shake / 2), -1.10
    def hrot(v): return rot_y(rot_x(rot_z(v, h_roll), h_pitch), h_yaw)
    h_right, h_up, h_fwd = hrot((1.0, 0.0, 0.0)), hrot((0.0, 1.0, 0.0)), hrot((0.0, 0.0, 1.0))
    neck = add(chest, mul(U_t, 0.72))
    HR = (1.08, 1.36, 1.05)
    head_c = add(neck, mul(h_up, 1.36))

    shoulders = {s_: add(chest, add(mul(R_t, s_ * 1.0), mul(U_t, 0.05))) for s_ in (-1, 1)}
    hips = {s_: add(pelvis, (s_ * 0.50, 0.0, 0.0)) for s_ in (-1, 1)}
    legs = {}
    for side in (-1, 1):
        knee, ankle = ik3(hips[side], (side * 0.85, FLOOR, 0.0), L_THIGH, L_SHIN, (side * 0.5, 0.0, 1.0))
        dirf = norm((side * 0.45, -0.1, 1.0))
        legs[side] = (hips[side], knee, ankle, add(ankle, mul(dirf, 0.80)), sub(ankle, mul(dirf, 0.12)))

    bust_pos = {s_: add(add(add(pelvis, mul(U_m, 1.42)), mul(R_t, s_ * 0.46)), mul(F_t, 0.60)) for s_ in (-1, 1)}
    arms = {}
    for side in (-1, 1):                                         # hands resting on the knees
        sh = shoulders[side]
        wrist_t = add(legs[side][1], (side * 0.05, 0.12, 0.35))
        elbow, wrist = ik3(sh, wrist_t, L_UPPER * 0.95, L_FORE * 0.95, (side * 1.0, 0.0, -0.4))
        for _ in range(3):                                       # keep the arms out of the bust
            for centre in bust_pos.values():
                for a_, b_, wa in ((sh, elbow, 0.0), (elbow, wrist, 1.0)):
                    for t in (0.3, 0.6, 0.9):
                        p_ = lerp3(a_, b_, t)
                        d_ = sub(p_, centre)
                        dist_ = length(d_)
                        need = 0.62 + 0.22 - dist_
                        if need > 0 and dist_ > 1e-6:
                            push = mul(d_, need / dist_)
                            elbow = add(elbow, mul(push, 0.9 if wa == 0.0 else 0.5))
        arms[side] = (sh, elbow, wrist)

    meshes = []
    def M(mesh, mat): meshes.append((mesh, mat))

    # ---- body: narrow waist, wide hips, big bust, and a very big rear that shakes ----
    M(ellipsoid(add(pelvis, mul(U_m, 1.50)), R_t, U_t, F_t, 0.52, 0.90, 0.38, 8, 12), "lady")
    M(ellipsoid(add(pelvis, mul(U_m, 0.75)), R_m, U_m, F_m, 0.40, 0.80, 0.34, 7, 10), "lady")
    PEL_R = (0.74, 0.50, 0.48)
    M(ellipsoid(pelvis, R_p, U_p, F_p, PEL_R[0], PEL_R[1], PEL_R[2], 7, 12), "lady")
    for side in (-1, 1):
        M(ellipsoid(bust_pos[side], R_t, U_t, F_t, 0.62, 0.60, 0.56, 9, 14), "lady")
    GL_R = (0.55, 0.58, 0.55)
    glute_local = {}                                             # centres in the hips' own frame
    for side in (-1, 1):
        off = 0.17 * math.sin(shake + (0.0 if side < 0 else math.pi))            # the two cheeks bounce in turn
        glute_local[side] = (side * 0.42, -0.05 + off, -0.48 + 0.06 * math.cos(shake + (0.0 if side < 0 else math.pi)))
        c = add(pelvis, add(add(mul(R_p, glute_local[side][0]), mul(U_p, glute_local[side][1])), mul(F_p, glute_local[side][2])))
        M(ellipsoid(c, R_p, U_p, F_p, GL_R[0], GL_R[1], GL_R[2], 9, 14), "lady")
    def P_(pt):                                                  # hips-frame point to world
        return add(pelvis, add(add(mul(R_p, pt[0]), mul(U_p, pt[1])), mul(F_p, pt[2])))

    # ---- thong, "whale tail" style: the straps climb toward the middle of her lower back, where a
    #      small triangle shows, with a string running down between the cheeks. It is laid on the
    #      surface of the hips and cheeks so it cannot sink in or float. ----
    Y_BAND, Y_TOP, Y_APEX = 0.12, 0.44, -0.04
    ells = [((0.0, 0.0, 0.0), PEL_R)] + [(glute_local[s_], GL_R) for s_ in (-1, 1)]
    def surf_pt(theta, side, y):
        d = (side * math.sin(theta), 0.0, math.cos(theta))
        o = (0.0, y, 0.0)
        best = None
        for c, r in ells:
            t = ray_ellipsoid(o, d, c, r)
            if t is not None and (best is None or t > best):
                best = t
        best = (best if best is not None else 0.6) + 0.035
        return (o[0] + d[0] * best, o[1], o[2] + d[2] * best)
    def back_z(x, y):                                            # the rear surface of the hips/cheeks at (x, y), hips frame
        z = None
        for c, r in ells:
            inside = 1.0 - ((x - c[0]) / r[0]) ** 2 - ((y - c[1]) / r[1]) ** 2
            if inside > 0.0:
                zz = c[2] - r[2] * math.sqrt(inside)
                z = zz if z is None else min(z, zz)
        return (z if z is not None else -0.3) - 0.035
    TAIL_HALF = 0.32
    th_end = math.pi - math.asin(TAIL_HALF / 0.95)              # where the strap meets the top corner of the tail
    for side in (-1, 1):
        n_seg = 16 if _ds > 0.7 else 8
        thetas = [0.60 + (th_end - 0.60) * i / n_seg for i in range(n_seg + 1)]
        def y_at(t):                                            # level at the sides, then it climbs at the back
            u_ = clamp((t - 1.9) / (th_end - 1.9))
            return Y_BAND + (Y_TOP - Y_BAND) * ease(u_)
        pts = [P_(surf_pt(t, side, y_at(t))) for t in thetas]
        # the last point sits exactly on the tail's top corner
        pts[-1] = P_((side * TAIL_HALF, Y_TOP, back_z(side * TAIL_HALF, Y_TOP)))
        for i in range(len(pts) - 1):
            M(capsule(pts[i], pts[i + 1], 0.045, 0.045, 5), "thong")
    # the tail itself: a triangle that points down toward the cleft
    tv, tn, tf = [], [], []
    rows_, cols_ = 5, 4
    for i in range(rows_ + 1):
        y = lerp(Y_TOP, Y_APEX, i / rows_)
        w = TAIL_HALF * (1.0 - i / rows_)
        for j in range(cols_ + 1):
            x = lerp(-w, w, j / cols_)
            tv.append(P_((x, y, back_z(x, y))))
            tn.append(norm(add(mul(F_p, -1.0), mul(U_p, 0.25))))
    for i in range(rows_):
        for j in range(cols_):
            k = i * (cols_ + 1) + j
            tf.append((k, k + 1, k + cols_ + 2, k + cols_ + 1))
    M((tv, tn, tf, [1.0] * len(tf)), "thong")
    # the string from the tail down between the cheeks
    def crack(y):
        return (0.0, y, back_z(0.0, y))
    ys = [Y_APEX - 0.09 * i for i in range(6 if _ds > 0.7 else 3)]
    for i in range(len(ys) - 1):
        M(capsule(P_(crack(ys[i])), P_(crack(ys[i + 1])), 0.038, 0.038, 5), "thong")
    # the front: a small triangle that follows the curve of the hips
    rows, cols = 5, 4
    pv, pn, pf = [], [], []
    for i in range(rows + 1):
        y = lerp(Y_BAND, -0.32, i / rows)
        w = 0.30 * (1.0 - i / rows)
        for j in range(cols + 1):
            x = lerp(-w, w, j / cols)
            zz = PEL_R[2] * math.sqrt(max(0.02, 1.0 - (x / PEL_R[0]) ** 2 - (y / PEL_R[1]) ** 2)) + 0.03
            pv.append(P_((x, y, zz)))
            pn.append(norm(add(add(mul(R_p, x / PEL_R[0] ** 2), mul(U_p, y / PEL_R[1] ** 2)), mul(F_p, zz / PEL_R[2] ** 2))))
    for i in range(rows):
        for j in range(cols):
            k = i * (cols + 1) + j
            pf.append((k, k + 1, k + cols + 2, k + cols + 1))
    M((pv, pn, pf, [1.0] * len(pf)), "thong")

    M(capsule(shoulders[-1], shoulders[1], 0.22, 0.22, 8), "lady")
    M(capsule(add(chest, mul(U_t, 0.4)), sub(head_c, mul(h_up, 0.95)), 0.24, 0.22, 8), "lady")
    M(ellipsoid(head_c, h_right, h_up, h_fwd, HR[0], HR[1], HR[2], 10, 16, 0.28), "lady")

    # ---- a plain, friendly face ----
    def surface_z(x, y):
        s_ = 1.0 - 0.28 * (1.0 - y / HR[1]) / 2.0
        return HR[2] * s_ * math.sqrt(max(0.02, 1.0 - (y / HR[1]) ** 2 - (x / (HR[0] * s_)) ** 2))
    def on_head(x, y, dz=0.0):
        return add(head_c, add(add(mul(h_right, x), mul(h_up, y)), mul(h_fwd, surface_z(x, y) + dz)))
    for side in (-1, 1):
        ex, ey, tilt = side * 0.62, -0.02, side * -0.50
        e_right = add(mul(h_right, math.cos(tilt)), mul(h_up, math.sin(tilt)))
        e_up = sub(mul(h_up, math.cos(tilt)), mul(h_right, math.sin(tilt)))
        M(ellipsoid(on_head(ex, ey, -0.03), e_right, e_up, h_fwd, 0.46, 0.36, 0.16, 8, 14), "eye")
        M(capsule(on_head(side * 0.10, -0.52, 0.01), on_head(side * 0.10, -0.52, 0.03), 0.035, 0.035, 5), "dark")
    def smile_pt(x):
        y = -0.86 + 0.18 * (x / 0.50) ** 2
        return on_head(x, y, -0.005)
    SM = 8 if _ds > 0.7 else 4
    xs = [-0.50 + 1.00 * i / SM for i in range(SM + 1)]
    for i in range(SM):
        M(capsule(smile_pt(xs[i]), smile_pt(xs[i + 1]), 0.034, 0.034, 5), "dark")

    for side in (-1, 1):
        sh, elbow, wrist = arms[side]
        M(capsule(sh, elbow, 0.22, 0.17, 6), "lady")
        M(capsule(elbow, wrist, 0.17, 0.13, 6), "lady")
        fore = norm(sub(wrist, elbow))
        hand_dir = norm(add(fore, (0.0, -0.25, 0.0)))
        side_v = norm(cross(hand_dir, (0.0, 0.0, 1.0)))
        for f in ((-0.4, 0.0, 0.4) if _ds > 0.7 else (0.0,)):
            tip = add(wrist, mul(norm(add(hand_dir, mul(side_v, f))), 0.55))
            M(capsule(wrist, tip, 0.08, 0.045, 5), "lady")
        hip, knee, ankle, toe, heel = legs[side]
        M(capsule(hip, knee, 0.36, 0.25, 7), "lady")
        M(capsule(knee, ankle, 0.25, 0.16, 7), "lady")
        M(capsule(heel, toe, 0.19, 0.13, 6), "lady")
    return meshes

def draw(screen, eyesy):
    global _ds
    lod_start()
    _ds = math.sqrt(_lod["q"])
    _draw(screen, eyesy)
    lod_end()

def _draw(screen, eyesy):
    xres, yres = eyesy.xres, eyesy.yres
    now = time.time()
    if _state["last"] is None:
        _state["last"] = now
    dt = min(now - _state["last"], 0.1)
    _state["last"] = now

    # ---- knobs ----
    scale = 0.35 + eyesy.knob1 * 1.5
    spin = eyesy.knob2 * 2 * math.pi
    speed = 0.4 + eyesy.knob3 * 2.6
    skin = tuple(eyesy.color_picker(eyesy.knob4))
    eyesy.color_picker_bg(0.0)                              # knob 5 is used for the ladies' tempo, so the background stays put
    lady_speed = 0.4 + eyesy.knob5 * 2.6                    # the ladies' own tempo (same range as the male's)

    _state["phase"] += dt * speed * 2 * math.pi / 2.7      # one full dance loop is about 2.7 seconds at speed 1
    _state["lady_phase"] += dt * lady_speed * 2 * math.pi / 2.7
    ph = _state["phase"]
    ph_lady = _state["lady_phase"]
    sw = 2 * ph                                              # the body sways twice per loop
    s1, s2 = math.sin(sw), math.sin(2 * sw)
    u_loop = ph / (2 * math.pi)

    # ---- the dancers: him in the middle, a bent-over lady on each side (the right one is a mirrored copy) ----
    meshes = []                                              # (mesh, material, sideways shift, turn, scale, mirrored)
    for mesh, mat in male_meshes(ph):
        meshes.append((mesh, mat, 0.0, 0.0, 1.0, False))
    lady = lady_meshes(ph_lady)
    for mesh, mat in lady:
        meshes.append((mesh, mat, -5.2, math.pi / 2 + 0.35, 0.94, False))
        meshes.append((mesh, mat, 5.2, -(math.pi / 2 + 0.35), 0.94, True))

    # ---- camera: a turntable spin about the feet, then a mild perspective ----
    D = 24.0
    U = yres * 0.050 * scale
    f = U * D
    cx, cy = xres / 2.0, yres / 2.0
    ca, sa = math.cos(spin), math.sin(spin)
    yc = 0.9

    # ---- light and colours ----
    skin_l = lerp3(skin, (255, 175, 215), 0.22)              # her skin is a touch pinker than his
    L = norm((-0.45, 0.65, 0.62))
    H = norm(add(L, (0.0, 0.0, 1.0)))
    Lx, Ly, Lz = L
    Hx, Hy, Hz = H
    skin_like = {"skin": skin, "lady": skin_l, "blush": (238, 105, 140)}
    tones = {m_: (lerp3(c, (8, 30, 12), 0.6), c) for m_, c in skin_like.items()}   # (shadow, lit) per material
    dark_c = tuple(int(lerp3(skin, (8, 30, 12), 0.6)[k] * 0.55) for k in range(3))
    thong_c = (205, 35, 95)
    def shade(mat, nx, ny, nz, m):
        diff = nx * Lx + ny * Ly + nz * Lz
        if diff < 0.0: diff = 0.0
        hd = nx * Hx + ny * Hy + nz * Hz
        if mat == "eye":
            spec = 255 * 0.95 * hd ** 40 if hd > 0.5 else 0.0
            return (min(255, int(10 + spec)), min(255, int(14 + spec)), min(255, int(16 + spec)))
        if mat == "dark":
            return dark_c
        if mat == "thong":
            k = 0.45 + 0.65 * diff
            sp = 255 * 0.25 * hd ** 30 if hd > 0.5 else 0.0
            return (int(min(255, thong_c[0] * k + sp)), int(min(255, thong_c[1] * k + sp)), int(min(255, thong_c[2] * k + sp)))
        sh_, lit = tones.get(mat, tones["skin"])
        t = 0.25 + 0.85 * diff
        if t > 1.0: t = 1.0
        rim = (1.0 - (nz if nz > 0.0 else 0.0)) ** 3 * 0.132
        sp = 255 * 0.28 * hd ** 24 if hd > 0.6 else 0.0
        r = (sh_[0] + (lit[0] - sh_[0]) * t); g = (sh_[1] + (lit[1] - sh_[1]) * t); b_ = (sh_[2] + (lit[2] - sh_[2]) * t)
        r += (255 - r) * rim; g += (255 - g) * rim; b_ += (230 - b_) * rim
        r = r * m + sp; g = g * m + sp; b_ = b_ * m + sp
        return (255 if r > 255 else int(r), 255 if g > 255 else int(g), 255 if b_ > 255 else int(b_))

    # ---- transform, cull, shade (a vertex is only projected if a visible face uses it) ----
    drawlist = []
    append = drawlist.append
    fs_cache = {}
    sqrt = math.sqrt
    for (verts, norms, faces, mult), mat, dx, yaw, sc, mirror in meshes:
        a_ = yaw + spin                                      # turn the character, then the whole turntable
        c1, s1_ = math.cos(a_), math.sin(a_)
        xx, xz, zx, zz = c1 * sc, s1_ * sc, -s1_ * sc, c1 * sc       # (x, z) -> (xr, zr) coefficients, scale included
        ox_, oz_ = dx * ca, -dx * sa
        if mirror:
            xx, zx = -xx, -zx
        nxx, nxz, nzx, nzz = (-c1 if mirror else c1), s1_, (s1_ if mirror else -s1_), c1
        key = id(faces), id(norms)
        fsum = fs_cache.get(key)
        if fsum is None:                                     # the summed model-space normal of every face (shared by both ladies)
            fsum = []
            for i0, i1, i2, i3 in faces:
                n0, n1, n2, n3 = norms[i0], norms[i1], norms[i2], norms[i3]
                fsum.append((n0[0] + n1[0] + n2[0] + n3[0], n0[1] + n1[1] + n2[1] + n3[1], n0[2] + n1[2] + n2[2] + n3[2]))
            fs_cache[key] = fsum
        cp = [None] * len(verts)
        cz = [0.0] * len(verts)
        bias = 0.35 if mat not in ("skin", "lady", "thong") else 0.0   # eyes and face marks sit on top of the head skin
        tone = tones.get(mat)
        if tone is not None:
            (sr_, sg_, sb_), (lr_, lg_, lb_) = tone
            dr_, dg_, db_ = lr_ - sr_, lg_ - sg_, lb_ - sb_
        for fi, quad in enumerate(faces):
            sx_, sy_, sz_ = fsum[fi]
            nz = sx_ * nzx + sz_ * nzz
            if nz < -0.2:                                    # facing away from the viewer
                continue
            nx = sx_ * nxx + sz_ * nxz
            l_ = sqrt(nx * nx + sy_ * sy_ + nz * nz) or 1.0
            pts = []
            zsum = 0.0
            for idx in quad:
                p = cp[idx]
                if p is None:
                    x, y, z = verts[idx]
                    zr = x * zx + z * zz + oz_
                    k_ = f / (D - zr)
                    p = cp[idx] = (cx + (x * xx + z * xz + ox_) * k_, cy - ((FLOOR + (y - FLOOR) * sc) - yc) * k_)
                    cz[idx] = zr
                pts.append(p)
                zsum += cz[idx]
            nx /= l_; ny = sy_ / l_; nz /= l_
            if tone is not None:                              # inlined skin shading: this is most of the faces
                diff = nx * Lx + ny * Ly + nz * Lz
                t = 0.25 + 0.85 * diff if diff > 0.0 else 0.25
                if t > 1.0: t = 1.0
                q_ = 1.0 - (nz if nz > 0.0 else 0.0)
                rim = q_ * q_ * q_ * 0.132
                hd = nx * Hx + ny * Hy + nz * Hz
                sp = 71.4 * hd ** 24 if hd > 0.6 else 0.0
                m_ = mult[fi]
                r = sr_ + dr_ * t; g = sg_ + dg_ * t; b_ = sb_ + db_ * t
                r = (r + (255 - r) * rim) * m_ + sp; g = (g + (255 - g) * rim) * m_ + sp; b_ = (b_ + (230 - b_) * rim) * m_ + sp
                color = (255 if r > 255 else int(r), 255 if g > 255 else int(g), 255 if b_ > 255 else int(b_))
            else:
                color = shade(mat, nx, ny, nz, mult[fi])
            append((zsum * 0.25 + bias, pts, color))

    drawlist.sort(key=lambda t: t[0])                        # far to near
    poly = pygame.draw.polygon
    for _, pts, color in drawlist:
        poly(screen, color, pts)
