# OGPocketPull
# A cutaway side view of an indoor climbing wall: a big neon pocket hold bolted to the wall, and a climber's hand
# (index + middle finger taped, ring/pinky curled, thumb tucked) reaching in from the left. The fingers slide into
# the slot, the tips drop into the little pit at the back and HOOK it, and then the whole arm loads up with body
# weight: wrist sags, forearm swells, the hold and the bolts glow, chalk blasts out of the mouth of the pocket and
# a shockwave rolls through the gym.
#
# The hand has real mass: it is on a spring, so a flick of the reach knob SLAMS it into the pocket (overshoot,
# bounce, impact), and a slow turn eases it in. Every kick (the 0 key on the desktop) is a body-weight pull.
# Leave the knobs alone for a few seconds and the climber takes over and works the hold on their own.
#
# Knobs (same meaning as every other mode where it fits):
#   knob1 = SIZE      zoom the whole scene. Flick it and the camera punches in and settles.
#   knob2 = REACH     how far the fingers are inside the pocket (0 = hovering well outside, 1 = fully seated).
#                     Flick up to slam the hand in, flick down to rip it back out.
#   knob3 = GRIP      how hard the fingers crimp the back pit, how much weight hangs on the arm, and how much chalk
#                     you shed. Wiggle it for a chalk burst.
#   knob4 = HOLD color (the neon of the pocket, bolts, glow and sparks). Flick it for a flash.
#   knob5 = BACKGROUND color (the gym behind the wall). Flick it and the bokeh lights swing.
import colorsys
import math
import random
import time
import pygame

TAU = math.pi * 2.0
_S = {}

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))
def lerp(a, b, t): return a + (b - a) * t
def smooth(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)

def mix(c1, c2, t):
    t = clamp(t)
    return (int(c1[0] + (c2[0] - c1[0]) * t), int(c1[1] + (c2[1] - c1[1]) * t), int(c1[2] + (c2[2] - c1[2]) * t))

def scale_c(c, k):
    return (int(clamp(c[0] * k, 0, 255)), int(clamp(c[1] * k, 0, 255)), int(clamp(c[2] * k, 0, 255)))

def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, clamp(s), clamp(v))
    return (int(r * 255), int(g * 255), int(b * 255))

# ---------------------------------------------------------------- the world (side view, x right, y DOWN, ~mm-ish units)
# The pocket mouth faces left. The wall plane is at x = WALL_X.
WALL_X = 180.0
WALL_BACK = 265.0
HS = 1.25          # the hand is drawn this much bigger than its local units
UPPER = [(-20, -40), (-34, -68), (-30, -110), (0, -155), (60, -185), (WALL_X, -195), (WALL_X, -38), (135, -38), (60, -41)]
LOWER = [(-20, 40), (50, 43), (56, 82), (125, 84), (135, 66), (135, -38), (WALL_X, -38), (WALL_X, 195),
         (70, 187), (10, 155), (-24, 110), (-30, 67)]
CAVITY = [(-20, -40), (60, -41), (135, -38), (135, 66), (125, 84), (56, 82), (50, 43), (-20, 40)]

# hand-local frame: origin = the knuckle (MCP) of the index finger, +x along the fingers, +y toward the pads (down)
IDX_LEN, IDX_RAD = (50.0, 30.0, 24.0), (11.0, 10.0, 9.0)
MID_LEN, MID_RAD = (56.0, 34.0, 26.0), (11.5, 10.5, 9.5)
WRIST = (-86.0, 2.0)

SKIN = (234, 186, 152)
SKIN_SHADE = (196, 142, 114)
SKIN_BACK = (206, 154, 124)
SKIN_HI = (250, 218, 190)
OUTLINE = (52, 30, 38)
TAPE = (244, 240, 232)

def point_in_poly(x, y, poly):
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi:
            inside = not inside
        j = i
    return inside

def make_glow():
    s = pygame.Surface((128, 128))
    s.fill((0, 0, 0))
    for i in range(64, 0, -1):
        v = int(255 * (1.0 - i / 64.0) ** 2.3)
        pygame.draw.circle(s, (v, v, v), (64, 64), i)
    return s

