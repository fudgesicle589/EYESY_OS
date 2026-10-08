# Classic Corvette Sting Ray (split-window coupe) driving away from the camera at sunset.
#
# Knob convention (same in every mode):
#   knob1 = size
#   knob2 = main motion / position / rotation  (here: steering, 0.5 = straight)
#   knob3 = extra detail                       (here: road speed)
#   knob4 = foreground color                   (here: the neon decal on the car, plus the palms and clouds)
#   knob5 = background color (sky and ground tint)
#
# The car is a lofted mesh (cross-sections along its length): long low body, fastback roof with
# a split rear window, round taillights, chrome bumpers. Lights, windows, exhausts
# and wheels are "decals" drawn right after the face they sit on, so they never flicker.
# Only the outer silhouette of the car is outlined.
import bisect
import math
import time
import pygame

# ============================== small math helpers ==============================

def sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def add(a, b): return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def scale(a, s): return (a[0]*s, a[1]*s, a[2]*s)
def dot(a, b): return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def length(v): return math.sqrt(dot(v, v))
def norm(v):
    l = length(v) or 1.0
    return (v[0]/l, v[1]/l, v[2]/l)

def lerp(a, b, t): return a + (b - a) * t
def lerp3(a, b, t): return (a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t, a[2]+(b[2]-a[2])*t)
def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))

def centroid(pts):
    n = float(len(pts))
    return (sum(p[0] for p in pts)/n, sum(p[1] for p in pts)/n, sum(p[2] for p in pts)/n)

OUT8 = ((-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, -1), (-1, 1), (1, 1))     # the offsets that make the outline
OUT4 = ((-2, 0), (2, 0), (0, -2), (0, 2))
LIFT = 0.06           # how far the body sits above the wheels (ride height)
AMBIENT = (95, 30, 150)   # purple fill light, matches the sunset

def shade(color, k):
    a = 0.35 * (1.0 - k)
    return (int(clamp(color[0]*k + AMBIENT[0]*a, 0, 255)),
            int(clamp(color[1]*k + AMBIENT[1]*a, 0, 255)),
            int(clamp(color[2]*k + AMBIENT[2]*a, 0, 255)))

def col(c, k):
    return (int(clamp(c[0]*k, 0, 255)), int(clamp(c[1]*k, 0, 255)), int(clamp(c[2]*k, 0, 255)))

# ============================== mesh ==============================

class Face:
    def __init__(self, pts, normal, ckey, decals=None):
        self.pts = pts
        self.n = normal
        self.c = centroid(pts)
        self.ckey = ckey
        self.decals = decals or []   # list of (pts, ckey, emissive)

def make_face(pts, ckey, axis_point, decals=None):
    """Face whose normal is flipped, if needed, to point away from axis_point."""
    n = cross(sub(pts[1], pts[0]), sub(pts[2], pts[0]))
    if length(n) < 1e-9:
        return None
    n = norm(n)
    if dot(n, sub(centroid(pts), axis_point)) < 0:
        n = scale(n, -1)
    return Face(pts, n, ckey, decals)

def make_face_wound(pts, ckey, decals=None):
    """Face whose normal comes straight from the winding of its points. The body rings run counter-clockwise, so this is
    always the outward normal, even where the body tilts inward (the fender tops and the cabin base), which a
    'point away from the middle of the car' guess gets backwards and then wrongly hides."""
    n = cross(sub(pts[1], pts[0]), sub(pts[2], pts[0]))
    if length(n) < 1e-9:
        return None
    return Face(pts, norm(n), ckey, decals)

# ---------- body: lofted from cross-sections ----------
# z: (belt-bottom half width, widest half width, fender half width, fender top, deck height)
BODY_KEYS = [
    (-2.20, 0.78, 0.90, 0.84, 0.76, 0.72),   # tail
    (-2.10, 0.80, 0.94, 0.88, 0.80, 0.72),
    (-1.85, 0.82, 0.97, 0.92, 0.84, 0.72),   # rear haunches
    (-1.30, 0.83, 0.98, 0.93, 0.82, 0.72),
    (-0.60, 0.81, 0.94, 0.90, 0.78, 0.72),
    (0.10, 0.80, 0.92, 0.88, 0.76, 0.72),    # doors
    (0.90, 0.82, 0.95, 0.91, 0.80, 0.70),    # front fenders
    (1.40, 0.82, 0.97, 0.92, 0.82, 0.70),
    (1.90, 0.78, 0.92, 0.88, 0.76, 0.66),    # long hood
    (2.20, 0.70, 0.86, 0.80, 0.70, 0.62),    # nose
]
# how much of the cab exists (0 = flat deck, 1 = full roof): hatchback with a long roof
CAB_KEYS = [(-1.75, 0.0), (-0.55, 1.0), (0.25, 1.0), (0.95, 0.0)]
ROOF_Y = 1.16
CAB_BASE_W = 0.70
BELT_Y = 0.60
PANES = [(-0.55, 0.25)]   # side window panes (z ranges)
ROW_ZS = sorted(set([k[0] for k in BODY_KEYS] + [k[0] for k in CAB_KEYS] +
                    [p[0] for p in PANES] + [p[1] for p in PANES] + [0.65]))

def interp_keys(keys, z, idx):
    if z <= keys[0][0]: return keys[0][idx]
    for a, b in zip(keys, keys[1:]):
        if z <= b[0]:
            return lerp(a[idx], b[idx], (z - a[0]) / (b[0] - a[0]))
    return keys[-1][idx]

def cab_frac(z):
    if z <= CAB_KEYS[0][0]: return 0.0
    for a, b in zip(CAB_KEYS, CAB_KEYS[1:]):
        if z <= b[0]:
            return lerp(a[1], b[1], (z - a[0]) / (b[0] - a[0]))
    return 0.0

