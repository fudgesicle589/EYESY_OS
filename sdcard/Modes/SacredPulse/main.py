# OG Sacred Pulse
# EDM main-stage visual in real perspective 3D: you fly down a curving wireframe tunnel of twisting polygons
# (joined ring-to-ring so it reads as a solid lattice), and floating in the middle of it is a spinning 3D sacred
# solid (nested prism + bipyramid), a tilted tumbling Flower of Life disc and orbiting beads. Depth-fogged rainbow
# colors, shockwave rings, reacts to audio (and breathes by itself when it is quiet).
#
# Every knob drives both the tunnel AND the centerpiece; the background is not a knob (dark, tinted by the pattern).
#   knob1 = size    - tunnel width + centerpiece size; a flick punches it in/out and it settles back
#   knob2 = motion  - 0.5 = straight, either way bends the tunnel into curves, twists it and spins the centerpiece;
#                     flicking it whips the tunnel spin
#   knob3 = symmetry - fold 3..12 sides for the tunnel, centerpiece and beads (turning it fires a shockwave)
#   knob4 = color   - base hue (rainbow spreads from it); flicking it strobes brightness
#   knob5 = rotate  - turns the centerpiece (solid, flower disc and beads) around and tumbles it; a flick spins it and it swings back
import math
import time
import colorsys
import pygame

TAU = math.pi * 2.0
ZNEAR, ZOBJ, SPACING = 0.5, 4.2, 0.7
_s = {"t": 0.0, "last": None, "spin": 0.0, "spin2": 0.0, "dist": 0.0, "prev": None, "beat": 0.0, "waves": [],
      "fold": 6, "vel": [0.0] * 5, "env": [0.0] * 5, "mom": [0.0] * 5, "q": 1.0, "avg": 0.0, "geo": None}

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))

def knob_play(eyesy, dt):
    """vel = turning speed, env = 0..1 'being played' ringing out, mom = swing that unwinds after a flick"""
    ks = (eyesy.knob1, eyesy.knob2, eyesy.knob3, eyesy.knob4, eyesy.knob5)
    prev = _s["prev"]
    _s["prev"] = ks
    vel, env, mom = _s["vel"], _s["env"], _s["mom"]
    ring, unwind = math.exp(-dt * 3.0), math.exp(-dt * 1.4)
    for i in range(5):
        delta = 0.0 if prev is None else ks[i] - prev[i]
        raw = delta / dt if dt > 0 else 0.0
        vel[i] += (raw - vel[i]) * min(1.0, dt * 15.0)
        env[i] = max(env[i] * ring, min(1.0, abs(vel[i]) / 1.2))
        mom[i] = mom[i] * unwind + delta
    return vel, env, mom

def setup(screen, eyesy):
    _s["last"] = None
    _s["prev"] = None
    _s["waves"] = []
    _s["geo"] = None

def rainbow(base, shift, bright=1.0):
    h, s, v = base
    r, g, b = colorsys.hsv_to_rgb((h + shift) % 1.0, s, clamp(v * bright))
    return (int(r * 255), int(g * 255), int(b * 255))

def rot(p, ay, ax):
    """rotate a 3D point about Y then X"""
    x, y, z = p
    ca, sa, cb, sb = math.cos(ay), math.sin(ay), math.cos(ax), math.sin(ax)
    x1, z1 = x * ca + z * sa, -x * sa + z * ca
    return (x1, y * cb - z1 * sb, y * sb + z1 * cb)

def solid(n):
    """edges of a nested n-gonal prism + bipyramid (and a smaller counter-twisted copy), as ((x,y,z),(x,y,z)) pairs"""
    edges = []
    for scale, off in ((1.0, 0.0), (0.55, math.pi / n)):
        ring = [(math.cos(off + TAU * i / n) * scale, 0.0, math.sin(off + TAU * i / n) * scale) for i in range(n)]
        top, bot = (0.0, 1.35 * scale, 0.0), (0.0, -1.35 * scale, 0.0)
        for i in range(n):
            a, b = ring[i], ring[(i + 1) % n]
            edges += [(a, b), (top, a), (bot, a)]
            h = 0.8 * scale                                  # prism: top and bottom rings joined by verticals
            at, ab, bt, bb = (a[0], h, a[2]), (a[0], -h, a[2]), (b[0], h, b[2]), (b[0], -h, b[2])
            edges += [(at, bt), (ab, bb), (at, ab)]
    return edges