def build_static():
    rng = random.Random(7)
    speck = []
    for poly in (UPPER, LOWER):
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        n = 0
        while n < 70:
            x, y = rng.uniform(min(xs), max(xs)), rng.uniform(min(ys), max(ys))
            if point_in_poly(x, y, poly):
                speck.append((x, y, rng.uniform(1.2, 2.8), rng.random() < 0.5))
                n += 1
    holds = []
    for y, h, d, k in ((-360, 70, 46, 0), (-262, 40, 30, 1), (-110 - 210, 54, 60, 2), (270, 64, 54, 3), (380, 44, 36, 4),
                       (470, 80, 50, 5), (-450, 60, 52, 6)):
        holds.append((y, h, d, k))
    bokeh = []
    for _ in range(26):
        bokeh.append([rng.uniform(-700, 400), rng.uniform(-330, 330), rng.uniform(12, 52), rng.uniform(4, 16), rng.random()])
    motes = [[rng.uniform(-600, 300), rng.uniform(-300, 300), rng.uniform(0.8, 2.2), rng.uniform(0, TAU)] for _ in range(70)]
    return speck, holds, bokeh, motes

def reset():
    _S.clear()
    speck, holds, bokeh, motes = build_static()
    _S.update(dict(last=None, t=0.0, prev=None, vel=[0.0] * 5, env=[0.0] * 5, mom=[0.0] * 5,
                   r=0.0, rv=0.0, g=0.0, p=0.0, pulse=0.0, shake=0.0, flash=0.0, chalk=0.2, idle=0.0, auto=0.0,
                   fake=0.0, rings=[], parts=[], bursts=[], beat=0.0, hue=0.0,
                   speck=speck, holds=holds, bokeh=bokeh, motes=motes, glow=make_glow(), rng=random.Random(3),
                   zoom_punch=0.0))

def setup(screen, eyesy):
    reset()

def knob_play(eyesy, dt):
    """vel = turning speed, env = 0..1 'being played' ringing out, mom = swing that unwinds after a flick"""
    ks = (eyesy.knob1, eyesy.knob2, eyesy.knob3, eyesy.knob4, eyesy.knob5)
    prev = _S["prev"]
    _S["prev"] = ks
    vel, env, mom = _S["vel"], _S["env"], _S["mom"]
    ring, unwind = math.exp(-dt * 3.0), math.exp(-dt * 1.4)
    for i in range(5):
        delta = 0.0 if prev is None else ks[i] - prev[i]
        raw = delta / dt if dt > 0 else 0.0
        vel[i] += (raw - vel[i]) * min(1.0, dt * 15.0)
        env[i] = max(env[i] * ring, min(1.0, abs(vel[i]) / 1.2))
        mom[i] = mom[i] * unwind + delta
    return vel, env, mom

# ---------------------------------------------------------------- drawing helpers
def glow(screen, cx, cy, radius, color, strength=1.0):
    d = int(radius * 2)
    if d < 4 or strength <= 0.01:
        return
    s = _S["glow"].copy()
    s.fill((int(clamp(color[0] * strength, 0, 255)), int(clamp(color[1] * strength, 0, 255)),
            int(clamp(color[2] * strength, 0, 255))), special_flags=pygame.BLEND_RGB_MULT)
    s = pygame.transform.smoothscale(s, (d, d))
    screen.blit(s, (int(cx - d / 2), int(cy - d / 2)), special_flags=pygame.BLEND_RGB_ADD)

def limb(screen, pts, radii, color):
    """a fat jointed line: round caps and joints, radii per point (screen pixels)"""
    for i in range(len(pts) - 1):
        (ax, ay), (bx, by) = pts[i], pts[i + 1]
        ra, rb = radii[i], radii[i + 1]
        dx, dy = bx - ax, by - ay
        ln = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / ln, dx / ln
        pygame.draw.polygon(screen, color, [(ax + nx * ra, ay + ny * ra), (bx + nx * rb, by + ny * rb),
                                           (bx - nx * rb, by - ny * rb), (ax - nx * ra, ay - ny * ra)])
    for (x, y), r in zip(pts, radii):
        pygame.draw.circle(screen, color, (int(x), int(y)), max(1, int(r)))

def chain(base, lens, angs):
    pts = [base]
    dirs = []
    a = 0.0
    for L, da in zip(lens, angs):
        a += da
        x, y = pts[-1]
        pts.append((x + L * math.cos(a), y + L * math.sin(a)))
        dirs.append(a)
    return pts, dirs