HOOD_KEYS = [(0.95, 0.0), (1.25, 1.0), (1.90, 1.0), (2.20, 0.3)]

def hood_bump(z):
    if z <= HOOD_KEYS[0][0]: return 0.0
    for a, b in zip(HOOD_KEYS, HOOD_KEYS[1:]):
        if z <= b[0]:
            return lerp(a[1], b[1], (z - a[0]) / (b[0] - a[0]))
    return HOOD_KEYS[-1][1]

def ring(z):
    wb, ws, wd, yf, yd = [interp_keys(BODY_KEYS, z, i) for i in range(1, 6)]
    f = cab_frac(z)
    yr = yd + f * (ROOF_Y - yd)
    cb = CAB_BASE_W
    cr = cb - 0.12 * f
    if f == 0.0:                                   # raised centre of the hood
        bump = hood_bump(z)
        cr = lerp(cb, 0.50, bump)
        yr = yd + 0.07 * bump
    pts2d = [(wb, 0.14), (wb + 0.02, 0.42), (ws, BELT_Y), (wd, yf), (cb, yd), (cr, yr),
             (-cr, yr), (-cb, yd), (-wd, yf), (-ws, BELT_Y), (-wb - 0.02, 0.42), (-wb, 0.14)]
    return [(x, y, z) for x, y in pts2d], f

def quad_point(A, B, e, u, v):
    """point on the loft quad between rings A,B at edge e: u along the car, v along the edge"""
    a = lerp3(A[e], A[e+1], v)
    b = lerp3(B[e], B[e+1], v)
    return lerp3(a, b, u)

def pane(A, B, e, u0, u1, v0, v1):
    return [quad_point(A, B, e, u0, v0), quad_point(A, B, e, u0, v1),
            quad_point(A, B, e, u1, v1), quad_point(A, B, e, u1, v0)]

def disc(cx, cy, r, z, n=16):
    return [(cx + r*math.cos(2*math.pi*i/n), cy + r*math.sin(2*math.pi*i/n), z) for i in range(n)]

def rear_decals():
    z = -2.2 - 0.004
    P = lambda pts: [(x, y, z) for x, y in pts]
    d = [(P([(-0.74, 0.15), (0.74, 0.15), (0.78, 0.31), (-0.78, 0.31)]), "dark", False),    # valance
         (P([(-0.19, 0.36), (0.19, 0.36), (0.19, 0.50), (-0.19, 0.50)]), "dark", False)]    # plate recess
    for s in (-1, 1):
        # chrome bumper bar and neon line over it
        d.append((P([(0.26*s, 0.32), (0.76*s, 0.32), (0.77*s, 0.40), (0.26*s, 0.40)]), "chrome", False))
        d.append((P([(0.26*s, 0.415), (0.77*s, 0.415), (0.78*s, 0.445), (0.26*s, 0.445)]), "decal", True))
        # two round taillights per side: chrome bezel, dark ring, glowing lens
        for cx in (0.48, 0.72):
            d.append((disc(cx*s, 0.60, 0.108, z), "chrome", False))
            d.append((disc(cx*s, 0.60, 0.088, z), "light_dim", False))
            d.append((disc(cx*s, 0.60, 0.064, z), "light", True))
        # exhaust outlets under the bumper
        for r, key in ((0.075, "chrome"), (0.052, "pipe")):
            d.append((disc(0.42*s, 0.225, r, z, 12), key, False))
    return d + badge_decals()

def front_decals():
    z = 2.2 + 0.004
    P = lambda pts: [(x, y, z) for x, y in pts]
    d = [(P([(-0.66, 0.16), (0.66, 0.16), (0.68, 0.30), (-0.68, 0.30)]), "dark", False),
         (P([(-0.64, 0.30), (0.64, 0.30), (0.66, 0.38), (-0.64, 0.38)]), "chrome", False),   # front bumper
         (P([(-0.30, 0.42), (0.30, 0.42), (0.34, 0.54), (-0.34, 0.54)]), "chrome", False),   # grille surround
         (P([(-0.26, 0.44), (0.26, 0.44), (0.29, 0.52), (-0.29, 0.52)]), "dark", False)]
    for s in (-1, 1):
        d.append((disc(0.56*s, 0.50, 0.11, z), "chrome", False))
        d.append((disc(0.56*s, 0.50, 0.085, z), "head", True))
    return d

# --- decal design, drawn in flank space: (z along the car, h 0..1 up the side of the car) ---
FLANK_HK = 0.33      # where the belt line sits in h
BOLT = [
    [(-0.02, 0.90), (0.36, 0.90), (0.15, 0.56), (-0.23, 0.56)],
    [(-0.30, 0.64), (0.22, 0.64), (0.10, 0.44), (-0.42, 0.44)],
    [(-0.42, 0.52), (0.06, 0.52), (-0.32, 0.08)],
]
SPEED_LINES = [
    [(-0.55, 0.78), (-1.45, 0.78), (-1.45, 0.72), (-0.55, 0.72)],
    [(-0.62, 0.60), (-1.25, 0.60), (-1.25, 0.55), (-0.62, 0.55)],
    [(-0.68, 0.42), (-1.05, 0.42), (-1.05, 0.38), (-0.68, 0.38)],
    [(0.55, 0.78), (1.20, 0.78), (1.20, 0.73), (0.55, 0.73)],
]

def clip_poly(poly, axis, value, keep_greater):
    """Sutherland-Hodgman against one axis-aligned line"""
    out = []
    def inside(p): return p[axis] >= value if keep_greater else p[axis] <= value
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        ia, ib = inside(a), inside(b)
        if ia: out.append(a)
        if ia != ib:
            t = (value - a[axis]) / (b[axis] - a[axis])
            out.append((lerp(a[0], b[0], t), lerp(a[1], b[1], t)))
    return out