def draw(screen, eyesy):
    xres, yres = eyesy.xres, eyesy.yres
    cx, cy = xres / 2.0, yres / 2.0
    F = min(xres, yres) * 0.6                                # focal length in pixels
    t0 = time.perf_counter()
    now = time.time()
    dt = 0.016 if _s["last"] is None else clamp(now - _s["last"], 0.001, 0.05)
    _s["last"] = now
    _s["t"] += dt
    t, q = _s["t"], _s["q"]
    vel, env, mom = knob_play(eyesy, dt)

    # ---- audio: real level if there is sound, otherwise a gentle fake kick ----
    try:
        pk = max(abs(v) for v in eyesy.audio_in[:100]) / 32768.0
    except Exception:
        pk = 0.0
    level = clamp(max(pk * 1.6, max(0.0, math.sin(t * 4.2)) ** 6 * 0.5))
    _s["beat"] = max(_s["beat"] * math.exp(-dt * 6.0), level)
    beat = _s["beat"]

    # ---- knobs ----
    size = 0.45 + clamp(eyesy.knob1) * 0.85 + mom[0] * 1.5 + beat * 0.05
    twist = (eyesy.knob2 - 0.5) * 2.0
    amp = abs(twist) * 1.8 + 0.25 * abs(twist) * math.sin(t)  # tunnel curve amount
    _s["spin"] += dt * (0.2 + twist * 1.2 + vel[1] * 0.8)
    _s["spin2"] += dt * (0.5 + abs(twist) * 1.5)
    spin, spin2 = _s["spin"] + mom[1] * 4.0, _s["spin2"]
    speed = 1.2 + beat * 0.6
    _s["dist"] += dt * speed
    D = _s["dist"]
    fold = 3 + int(clamp(eyesy.knob3) * 9.99)
    if fold != _s["fold"]:
        _s["fold"] = fold
        _s["waves"].append(0.0)
        _s["geo"] = None
    if _s["geo"] is None:
        _s["geo"] = solid(fold)
    base = colorsys.rgb_to_hsv(*[c / 255.0 for c in eyesy.color_picker(eyesy.knob4)])
    base = (base[0], max(base[1], 0.85), 1.0)
    strobe = 1.0 + env[3] * 0.7
    spread = 0.6 + eyesy.knob3 * 0.4
    screen.fill(rainbow(base, 0.5, 0.05 + beat * 0.08))

    def path(s):                                              # the tunnel's centerline wiggle
        return amp * math.sin(s * 0.45), amp * 0.7 * math.cos(s * 0.31)
    p0 = path(D)

    def proj(x, y, z, ox, oy):                                # world (relative to camera path) -> screen
        z = max(z, 0.2)
        k = F / z
        return (cx + (x + ox) * k, cy + (y + oy) * k)

    Rt = 3.2 + size * 1.0                                     # tunnel radius (world units)
    N = int(16 * q) + 6
    base_i = int(D / SPACING)
    prev = None
    obj_done = False
    spin_o = clamp(eyesy.knob5) * TAU * 2.0 + mom[4] * 6.0 + spin2 * 0.1   # knob5 turns the centerpiece directly

    def draw_object():
        zo = ZOBJ
        ox, oy = 0.0, 0.0                                     # centerpiece stays centered; the tunnel curves around it
        ay, ax = spin_o, 0.5 + math.sin(spin_o * 0.5) * 0.5 + mom[1]
        sc = size * (1.0 + beat * 0.25)

        def P(pt, ay=ay, ax=ax, sc=sc):
            x, y, z = rot(pt, ay, ax)
            return proj(x * sc, y * sc, zo + z * sc, ox, oy), zo + z * sc
        # tilted Flower of Life disc (19 circles) tumbling like a coin
        fr = 0.33
        segs = 20 if q > 0.5 else 12
        for qa in range(-2, 3):
            for ra in range(-2, 3):
                if abs(qa + ra) > 2:
                    continue
                cxl, cyl = fr * (qa + ra * 0.5), fr * ra * 0.8660254
                dist = max(abs(qa), abs(ra), abs(qa + ra))
                pts = []
                for i in range(segs):
                    a = TAU * i / segs
                    pts.append(P((cxl + math.cos(a) * fr, cyl + math.sin(a) * fr, 0.0), -spin_o * 0.6, 1.1 + math.sin(t * 0.5) * 0.4)[0])
                col = rainbow(base, (0.1 * dist + t * 0.1) % 1.0, strobe)
                pygame.draw.lines(screen, col, True, pts, 1)
        # nested prism + bipyramid, depth-shaded
        for (a, b) in _s["geo"]:
            pa, za = P(a)
            pb, zb = P(b)
            d = clamp(1.3 - (za + zb) * 0.5 / (ZOBJ * 1.4))
            col = rainbow(base, ((a[1] + 1.7) * 0.25 + t * 0.07) % 1.0, strobe * (0.5 + 0.5 * d))
            pygame.draw.line(screen, col, pa, pb, 2 if d > 0.55 else 1)
        # orbiting beads in N-fold symmetry on three tilted orbits
        for orb in range(3):
            for k in range(fold):
                a = spin_o * (1.5 - orb * 0.5) + TAU * k / fold
                pt = (math.cos(a) * (2.0 + orb * 0.5), math.sin(a * 2.0) * 0.3, math.sin(a) * (2.0 + orb * 0.5))
                x, y, z = rot(pt, orb * 1.0, 0.6 * orb + 0.4)
                zc = zo + z * sc
                sp = proj(x * sc, y * sc, zc, ox, oy)
                rad = max(2, int(0.08 * sc * F / max(zc, 0.2) * (1.0 + beat * 0.7)))
                col = rainbow(base, (orb * 0.2 + k / fold * spread + t * 0.08) % 1.0, strobe)
                pygame.draw.circle(screen, col, (int(sp[0]), int(sp[1])), rad)
                pygame.draw.circle(screen, (255, 255, 255), (int(sp[0]), int(sp[1])), max(1, rad // 3))

    # ---- the tunnel, far -> near; the centerpiece is drawn when we pass its depth ----
    ZFAR = N * SPACING
    for m in range(N - 1, -1, -1):
        idx = base_i + m + 1
        s = idx * SPACING
        z = s - D + ZNEAR
        if z < ZNEAR:
            continue
        if not obj_done and z < ZOBJ:
            draw_object()
            obj_done = True
            prev = None if prev is None else prev
        px, py = path(s)
        ox, oy = px - p0[0], py - p0[1]
        near = clamp(1.0 - z / ZFAR)
        a0 = spin + twist * s * 0.35 + (math.pi / fold if idx % 2 else 0.0)
        pts = [proj(math.cos(a0 + TAU * j / fold) * Rt, math.sin(a0 + TAU * j / fold) * Rt, z, ox, oy) for j in range(fold)]
        col = rainbow(base, (idx * 0.06 * spread + t * 0.05) % 1.0, strobe * (0.35 + 0.65 * near))
        w = 1 + int(near * 2.5 * q)
        pygame.draw.polygon(screen, col, pts, w)
        if fold >= 5 and idx % 3 == 0:
            pygame.draw.polygon(screen, rainbow(base, (idx * 0.06 * spread + 0.5) % 1.0, strobe * 0.8 * near),
                                [pts[(j * 2) % fold] for j in range(fold)], 1)
        if prev is not None:                                  # ring-to-ring lattice lines give the real depth feel
            pcol = rainbow(base, (idx * 0.06 * spread + 0.25) % 1.0, strobe * (0.2 + 0.6 * near))
            for j in range(fold):
                pygame.draw.line(screen, pcol, prev[j], pts[j], 1)
        prev = pts
    if not obj_done:
        draw_object()

    # ---- shockwaves from the middle (symmetry change, strong beats) ----
    if beat > 0.8 and (not _s["waves"] or _s["waves"][-1] > 0.35):
        _s["waves"].append(0.0)
    alive = []
    for w in _s["waves"]:
        w += dt * 0.9
        if w < 1.0:
            alive.append(w)
            col = rainbow(base, (w + t * 0.2) % 1.0, 1.0 - w * 0.5)
            pygame.draw.circle(screen, col, (int(cx), int(cy)), max(2, int(w * max(xres, yres) * 0.7)), max(1, int(5 * (1 - w))))
    _s["waves"] = alive[-6:]

    # ---- adaptive quality ----
    dtd = time.perf_counter() - t0
    _s["avg"] = _s["avg"] * 0.9 + dtd * 0.1 if _s["avg"] else dtd
    if _s["avg"] > 0.016:
        _s["q"] = max(0.25, q - 0.04)
    elif _s["avg"] < 0.009:
        _s["q"] = min(1.0, q + 0.01)