def draw_finger(screen, pts, dirs, rads, U, base, shade, tape_on, chalk, back):
    """pts are already in screen pixels; rads in world units"""
    rp = [r * U * HS for r in rads] + [rads[-1] * 0.85 * U * HS]
    limb(screen, pts, [r + 2.2 for r in rp], OUTLINE)
    limb(screen, pts, rp, base)
    # pad shading on the underside
    sh = []
    for i, (x, y) in enumerate(pts):
        a = dirs[min(i, len(dirs) - 1)]
        sh.append((x - math.sin(a) * rp[i] * 0.42, y + math.cos(a) * rp[i] * 0.42))
    limb(screen, sh, [r * 0.55 for r in rp], shade)
    # top highlight
    hi = []
    for i, (x, y) in enumerate(pts):
        a = dirs[min(i, len(dirs) - 1)]
        hi.append((x + math.sin(a) * rp[i] * 0.45, y - math.cos(a) * rp[i] * 0.45))
    limb(screen, hi, [max(1.0, r * 0.2) for r in rp], mix(base, SKIN_HI, 0.0 if back else 1.0))
    # tape on the proximal phalanx (climbers always tape these)
    if tape_on:
        a, b = pts[0], pts[1]
        t0 = (a[0] + (b[0] - a[0]) * 0.18, a[1] + (b[1] - a[1]) * 0.18)
        t1 = (a[0] + (b[0] - a[0]) * 0.8, a[1] + (b[1] - a[1]) * 0.8)
        tc = scale_c(TAPE, 0.82) if back else TAPE
        limb(screen, [t0, t1], [rp[0] * 1.06, rp[1] * 1.04], tc)
        for f in (0.32, 0.55, 0.74):
            c = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
            dxy = (b[0] - a[0], b[1] - a[1])
            ln = math.hypot(*dxy) or 1.0
            nx, ny = -dxy[1] / ln, dxy[0] / ln
            pygame.draw.line(screen, (190, 186, 178), (c[0] + nx * rp[0] * 0.95, c[1] + ny * rp[0] * 0.95),
                             (c[0] - nx * rp[0] * 0.95, c[1] - ny * rp[0] * 0.95), 1)
    # nail on the back of the distal phalanx
    a, b = pts[2], pts[3]
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy) or 1.0
    ux, uy = dx / ln, dy / ln
    nx, ny = uy, -ux
    n0 = (a[0] + ux * ln * 0.22 + nx * rp[2] * 0.62, a[1] + uy * ln * 0.22 + ny * rp[2] * 0.62)
    n1 = (a[0] + ux * ln * 0.86 + nx * rp[3] * 0.5, a[1] + uy * ln * 0.86 + ny * rp[3] * 0.5)
    limb(screen, [n0, n1], [rp[2] * 0.3, rp[3] * 0.3], (248, 222, 214))
    # chalk dust caked on the tips
    if chalk > 0.02:
        c0 = (a[0] + ux * ln * 0.1, a[1] + uy * ln * 0.1)
        limb(screen, [c0, b], [rp[2] * 0.97, rp[3] * 0.92], mix(base, (255, 255, 255), 0.65 * chalk))

def world_poly(P, poly):
    return [P(x, y) for x, y in poly]

# ---------------------------------------------------------------- the effects
def spawn_chalk(world_pts, n, speed=1.0):
    rng = _S["rng"]
    parts = _S["parts"]
    for _ in range(n):
        if len(parts) > 260:
            break
        x, y = rng.choice(world_pts)
        parts.append([x + rng.uniform(-8, 8), y + rng.uniform(-8, 8), rng.uniform(-260, -20) * speed,
                      rng.uniform(-190, 60) * speed, rng.uniform(0.7, 1.7), 0.0, rng.uniform(2.0, 6.0)])

def impact(power, tips):
    _S["pulse"] = max(_S["pulse"], 0.55 + 0.45 * power)
    _S["shake"] = max(_S["shake"], 0.35 + 0.8 * power)
    _S["flash"] = max(_S["flash"], 0.35 + 0.65 * power)
    _S["chalk"] = clamp(_S["chalk"] + 0.1 + 0.15 * power)
    _S["rings"].append(0.0)
    for _ in range(5 + int(7 * power)):
        a = _S["rng"].uniform(0, TAU)
        _S["bursts"].append([a, _S["rng"].uniform(30, 110) * (0.6 + power), 0.0])
    spawn_chalk(tips + [(-20.0, 0.0)], 10 + int(26 * power), 0.7 + 0.7 * power)