def flank_decals(ra, rb, e, side):
    """the part of the flank design that falls on loft quad (ra,rb) edge e (right: e=1 lower, 2 upper; left: 9 lower, 8 upper)"""
    za, zb = ra[0][2], rb[0][2]
    lower = e in (1, 9)
    hlo, hhi = (0.0, FLANK_HK) if lower else (FLANK_HK, 1.0)
    out = []
    for piece in BOLT + SPEED_LINES:
        poly = clip_poly(piece, 0, za, True)
        for axis, val, keep in ((0, zb, False), (1, hlo, True), (1, hhi, False)):
            if len(poly) < 3: break
            poly = clip_poly(poly, axis, val, keep)
        if len(poly) < 3: continue
        pts3 = []
        for z, h in poly:
            u = (z - za) / (zb - za)
            if side > 0: v = (h - hlo) / (hhi - hlo)
            else: v = 1 - (h - hlo) / (hhi - hlo)
            pts3.append(quad_point(ra, rb, e, u, v))
        out.append((pts3, "decal", True))
    return out

def badge_decals():
    """striped half-sun badge for the middle of the tailgate"""
    z = -2.2 - 0.004
    cx, cy, r = 0.0, 0.60, 0.10
    d = []
    edges = [0.0, 0.25, 0.42, 0.56, 0.67, 0.76, 0.84, 1.0]
    for i in range(0, len(edges) - 1, 2):
        y0, y1 = cy + r * edges[i], cy + r * edges[i + 1]
        x0 = math.sqrt(max(r*r - (y0 - cy)**2, 0)); x1 = math.sqrt(max(r*r - (y1 - cy)**2, 0))
        d.append(([(-x0, y0, z), (x0, y0, z), (x1, y1, z), (-x1, y1, z)], "decal", True))
    return d

SEAM = 0.06   # how far glass panes overlap into the next body section (as a share of its length)

def build_body():
    faces = []
    rows = [ring(z) for z in ROW_ZS]
    for (ra, fa), (rb, fb) in zip(rows, rows[1:]):
        za, zb = ra[0][2], rb[0][2]
        zc = (za + zb) / 2
        for e in range(11):
            quad = [ra[e], ra[e+1], rb[e+1], rb[e]]
            decals = []
            ckey = "dark" if e in (0, 10) else "body"
            if e == 5 and fa != fb:                            # rear hatch glass / windshield
                if fb != fa:
                    u_a = (0.10 - fa) / (fb - fa)
                    u_b = (0.92 - fa) / (fb - fa)
                    raw0, raw1 = min(u_a, u_b), max(u_a, u_b)
                    u0, u1 = clamp(raw0), clamp(raw1)
                    if u1 - u0 > 0.02:
                        if raw0 <= 0.0: u0 = -SEAM                     # the glass carries on into the neighbouring section, so
                        if raw1 >= 1.0: u1 = 1.0 + SEAM                # overlap it a little to close the hairline between them
                        decals.append((pane(ra, rb, e, u0, u1, 0.08, 0.92), "glass", False))
                        if zc < 0:                                 # the split-window centre spine
                            decals.append((pane(ra, rb, e, u0, u1, 0.47, 0.53), "body", False))
            if e in (4, 6) and fa == 1.0 and fb == 1.0:        # side windows
                for z0, z1 in PANES:
                    if z0 <= za + 1e-6 and zb <= z1 + 1e-6:
                        m = 0.05 / max(zb - za, 1e-6)
                        u0 = m if abs(za - z0) < 1e-6 else -SEAM
                        u1 = 1 - m if abs(zb - z1) < 1e-6 else 1.0 + SEAM
                        decals.append((pane(ra, rb, e, u0, u1, 0.22, 0.86), "glass", False))
            if e in (2, 8) and za >= 0.65 - 1e-6 and zb <= 0.90 + 1e-6:
                for lo in (0.12, 0.42, 0.72):                      # chrome fender slashes behind the front wheel
                    decals.append((pane(ra, rb, e, lo, lo + 0.16, 0.14, 0.86), "chrome", False))
            if e == 5 and fa == 0.0 and fb == 0.0 and zc > 1.0:   # twin racing stripes over the hood too
                decals.append((pane(ra, rb, e, 0, 1, 0.36, 0.44), "decal", True))
                decals.append((pane(ra, rb, e, 0, 1, 0.56, 0.64), "decal", True))
            f = make_face_wound(quad, ckey, decals)
            if f: faces.append(f)
    rear = Face(list(rows[0][0]), (0.0, 0.0, -1.0), "body", rear_decals())
    front = Face(list(rows[-1][0]), (0.0, 0.0, 1.0), "body", front_decals())
    return faces + [rear, front]

# ---------- wheels and mirrors ----------

def build_wheel(sx, cz, cy=0.38, r=0.38, n=20):
    xi, xo = (0.70, 0.98) if sx > 0 else (-0.70, -0.98)     # inner / outer cap planes
    def rp(x, rad, a):
        return (x, cy + rad*math.sin(a), cz + rad*math.cos(a))
    ang = [2*math.pi*i/n for i in range(n)]
    faces = []
    for i in range(n):
        j = (i + 1) % n
        q = [rp(xi, r, ang[i]), rp(xi, r, ang[j]), rp(xo, r, ang[j]), rp(xo, r, ang[i])]
        faces.append(make_face(q, "tire", (xi, cy, cz)))
    dx = 0.004 * sx
    decals = [([rp(xo + dx, 0.30, a) for a in ang], "rim", False),          # chrome wheel cover
              ([rp(xo + dx*2, 0.245, a) for a in ang], "rimdark", False),
              ([rp(xo + dx*3, 0.225, a) for a in ang], "rim", False),
              ([rp(xo + dx*4, 0.09, a) for a in ang], "body", False)]         # painted centre cap
    faces.append(Face([rp(xo, r, a) for a in ang], (float(sx), 0.0, 0.0), "tire", decals))
    faces.append(Face([rp(xi, r, a) for a in ang], (-float(sx), 0.0, 0.0), "tire"))
    return {"faces": faces, "outer": len(faces) - 2, "lift": 0.0, "center": (0.5 * (xi + xo), cy, cz),
            "is_wheel": True, "radius": r}

def build_box(x0, x1, y0, y1, z0, z1, ckey, sx=1, always_front=False):
    p = lambda x, y, z: (x, y, z)
    axis = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    quads = [[p(x0,y0,z0), p(x1,y0,z0), p(x1,y1,z0), p(x0,y1,z0)],
             [p(x0,y0,z1), p(x1,y0,z1), p(x1,y1,z1), p(x0,y1,z1)],
             [p(x0,y0,z0), p(x0,y0,z1), p(x0,y1,z1), p(x0,y1,z0)],
             [p(x1,y0,z0), p(x1,y0,z1), p(x1,y1,z1), p(x1,y1,z0)],
             [p(x0,y1,z0), p(x1,y1,z0), p(x1,y1,z1), p(x0,y1,z1)],
             [p(x0,y0,z0), p(x1,y0,z0), p(x1,y0,z1), p(x0,y0,z1)]]
    faces = [make_face(q, ckey, axis) for q in quads]
    outer = max(range(6), key=lambda i: faces[i].n[0] * sx)
    return {"faces": faces, "outer": outer, "always_front": always_front, "lift": LIFT, "center": axis}

BODY = build_body()
ATTACHMENTS = (
    [build_wheel(sx, cz) for sx in (-1, 1) for cz in (-1.46, 1.46)] +
    [build_box(0.66, 0.84, 0.80, 0.89, 0.28, 0.46, "chrome", 1), build_box(-0.84, -0.66, 0.80, 0.89, 0.28, 0.46, "chrome", -1)]
)

COLORS = {
    "body": (150, 12, 30),        # deep red
    "dark": (30, 30, 36),
    "glass": (16, 24, 44),
    "light": (255, 90, 70),
    "light_dim": (48, 8, 14),
    "head": (255, 245, 210),
    "tire": (24, 24, 27),
    "rim": (196, 202, 214),
    "chrome": (196, 202, 214),
    "rimdark": (70, 54, 22),
    "pipe": (8, 8, 10),
}
OUTLINE = (10, 6, 18)
LIGHT = norm((0.35, 0.85, -0.45))

# ============================== scene ==============================

CAM_DIST = 9.0
CAM_H = 1.6
ROAD_HW = 2.6            # half width of the road in car units
HORIZON = 0.38           # horizon height as a fraction of the screen
NEON_PINK = (255, 70, 200)
SUN_TOP = (150, 60, 255)
SUN_BOT = (255, 70, 220)

_bg_cache = {"key": None, "surf": None}
_scroll = {"pos": 0.0, "dist": 0.0, "t": None, "dt": None}
_car_surf = {"size": None, "surf": None}

def palette(base):
    return {
        "top": lerp3(col(base, 0.30), (8, 0, 28), 0.5),
        "horizon": lerp3(col(base, 0.9), (255, 60, 190), 0.55),
        "ground": lerp3(col(base, 0.14), (10, 4, 26), 0.6),
        "road": lerp3(col(base, 0.20), (34, 30, 50), 0.7),
    }

def build_background(xres, yres, base):
    """sky, sun and the ground either side of the road (the road itself is drawn every frame)"""
    oy = int(yres * HORIZON)
    ox = xres // 2
    surf = pygame.Surface((xres, yres))
    pal = palette(base)
    top, horizon, ground = pal["top"], pal["horizon"], pal["ground"]

    for y in range(oy + 1):
        t = (y / max(oy, 1)) ** 1.7
        pygame.draw.line(surf, lerp3(top, horizon, t), (0, y), (xres, y))

    r = yres * 0.20
    cy = oy - 0.05 * r
    glow = pygame.Surface((xres, oy + 1), pygame.SRCALPHA)
    for i in range(40):
        rad = r * (2.0 - i * 0.025)
        pygame.draw.circle(glow, (190, 60, 255, 3), (ox, int(cy)), int(rad))
    surf.blit(glow, (0, 0))
    for y in range(int(cy - r), oy + 1):
        dy = y - cy
        if abs(dy) >= r: continue
        w = math.sqrt(r * r - dy * dy)
        t = (y - (cy - r)) / (2 * r)
        if t > 0.25:                                           # stripes cut into the lower part
            band = clamp((t - 0.25) / 0.28)
            period = lerp(r * 0.17, r * 0.08, band)
            if (y % period) < period * (0.12 + 0.55 * band):
                continue
        pygame.draw.line(surf, lerp3(SUN_TOP, SUN_BOT, t), (ox - w, y), (ox + w, y))

    span = max(yres - oy, 1)
    for y in range(oy + 1, yres):
        s = clamp(((y - oy) / span) / 0.55) ** 0.8
        pygame.draw.line(surf, lerp3(horizon, ground, s), (0, y), (xres, y))
    return surf

def road_samples():
    """distances along the road (in car units) at which the road is sampled"""
    ss, s = [], 0.0
    while s < 30: ss.append(s); s += 1.0
    while s < 100: ss.append(s); s += 3.0
    while s < 240: ss.append(s); s += 10.0
    return ss

ROAD_S = road_samples()
# lateral positions across the road that get projected for every sample:
# left halo (out, in), left core (out, in), left edge, dash left/right, right edge, right core (in, out), right halo (in, out)
def _lats(hw):
    return (-hw - 0.24, -hw - 0.10, -hw, -hw + 0.10, -hw + 0.24, -0.07, 0.07, hw - 0.24, hw - 0.10, hw, hw + 0.10, hw + 0.24)