# ---------------------------------------------------------------- draw
def draw(screen, eyesy):
    if not _S:
        reset()
    xres, yres = eyesy.xres, eyesy.yres
    now = time.time()
    if _S["last"] is None:
        _S["last"] = now
    dt = min(max(now - _S["last"], 1e-3), 0.05)
    _S["last"] = now
    _S["t"] += dt
    t = _S["t"]
    rng = _S["rng"]
    vel, env, mom = knob_play(eyesy, dt)

    try:
        level = clamp(max(abs(v) for v in eyesy.audio_in[:100]) / 30000.0)
    except Exception:
        level = 0.0
    beat = False
    if getattr(eyesy, "trig", False):
        beat = True
    # ---- autopilot: when nobody is touching the knobs the climber works the hold alone ----
    moving = max(abs(v) for v in vel) > 0.03
    _S["idle"] = 0.0 if moving else _S["idle"] + dt
    want_auto = 1.0 if _S["idle"] > 5.0 else 0.0
    _S["auto"] += (want_auto - _S["auto"]) * min(1.0, dt * (0.5 if want_auto else 4.0))
    auto = _S["auto"]
    u = (t % 11.0) / 11.0
    if u < 0.35:
        ra = 0.55 * smooth(u / 0.35)
    elif u < 0.8:
        ra = 1.0
    else:
        ra = 1.0 - smooth((u - 0.8) / 0.2)
    if auto > 0.3 and level < 0.03:
        _S["fake"] += dt
        if _S["fake"] > 0.55:           # no music? the climber's own heartbeat pulls on the hold
            _S["fake"] = 0.0
            beat = True
    target = lerp(eyesy.knob2, ra, auto)
    grip_knob = lerp(eyesy.knob3, 0.75, auto * 0.7)

    # ---- reach spring: the hand has weight ----
    r, rv = _S["r"], _S["rv"]
    acc = 150.0 * (target * 1.0 - r) - 15.0 * rv
    rv += acc * dt
    r += rv * dt
    if r > 1.0:
        if rv > 1.4:
            _S["pending_impact"] = min(1.0, rv / 4.5)
        r = 1.0
        rv = -rv * 0.28
    r = clamp(r, -0.04, 1.0)
    _S["r"], _S["rv"] = r, rv
    inside = smooth((r - 0.62) / 0.34)

    # ---- grip + body-weight pull ----
    if beat and inside > 0.5:
        _S["pulse"] = max(_S["pulse"], 0.7 + 0.3 * rng.random())
        _S["shake"] = max(_S["shake"], 0.25)
        _S["flash"] = max(_S["flash"], 0.45)
        _S["rings"].append(0.0)
        _S["chalk"] = clamp(_S["chalk"] + 0.06)
    _S["pulse"] *= math.exp(-dt * 4.0)
    for k, rate in (("shake", 6.0), ("flash", 4.0)):
        _S[k] *= math.exp(-dt * rate)
    _S["chalk"] = max(0.12, _S["chalk"] - dt * 0.02)
    g_t = inside * (0.3 + 0.7 * grip_knob)
    _S["g"] += (g_t - _S["g"]) * min(1.0, dt * (7.0 if g_t > _S["g"] else 3.5))
    p_t = inside * (0.2 + 0.45 * grip_knob + 0.9 * _S["pulse"] + 0.4 * level)
    _S["p"] += (clamp(p_t) - _S["p"]) * min(1.0, dt * 9.0)
    g, p = _S["g"], _S["p"]

    # knob gestures
    zoom = 0.45 + 0.9 * eyesy.knob1 + clamp(mom[0], -0.5, 0.5) * 0.6
    if env[2] > 0.5 and inside > 0.5 and rng.random() < 0.5:
        _S["chalk"] = clamp(_S["chalk"] + 0.01)
    colorful = env[3]
    bg_swing = mom[4]

    # ---- colors ----
    fg = eyesy.color_picker(eyesy.knob4)
    bg = eyesy.color_picker_bg(eyesy.knob5)
    fg_hi = mix(fg, (255, 255, 255), 0.45)
    bg_dark = scale_c(bg, 0.5)
    bg_deep = scale_c(bg, 0.1)

    # ---- camera ----
    U = yres / 400.0 * zoom
    cam_x = -90.0 + 60.0 * (1.0 - r) * 0.8
    shx = (rng.random() - 0.5) * 10.0 * _S["shake"] * U
    shy = (rng.random() - 0.5) * 10.0 * _S["shake"] * U + 4.0 * _S["flash"] * U * 0.2
    ox = xres / 2.0 - cam_x * U + shx
    oy = yres / 2.0 + shy

    def P(x, y):
        return (ox + x * U, oy + y * U)

    # ---- hand pose ----
    wig = (math.sin(t * 8.7) * 0.05 + math.sin(t * 5.3 + 1.0) * 0.04) * (1.0 - 0.8 * g) * (0.4 + 0.6 * (1 - inside))
    hx = lerp(-470.0, 2.0, r)
    hy = -3.0 + (1.0 - r) ** 1.6 * 130.0 + math.sin(t * 1.7) * 5.0 * (1.0 - inside) + p * 5.0
    tilt = -0.10 * p - 0.02 * math.sin(t * 25.0) * p * p
    pivot = (70.0, 12.0)
    ct, st = math.cos(tilt), math.sin(tilt)

    def T(lx, ly):
        dx, dy = (lx - pivot[0]) * HS, (ly - pivot[1]) * HS
        return (hx + pivot[0] * HS + dx * ct - dy * st, hy + pivot[1] * HS + dx * st + dy * ct)

    def finger_world(base_local, lens, mcp, pip, dip):
        pts, dirs = chain(base_local, lens, (mcp, pip, dip))
        return [T(x, y) for x, y in pts], dirs

    idx_w, idx_dirs = finger_world((0.0, 0.0), IDX_LEN, 0.03 + 0.10 * g + wig, 0.16 + 0.95 * g + wig * 1.2, 0.10 + 0.62 * g + wig)
    mid_w, mid_dirs = finger_world((4.0, -3.5), MID_LEN, 0.04 + 0.12 * g - wig * 0.8, 0.22 + 1.00 * g - wig, 0.12 + 0.70 * g - wig * 0.7)
    tilt_dirs = [a + tilt for a in idx_dirs]
    tilt_dirs_m = [a + tilt for a in mid_dirs]
    tips_world = [idx_w[3], mid_w[3]]

    if "pending_impact" in _S:
        impact(_S.pop("pending_impact"), tips_world)

    # ================================================================ background
    bands = 14
    for i in range(bands):
        c = mix(bg_dark, bg_deep, i / (bands - 1.0))
        pygame.draw.rect(screen, c, (0, int(i * yres / bands), xres, int(yres / bands) + 2))
    # bokeh gym lights drift behind the wall
    for b in _S["bokeh"]:
        b[0] -= b[3] * dt * 1.2
        if b[0] < -760:
            b[0] = 420
        bx, by = P(b[0] * 0.7 + cam_x * 0.3, b[1] + math.sin(t * 0.4 + b[4] * 9) * 6)
        c = mix(bg_dark, mix(bg, (255, 255, 255), 0.35), 0.35 + 0.35 * b[4] + 0.2 * abs(bg_swing) * 8)
        pygame.draw.circle(screen, mix(bg_dark, c, 0.3), (int(bx), int(by)), int(b[2] * U))
        pygame.draw.circle(screen, mix(bg_dark, c, 0.7), (int(bx), int(by)), int(b[2] * U), max(1, int(U * 1.2)))
    # floating chalk motes
    for m in _S["motes"]:
        m[0] += math.sin(t * 0.7 + m[3]) * 6.0 * dt
        m[1] -= m[2] * 4.0 * dt
        if m[1] < -330:
            m[1] = 330
            m[0] = rng.uniform(-600, 300)
        mx, my = P(m[0], m[1])
        pygame.draw.circle(screen, mix(bg_dark, (255, 255, 255), 0.35), (int(mx), int(my)), max(1, int(m[2] * U * 0.7)))
    # shockwaves rolling out of the pocket
    rings = _S["rings"]
    for i in range(len(rings) - 1, -1, -1):
        rings[i] += dt
        if rings[i] > 1.3:
            rings.pop(i)
            continue
        rad = rings[i] * 620.0 * U
        k = (1.0 - rings[i] / 1.3) ** 1.5
        cx, cy = P(80.0, 0.0)
        pygame.draw.circle(screen, mix(bg_dark, fg, 0.7 * k), (int(cx), int(cy)), int(rad), max(1, int(5 * U * k)))
        pygame.draw.circle(screen, mix(bg_dark, fg_hi, 0.9 * k), (int(cx), int(cy)), int(rad * 0.97), 1)

    # ================================================================ the wall (a cross-section)
    wx0, wx1 = P(WALL_X, 0)[0], P(WALL_BACK, 0)[0]
    ply = mix(scale_c(bg, 0.5), (92, 70, 54), 0.5)
    pygame.draw.rect(screen, scale_c(ply, 0.55), (int(wx0), 0, int(wx1 - wx0), yres))
    for gx in (0.3, 0.62):                       # plywood layers
        lx = wx0 + (wx1 - wx0) * gx
        pygame.draw.line(screen, scale_c(ply, 0.35), (lx, 0), (lx, yres), 1)
    pygame.draw.rect(screen, ply, (int(wx0), 0, int((wx1 - wx0) * 0.3), yres))
    # T-nut grid: a bolt hole every 90 units
    for yy in range(-900, 901, 90):
        a = P(WALL_X, yy)
        b = P(WALL_BACK, yy)
        if -20 < a[1] < yres + 20:
            pygame.draw.line(screen, (14, 10, 12), a, b, max(1, int(3 * U)))
            pygame.draw.rect(screen, (150, 150, 158), (int(b[0]), int(b[1] - 6 * U), max(2, int(7 * U)), int(12 * U)))
    # framing studs behind the wall
    for sx_, sw in ((WALL_BACK + 24, 34), (WALL_BACK + 150, 34)):
        a = P(sx_, 0)
        pygame.draw.rect(screen, scale_c(ply, 0.35), (int(a[0]), 0, int(sw * U), yres))
        pygame.draw.rect(screen, scale_c(ply, 0.55), (int(a[0]), 0, int(sw * U), yres), 1)
    pygame.draw.rect(screen, mix(bg_dark, (255, 255, 255), 0.0), (int(P(WALL_BACK + 220, 0)[0]), 0, xres, yres))
    # neighbouring holds stuck to the wall (also in section), lit by the beat
    for i, (hy_, hh, hd, k) in enumerate(_S["holds"]):
        col = hsv(0.0 + k * 0.137 + t * 0.02 + eyesy.knob4 * 0.0, 0.75, 0.8)
        face = scale_c(col, 0.35 + 0.35 * _S["flash"])
        pts = [(WALL_X, hy_ - hh / 2), (WALL_X - hd * 0.5, hy_ - hh * 0.5 - 4), (WALL_X - hd, hy_ - hh * 0.25), (WALL_X - hd * 0.9, hy_ + hh * 0.3),
               (WALL_X - hd * 0.3, hy_ + hh * 0.5 + 3), (WALL_X, hy_ + hh / 2)]
        sp = world_poly(P, pts)
        pygame.draw.polygon(screen, face, sp)
        pygame.draw.polygon(screen, mix(face, (255, 255, 255), 0.5), sp, max(1, int(1.5 * U)))
    # wall face edge
    pygame.draw.line(screen, mix(ply, (255, 255, 255), 0.35), (wx0, 0), (wx0, yres), max(1, int(2 * U)))

    # ================================================================ the pocket
    cav = world_poly(P, CAVITY)
    pygame.draw.polygon(screen, (6, 3, 8), cav)
    # inner back wall glows with the pull
    cglow = (0.25 + 0.75 * p) * (0.35 + 0.65 * inside)
    for tp in tips_world:
        sx_, sy_ = P(*tp)
        glow(screen, sx_, sy_, 95 * U, fg, 0.55 * cglow + 0.5 * _S["flash"])
    bx_, by_ = P(120.0, 20.0)
    glow(screen, bx_, by_, 140 * U, fg, 0.35 * cglow + 0.3 * _S["flash"])
    # the bolts that hold it on glow when the hold is loaded
    for byy in (-95, 95):
        a, b = P(40, byy), P(WALL_BACK + 16, byy)
        pygame.draw.line(screen, (30, 28, 34), a, b, max(2, int(10 * U)))
        pygame.draw.line(screen, mix((150, 150, 160), fg_hi, clamp(p + _S["flash"])), a, b, max(1, int(4 * U)))
        nx_, ny_ = P(WALL_BACK + 18, byy)
        glow(screen, nx_, ny_, 40 * U, fg, clamp(p * 1.3 + _S["flash"]) * 0.9)

    # ================================================================ the climber
    # forearm
    wrist = P(*T(*WRIST))
    beta = 0.30 + 0.24 * p + 0.22 * (1.0 - inside) + 0.01 * math.sin(t * 2.0)
    dvx, dvy = -math.cos(beta), math.sin(beta)
    pxn, pyn = dvy, -dvx
    stations = [(0.0, 21.0 * HS), (90.0, (27.0 + 5.0 * p) * HS), (230.0, (33.0 + 6.0 * p) * HS), (760.0, 46.0 * HS)]
    top, bot, mid = [], [], []
    for s, hw in stations:
        cx, cy = wrist[0] + dvx * s * U, wrist[1] + dvy * s * U
        top.append((cx + pxn * hw * U, cy + pyn * hw * U))
        bot.append((cx - pxn * hw * U, cy - pyn * hw * U))
        mid.append((cx, cy))
    out_t = [(x + pxn * 3, y + pyn * 3) for x, y in top]
    out_b = [(x - pxn * 3, y - pyn * 3) for x, y in bot]
    pygame.draw.polygon(screen, OUTLINE, out_t + out_b[::-1])
    pygame.draw.polygon(screen, SKIN, top + bot[::-1])
    pygame.draw.polygon(screen, SKIN_SHADE, mid + bot[::-1])
    hi_line = [(m[0] + (t_[0] - m[0]) * 0.55, m[1] + (t_[1] - m[1]) * 0.55) for m, t_ in zip(mid, top)]
    pygame.draw.lines(screen, SKIN_HI, False, hi_line, max(1, int(3 * U)))
    # tendons stand out under load
    for off in (-0.35, 0.0, 0.3):
        ln = [(m[0] + (t_[0] - m[0]) * off, m[1] + (t_[1] - m[1]) * off) for m, t_ in zip(mid[:3], top[:3])]
        pygame.draw.lines(screen, mix(SKIN, SKIN_SHADE, 0.4 + 0.5 * p), False, ln, 1)
    # wristband
    wb = [(wrist[0] + dvx * s * U, wrist[1] + dvy * s * U) for s in (26, 54)]
    hw0, hw1 = 24.0 * U * HS, 28.0 * U * HS
    band = [(wb[0][0] + pxn * hw0, wb[0][1] + pyn * hw0), (wb[1][0] + pxn * hw1, wb[1][1] + pyn * hw1),
            (wb[1][0] - pxn * hw1, wb[1][1] - pyn * hw1), (wb[0][0] - pxn * hw0, wb[0][1] - pyn * hw0)]
    pygame.draw.polygon(screen, mix(fg, (30, 20, 40), 0.35), band)
    pygame.draw.polygon(screen, fg_hi, band, max(1, int(1.5 * U)))

    UH = U * HS
    # ring + pinky curled under the palm, thumb tucked over them
    def Sp(lx, ly):
        return P(*T(lx, ly))
    cur = [(Sp(-34, 21), 12.5), (Sp(-14, 25), 11.5)]
    for (cx, cy), rr in cur:
        pygame.draw.circle(screen, OUTLINE, (int(cx), int(cy)), int((rr + 2) * UH))
        pygame.draw.circle(screen, SKIN_BACK, (int(cx), int(cy)), int(rr * UH))
    # palm
    palm = [Sp(-86, 0), Sp(-30, -1), Sp(-4, -2)]
    limb(screen, palm, [(24 + 2.3) * UH, (23 + 2.3) * UH, (15 + 2.3) * UH], OUTLINE)
    limb(screen, palm, [24 * UH, 23 * UH, 15 * UH], SKIN)
    limb(screen, [Sp(-80, 11), Sp(-30, 11)], [10 * UH, 10 * UH], SKIN_SHADE)
    kx, ky = Sp(-2, -1)
    pygame.draw.circle(screen, mix(SKIN, SKIN_HI, 0.6), (int(kx), int(ky - 5 * UH)), max(1, int(4 * UH)))
    # thumb
    th = [Sp(-72, 14), Sp(-44, 30), Sp(-14, 33)]
    limb(screen, th, [(11 + 2.2) * UH, (10.5 + 2.2) * UH, (9 + 2.2) * UH], OUTLINE)
    limb(screen, th, [11 * UH, 10.5 * UH, 9 * UH], mix(SKIN, SKIN_HI, 0.3))
    limb(screen, [Sp(-18, 28), Sp(-13, 33)], [4.5 * UH, 4.0 * UH], (248, 222, 214))
    # the two working fingers: middle at the back (a touch darker), index in front
    chalk = _S["chalk"]
    draw_finger(screen, [P(x, y) for x, y in mid_w], tilt_dirs_m, MID_RAD, U,
                SKIN_BACK, scale_c(SKIN_SHADE, 0.9), True, chalk, True)
    draw_finger(screen, [P(x, y) for x, y in idx_w], tilt_dirs, IDX_RAD, U, SKIN, SKIN_SHADE, True, chalk, False)

    # ================================================================ hold material goes over everything that intruded
    dark = mix(scale_c(fg, 0.26), (14, 10, 22), 0.4)
    lit = mix(dark, fg, 0.12 + 0.3 * p + 0.5 * _S["flash"] + 0.25 * colorful)
    for poly, tag in ((UPPER, 0), (LOWER, 1)):
        sp = world_poly(P, poly)
        pygame.draw.polygon(screen, lit, sp)
    for x, y, rr, light in _S["speck"]:
        sx_, sy_ = P(x, y)
        pygame.draw.circle(screen, mix(lit, (255, 255, 255), 0.28) if light else scale_c(lit, 0.6), (int(sx_), int(sy_)), max(1, int(rr * U * 0.6)))
    # cutaway shading: a band of darker volume along the inside of the slot so it reads as a deep hole
    for poly in (UPPER, LOWER):
        sp = world_poly(P, poly)
        pygame.draw.polygon(screen, mix(fg, bg_dark, 0.35), sp, max(5, int(9 * U)))
    for poly in (UPPER, LOWER):
        sp = world_poly(P, poly)
        pygame.draw.polygon(screen, mix(fg, (255, 255, 255), 0.25 + 0.4 * p), sp, max(2, int(3 * U)))
    # a second, fainter neon line inside the outline gives the section some depth
    for poly in (UPPER, LOWER):
        cx0 = sum(q[0] for q in poly) / len(poly)
        cy0 = sum(q[1] for q in poly) / len(poly)
        inner = world_poly(P, [(cx0 + (x - cx0) * 0.88, cy0 + (y - cy0) * 0.88) for x, y in poly])
        pygame.draw.polygon(screen, mix(lit, fg, 0.55), inner, 1)
    # re-lit rim of the slot, the brightest edge on the whole scene
    rim = world_poly(P, [(-20, -40), (60, -41), (135, -38)])
    rim2 = world_poly(P, [(-20, 40), (50, 43), (56, 82), (125, 84), (135, 66)])
    for line in (rim, rim2):
        pygame.draw.lines(screen, fg_hi, False, line, max(2, int(3 * U)))
    # bloom around the whole hold when it's loaded
    ccx, ccy = P(60.0, 0.0)
    glow(screen, ccx, ccy, 330 * U, fg, 0.18 + 0.42 * p + 0.45 * _S["flash"])

    # ---- the hook sparks where the tips bite the pit, plus star bursts ----
    bursts = _S["bursts"]
    for i in range(len(bursts) - 1, -1, -1):
        bursts[i][2] += dt
        if bursts[i][2] > 0.45:
            bursts.pop(i)
            continue
        a, ln, age = bursts[i]
        k = 1.0 - age / 0.45
        cx, cy = P(90.0, 50.0)
        x1, y1 = cx + math.cos(a) * ln * U * (0.4 + age * 2.5), cy + math.sin(a) * ln * U * (0.4 + age * 2.5)
        x0, y0_ = cx + math.cos(a) * ln * U * 0.4 * (0.4 + age * 2.5), cy + math.sin(a) * ln * U * 0.4 * (0.4 + age * 2.5)
        pygame.draw.line(screen, mix(fg, (255, 255, 255), k), (x0, y0_), (x1, y1), max(1, int(3 * U * k)))

    # ---- chalk cloud puffed out of the mouth ----
    parts = _S["parts"]
    for i in range(len(parts) - 1, -1, -1):
        c = parts[i]
        c[5] += dt
        if c[5] > c[4]:
            parts.pop(i)
            continue
        c[3] += 240.0 * dt
        c[2] *= math.exp(-dt * 1.2)
        c[0] += c[2] * dt
        c[1] += c[3] * dt
        k = 1.0 - c[5] / c[4]
        sx_, sy_ = P(c[0], c[1])
        col = mix(bg_dark, (255, 255, 255), 0.25 + 0.75 * k)
        pygame.draw.circle(screen, col, (int(sx_), int(sy_)), max(1, int(c[6] * U * (0.5 + 0.8 * (1 - k)))))

    # ---- flash on a hard hit ----
    if _S["flash"] > 0.5:
        glow(screen, xres / 2, yres / 2, max(xres, yres) * 0.8, fg, (_S["flash"] - 0.5) * 0.4)