def draw_road(screen, xres, yres, focal, S, yaw, steer, speed, pal):
    """The road starts under the car heading the way the car points, then keeps bending the same way."""
    now = time.time()
    if _scroll["t"] is not None:
        dt = min(now - _scroll["t"], 0.1)
        _scroll["dt"] = dt if _scroll["dt"] is None else _scroll["dt"] + (dt - _scroll["dt"]) * 0.1     # frames never arrive perfectly evenly; moving by the average gap keeps the scenery from stuttering
        _scroll["dist"] += speed * _scroll["dt"]
    _scroll["pos"] = _scroll["dist"] % 4.0
    _scroll["t"] = now

    ox, oy = xres / 2, yres * HORIZON
    kappa = steer * 0.006                               # extra bend per unit of road
    sin, cos = math.sin, math.cos
    X = Z = 0.0
    fwd = [(0.0, 0.0, 0.0, yaw)]                        # forward: integrate the heading along the road
    for s0, s1 in zip(ROAD_S, ROAD_S[1:]):
        h = clamp(yaw + kappa * (s0 + s1) / 2, -1.3, 1.3)
        X += sin(h) * (s1 - s0)
        Z += cos(h) * (s1 - s0)
        fwd.append((s1, X, Z, h))
    s_min = -(CAM_DIST - 2.6) / S                       # back to just in front of the camera
    n_back = max(int(-s_min / 1.0), 1)
    back = [(s_min * (1 - i / n_back), s_min * (1 - i / n_back) * sin(yaw),
             s_min * (1 - i / n_back) * cos(yaw), yaw) for i in range(n_back)]
    pts = back + fwd

    # project every sample across the road just once (neighbouring segments share their end points)
    lats = _lats(ROAD_HW)
    k_ = S * focal
    rows = []
    for (s, x, z, h) in pts:
        ch, sh_ = cos(h), sin(h)
        row = []
        for lat in lats:
            zc = (z - sh_ * lat) * S + CAM_DIST
            if zc < 2.5:
                row.append(None)
            else:
                row.append((ox + (x + ch * lat) * k_ / zc, oy + CAM_H * focal / zc))
        rows.append(row)

    horizon, road = pal["horizon"], pal["road"]
    halo_c = lerp3(road, NEON_PINK, 0.35)
    dash_c = (235, 130, 225)
    poly = pygame.draw.polygon
    q = _lod["q"]
    dash_period, dash_len = 4.0, 1.8
    span_y = (yres - oy) * 0.55
    for i in range(len(pts) - 2, -1, -1):              # far to near
        ra, rb = rows[i], rows[i + 1]
        if ra[2] is None or ra[9] is None or rb[2] is None or rb[9] is None:
            continue
        f = clamp(((ra[5] or ra[2])[1] - oy) / span_y) ** 0.8
        # the far end of every piece is nudged up a pixel so neighbouring pieces overlap: no hairline gaps, no outline pass
        def quad(ia, ib, color):
            a, b, c, d = ra[ia], ra[ib], rb[ib], rb[ia]
            if a and b and c and d:
                poly(screen, color, [a, b, (c[0], c[1] - 1.0), (d[0], d[1] - 1.0)])
        quad(2, 9, lerp3(horizon, road, f))
        if q > 0.45:
            hc = lerp3(horizon, halo_c, f)
            quad(0, 4, hc)
            quad(7, 11, hc)
        cc = lerp3(horizon, NEON_PINK, f)
        quad(1, 3, cc)
        quad(8, 10, cc)
        # centre dashes, clipped to this segment
        s0, s1 = pts[i][0], pts[i + 1][0]
        if ra[5] and ra[6] and rb[5] and rb[6]:
            k = math.floor((s0 + _scroll["pos"]) / dash_period)
            dcol = lerp3(horizon, dash_c, f)
            while True:
                a = k * dash_period - _scroll["pos"]
                if a >= s1: break
                lo, hi = max(a, s0), min(a + dash_len, s1)
                if hi > lo:
                    t0, t1 = (lo - s0) / (s1 - s0), (hi - s0) / (s1 - s0)
                    l0 = (lerp(ra[5][0], rb[5][0], t0), lerp(ra[5][1], rb[5][1], t0)); r0 = (lerp(ra[6][0], rb[6][0], t0), lerp(ra[6][1], rb[6][1], t0))
                    l1 = (lerp(ra[5][0], rb[5][0], t1), lerp(ra[5][1], rb[5][1], t1) - 1.0); r1 = (lerp(ra[6][0], rb[6][0], t1), lerp(ra[6][1], rb[6][1], t1) - 1.0)
                    poly(screen, dcol, [l0, r0, r1, l1])
                k += 1
    return pts

# ---------- palm trees: same neon gradient and cut-out stripes as the sun ----------
PALM_W, PALM_H = 200, 330
TREE_SPACING = 7.0
_palm = {"sprite": None}

def bezier(p0, p1, p2, n=14):
    return [((1-t)**2*p0[0] + 2*(1-t)*t*p1[0] + t*t*p2[0],
             (1-t)**2*p0[1] + 2*(1-t)*t*p1[1] + t*t*p2[1]) for t in [i/(n-1) for i in range(n)]]

def ribbon(curve, w0, w1, shape=None):
    """polygon around a curve with a width that runs from w0 to w1 (or follows shape(t))"""
    left, right = [], []
    for i, (x, y) in enumerate(curve):
        a = curve[max(i-1, 0)]; b = curve[min(i+1, len(curve)-1)]
        dx, dy = b[0]-a[0], b[1]-a[1]
        l = math.hypot(dx, dy) or 1
        nx, ny = -dy/l, dx/l
        t = i / (len(curve) - 1)
        w = shape(t) if shape else lerp(w0, w1, t)
        left.append((x + nx*w/2, y + ny*w/2)); right.append((x - nx*w/2, y - ny*w/2))
    return left + right[::-1]

def build_palm(k=3):
    """palm sprite drawn at k times its logical size so it stays crisp when the car is zoomed in"""
    W, H = PALM_W * k, PALM_H * k
    mask = pygame.Surface((W, H), pygame.SRCALPHA)
    white = (255, 255, 255, 255)
    crown = (122 * k, 96 * k)
    pygame.draw.polygon(mask, white, ribbon(bezier((96 * k, H - 4 * k), (84 * k, 220 * k), crown), 16 * k, 8 * k))
    for ang, ln in ((172, 96), (148, 112), (122, 92), (90, 66), (58, 94), (32, 112), (8, 96)):
        a = math.radians(ang)
        ln *= k
        dx, dy = math.cos(a), -math.sin(a)
        mid = (crown[0] + dx*ln*0.55, crown[1] + dy*ln*0.55 - ln*0.30)
        end = (crown[0] + dx*ln, crown[1] + dy*ln + ln*0.34)
        pygame.draw.polygon(mask, white, ribbon(bezier(crown, mid, end, 24), 0, 0,
                                                lambda t: 15 * k * math.sin(math.pi * min(t * 1.05, 1))))
    for ox_, oy_ in ((-6, 6), (6, 7), (0, 12)):
        pygame.draw.circle(mask, white, (crown[0] + ox_ * k, crown[1] + oy_ * k), 6 * k)
    grad = pygame.Surface((W, H), pygame.SRCALPHA)
    for y in range(H):
        t = y / H
        g = int(lerp(255, 205, t))                              # grey ramp, tinted with the decal colour when drawn
        color = (g, g, g)
        alpha = 255
        if t > 0.30:                                            # stripes, thicker toward the bottom like the sun
            band = (t - 0.30) / 0.70
            period = lerp(H * 0.075, H * 0.04, band)
            if (y % period) < period * (0.12 + 0.5 * band):
                alpha = 0
        pygame.draw.line(grad, color + (alpha,), (0, y), (W, y))
    grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return grad

def build_palm_mips():
    """the sprite at 1/2, 1/4, 1/8 ... size; scaling straight down from the big one to a few pixels breaks smoothscale"""
    mips = [build_palm()]
    while mips[-1].get_width() > 8 and mips[-1].get_height() > 8:
        w, h = mips[-1].get_size()
        mips.append(pygame.transform.smoothscale(mips[-1], (w // 2, h // 2)))
    return mips

def road_at(pts, svals, s):
    i = max(1, min(bisect.bisect_left(svals, s), len(pts) - 1))
    a, b = pts[i - 1], pts[i]
    t = (s - a[0]) / ((b[0] - a[0]) or 1.0)
    return lerp(a[1], b[1], t), lerp(a[2], b[2], t), b[3]

def palm_trees(pts, xres, yres, focal, S):
    """returns [(depth, sprite, x, y)] far to near"""
    if _palm["sprite"] is None:
        _palm["sprite"] = build_palm_mips()
    svals = [p[0] for p in pts]
    ox, oy = xres / 2, yres * HORIZON
    dist = _scroll["dist"]
    out = []
    k0 = int(math.floor((svals[0] + dist) / TREE_SPACING))
    k1 = int(math.floor((140 + dist) / TREE_SPACING))
    for k in range(k0, k1 + 1):
        s = k * TREE_SPACING - dist
        if s < svals[0] or s > svals[-1]: continue
        x, z, h = road_at(pts, svals, s)
        for sgn in (-1, 1):
            r1 = ((k * 73856093) ^ ((sgn + 2) * 19349663)) % 1000 / 1000.0
            r2 = ((k * 83492791) ^ ((sgn + 3) * 2654435761)) % 1000 / 1000.0
            if r1 > 0.85: continue                              # gaps between trees
            lat = sgn * (ROAD_HW + 1.7 + 2.6 * r2)
            wx, wz = x + math.cos(h) * lat, z - math.sin(h) * lat
            zc = wz * S + CAM_DIST
            if zc < 3.0: continue
            ph = 3.6 * (0.8 + 0.4 * r1) * S * focal / zc
            if ph < 4 or ph > 1100: continue
            pw = ph * PALM_W / PALM_H
            bx, by = ox + wx * S * focal / zc, oy + CAM_H * focal / zc
            if bx + pw < 0 or bx - pw > xres: continue
            f = clamp((by - oy) / ((yres - oy) * 0.55)) ** 0.8
            out.append((zc, int(pw), int(ph), bx, by, int(40 + 215 * f)))
    out.sort(key=lambda t: -t[0])
    return out

_tree_cache = {"key": None, "imgs": {}}

def blit_tree(screen, t, tint):
    zc, pw, ph, bx, by, alpha = t
    tq = (tint[0] >> 4, tint[1] >> 4, tint[2] >> 4)
    if _tree_cache["key"] != tq:                   # the colour changed: start the cache afresh
        _tree_cache["key"] = tq
        _tree_cache["imgs"] = {}
    imgs = _tree_cache["imgs"]
    hh = max(4, ph)                                # exact pixel height, so a tree grows smoothly instead of popping between sizes
    aq = min(5, alpha * 6 // 256)
    img = imgs.get((hh, aq))
    if img is None:
        if len(imgs) > 150:                        # never let the cache grow without limit
            imgs.clear()
        ww = max(2, int(hh * PALM_W / PALM_H))
        src = _palm["sprite"][0]
        for m in _palm["sprite"]:                  # smallest version that is still at least as big as needed
            if m.get_width() >= ww and m.get_height() >= hh: src = m
        if ww > src.get_width() or hh > src.get_height():
            img = pygame.transform.scale(src, (ww, hh))
        else:
            img = pygame.transform.smoothscale(src, (ww, hh))
        a_ = int(40 + (aq + 0.5) * 36)
        img.fill((tq[0] * 16 + 8, tq[1] * 16 + 8, tq[2] * 16 + 8, min(255, a_)), special_flags=pygame.BLEND_RGBA_MULT)
        imgs[(hh, aq)] = img
    screen.blit(img, (int(bx - img.get_width() / 2), int(by - img.get_height())))

# ---------- clouds: flat-bottomed neon clouds with sun-style stripes, tinted by the decal colour ----------
CLOUD_W, CLOUD_H = 480, 150
CLOUD_BASE = 125
# (shape, left position 0..1, cloud bottom as fraction of the screen height, width as fraction of the screen, drift, opacity)
CLOUDS = [
    (0, 0.05, 0.27, 0.34, 1.0, 0.75), (1, 0.42, 0.15, 0.22, 0.6, 0.65), (2, 0.70, 0.31, 0.42, 1.4, 0.55),
    (0, 0.83, 0.12, 0.26, 0.5, 0.60), (2, 0.20, 0.09, 0.30, 0.8, 0.45), (1, 0.60, 0.34, 0.20, 1.1, 0.60),
]
_cloud_sprites = {}

def build_cloud(kind):
    mask = pygame.Surface((CLOUD_W, CLOUD_H), pygame.SRCALPHA)
    white = (255, 255, 255, 255)
    if kind == 0:
        blobs = [(90, 98, 42), (165, 72, 60), (255, 58, 68), (340, 78, 56), (412, 104, 38)]
    elif kind == 1:
        blobs = [(75, 96, 36), (145, 72, 50), (220, 84, 44), (292, 102, 30)]
    else:
        blobs = []
    for cx, cy, r in blobs:
        pygame.draw.circle(mask, white, (cx, cy), r)
    if blobs:
        x0 = min(b[0] - b[2] * 0.6 for b in blobs); x1 = max(b[0] + b[2] * 0.6 for b in blobs)
        pygame.draw.rect(mask, white, (x0, CLOUD_BASE - 34, x1 - x0, 34))
    else:                                                       # long thin streaks
        pygame.draw.ellipse(mask, white, (10, CLOUD_BASE - 34, CLOUD_W - 20, 34))
        pygame.draw.ellipse(mask, white, (90, CLOUD_BASE - 58, CLOUD_W - 210, 30))
    pygame.draw.rect(mask, (0, 0, 0, 0), (0, CLOUD_BASE, CLOUD_W, CLOUD_H - CLOUD_BASE))   # flat bottom
    grad = pygame.Surface((CLOUD_W, CLOUD_H), pygame.SRCALPHA)
    for y in range(CLOUD_H):
        g = int(lerp(255, 165, clamp(y / CLOUD_BASE)))
        alpha = 255
        t = (y - (CLOUD_BASE - 50)) / 50.0
        if t > 0:                                               # stripes cut into the bottom, thicker toward the base
            period = lerp(11, 6, t)
            if (y % period) < period * (0.15 + 0.5 * t):
                alpha = 0
        pygame.draw.line(grad, (g, g, g, alpha), (0, y), (CLOUD_W, y))
    grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return grad

_cloud_cache = {"key": None, "imgs": []}

def draw_clouds(screen, xres, yres, tint):
    if not _cloud_sprites:
        for kind in (0, 1, 2):
            _cloud_sprites[kind] = build_cloud(kind)
    tq = (tint[0] >> 4, tint[1] >> 4, tint[2] >> 4)
    key = (xres, yres, tq)
    if _cloud_cache["key"] != key:                 # scale and tint the clouds only when the size or colour changes
        imgs = []
        for kind, x0, yb, wf, drift, opacity in CLOUDS:
            w = int(xres * wf)
            h = int(w * CLOUD_H / CLOUD_W)
            img = pygame.transform.smoothscale(_cloud_sprites[kind], (w, h))
            img.fill((tq[0] * 16 + 8, tq[1] * 16 + 8, tq[2] * 16 + 8, int(255 * opacity)), special_flags=pygame.BLEND_RGBA_MULT)
            imgs.append(img)
        _cloud_cache["key"], _cloud_cache["imgs"] = key, imgs
    now = time.time()
    for img, (kind, x0, yb, wf, drift, opacity) in zip(_cloud_cache["imgs"], CLOUDS):
        w, h = img.get_size()
        span = xres + w
        x = (x0 * span + now * 6.0 * drift * xres / 1280.0) % span - w
        y = int(yres * yb - h * CLOUD_BASE / CLOUD_H)
        screen.blit(img, (int(x), y))

# ============================== mode ==============================

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

    # ---- knobs ----
    S = 0.3 + eyesy.knob1 * 1.2                    # car scale
    steer = (eyesy.knob2 - 0.5) * 2                # -1 (left) .. +1 (right)
    speed = eyesy.knob3 * 40.0                     # road speed, units per second
    base_bg = tuple(int(c) for c in eyesy.color_picker_bg(eyesy.knob5))
    decal = tuple(int(c) for c in eyesy.color_picker(eyesy.knob4))
    colors = dict(COLORS, decal=decal)

    # ---- background (cached until the resolution or bg color changes) ----
    key = (xres, yres, base_bg)
    if _bg_cache["key"] != key:
        _bg_cache["key"], _bg_cache["surf"] = key, build_background(xres, yres, base_bg)
    screen.blit(_bg_cache["surf"], (0, 0))
    draw_clouds(screen, xres, yres, decal)

    # ---- camera ----
    focal = yres * 2.1
    ox = xres / 2
    oy = yres * HORIZON                            # the horizon sits at the camera's eye line
    yaw = math.radians(steer * 40)
    cs, sn = math.cos(yaw), math.sin(yaw)

    def rot(v):
        return (v[0]*cs + v[2]*sn, v[1], -v[0]*sn + v[2]*cs)

    def to_cam(p, lift=0.0):
        r = rot(p)
        return (r[0]*S, (r[1] + lift)*S - CAM_H, r[2]*S + CAM_DIST)

    def project(p):
        return (ox + p[0] * focal / p[2], oy - p[1] * focal / p[2])

    pts = draw_road(screen, xres, yres, focal, S, yaw, steer, speed, palette(base_bg))
    trees = palm_trees(pts, xres, yres, focal, S)
    for t in trees:                                # trees behind the car go under it
        if t[0] >= CAM_DIST: blit_tree(screen, t, decal)

    # ---- ground shadow (a plain dark shape: no temporary surface to allocate every frame) ----
    sh = [project(to_cam(p)) for p in [(-1.4, 0, -2.3), (1.4, 0, -2.3), (1.4, 0, 2.3), (-1.4, 0, 2.3)]]
    pygame.draw.polygon(screen, (9, 6, 15), sh)

    # ---- draw the car onto its own transparent layer (only the part of it used last frame is cleared) ----
    if _car_surf["size"] != (xres, yres):
        _car_surf["size"] = (xres, yres)
        _car_surf["surf"] = pygame.Surface((xres, yres), pygame.SRCALPHA)
        _car_surf["dirty"] = None
    car = _car_surf["surf"]
    if _car_surf.get("dirty") is None:
        car.fill((0, 0, 0, 0))
    else:
        car.fill((0, 0, 0, 0), _car_surf["dirty"])
    bb = [xres, yres, 0, 0]
    two_pass = _lod["q"] > 0.6                       # a same-colour edge pass closes hairline cracks between faces
    poly_draw = pygame.draw.polygon

    def proj_pts(pts3, lift):
        """project model-space points to the screen (rotation, scale, camera and perspective in one go)"""
        out = []
        for x, y, z in pts3:
            Z = (-x * sn + z * cs) * S + CAM_DIST
            k = focal / Z
            out.append((ox + (x * cs + z * sn) * S * k, oy - ((y + lift) * S - CAM_H) * k))
        return out

    def visible(face, lift):
        c = to_cam(face.c, lift)
        n = rot(face.n)
        return (c, n) if dot(n, c) < 0 else None

    def paint(face, n, lift):
        k = 0.5 + 0.5 * max(0.0, dot(n, LIGHT))
        poly = proj_pts(face.pts, lift)
        for x, y in poly:
            if x < bb[0]: bb[0] = x
            if y < bb[1]: bb[1] = y
            if x > bb[2]: bb[2] = x
            if y > bb[3]: bb[3] = y
        color = shade(colors[face.ckey], k)
        poly_draw(car, color, poly)
        if two_pass:
            poly_draw(car, color, poly, 1)
        for pts, ckey, emissive in face.decals:
            dpoly = proj_pts(pts, lift)
            dcol = colors[ckey] if emissive else shade(colors[ckey], k)
            poly_draw(car, dcol, dpoly)
            if two_pass:
                poly_draw(car, dcol, dpoly, 1)

    def visible_sorted(faces, lift):
        vis = []
        for f in faces:
            if f is None: continue
            v = visible(f, lift)
            if v: vis.append((dot(v[0], v[0]), f, v[1]))
        vis.sort(key=lambda t: -t[0])              # far to near
        return vis

    def paint_all(vis, lift):
        for _, f, n in vis:
            paint(f, n, lift)

    # wheels/mirrors on the far side go behind the body, near side in front of it
    behind, front = [], []
    for a in ATTACHMENTS:
        if a.get("always_front") or visible(a["faces"][a["outer"]], a["lift"]):
            front.append(a)
        else:
            behind.append(a)
    def far_to_near(group):
        def dist2(a):
            c = to_cam(a["center"], a["lift"])
            return dot(c, c)
        return sorted(group, key=lambda a: -dist2(a))
    for a in far_to_near(behind): paint_all(visible_sorted(a["faces"], a["lift"]), a["lift"])
    body_vis = visible_sorted(BODY, LIFT)            # worked out once, then reused for every wheel below
    paint_all(body_vis, LIFT)
    for a in far_to_near(front):
        paint_all(visible_sorted(a["faces"], a["lift"]), a["lift"])
        if a.get("is_wheel"):
            # body panels that are clearly closer to the camera than this wheel (the tail, the rear
            # fender) sit in front of it, so paint them again on top of the wheel
            c = to_cam(a["center"], a["lift"])
            wheel_dist = math.sqrt(dot(c, c))
            limit = (wheel_dist - a["radius"]) ** 2 if wheel_dist > a["radius"] else -1.0
            paint_all([v for v in body_vis if v[0] < limit], LIFT)

    # ---- outline only the outside edge of the car ----
    pad = 4
    rx, ry = max(int(bb[0]) - pad, 0), max(int(bb[1]) - pad, 0)
    rw, rh = min(int(bb[2]) + pad, xres) - rx, min(int(bb[3]) + pad, yres) - ry
    if rw > 0 and rh > 0:
        crop = car.subsurface((rx, ry, rw, rh))
        sil = pygame.mask.from_surface(crop).to_surface(setcolor=OUTLINE + (255,), unsetcolor=(0, 0, 0, 0))
        offsets = OUT8 if _lod["q"] > 0.5 else OUT4
        for dx, dy in offsets:
            screen.blit(sil, (rx + dx, ry + dy))
        screen.blit(crop, (rx, ry))
        _car_surf["dirty"] = pygame.Rect(rx, ry, rw, rh)
    for t in trees:                                # trees between the camera and the car go over it
        if t[0] < CAM_DIST: blit_tree(screen, t, decal)
