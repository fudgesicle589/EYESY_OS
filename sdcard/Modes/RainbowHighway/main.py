# Tesseract Tunnel: a flat-shaded, cel-outlined flight down a tiled path through a terraced
# arcade of arches toward a spiky sunburst. The palette drifts through the spectrum over time.
# An original piece inspired by the look of a live-visuals intro; not a copy of it.
#
# Knob convention (same in every mode):
#   knob1 = size            (zoom: how big the tunnel looms)
#   knob2 = main motion     (steering: the tunnel bends and the camera rolls, 0.5 = straight)
#   knob3 = extra detail    (flight speed)
#   knob4 = foreground color (shifts the colour of the whole tunnel; it also keeps drifting on its own)
#   knob5 = background color (sky tint)
import colorsys
import math
import time
import pygame

# ============================== helpers ==============================

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))
def lerp(a, b, t): return a + (b - a) * t
def lerp3(a, b, t): return (a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t, a[2]+(b[2]-a[2])*t)

def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, clamp(s), clamp(v))
    return (r * 255, g * 255, b * 255)

def ic(c):
    return (int(clamp(c[0], 0, 255)), int(clamp(c[1], 0, 255)), int(clamp(c[2], 0, 255)))

def shade(c, k):
    return (c[0] * k, c[1] * k, c[2] * k)

# ============================== scene constants ==============================

CAM_H = 2.4            # camera height above the path
PERIOD = 3.0           # length of one arch bay
NMOD = 15              # how many bays are drawn ahead of the camera
NEAR = 0.5
HORIZON = 0.40
PATH_HW = 1.25         # half width of the tiled path
XA = 2.1               # first terrace wall
XB = 4.2               # second terrace wall
OUTLINE = (22, 10, 36)

_state = {"t0": None, "last": None, "dist": 0.0}

def hash01(k, salt):
    return ((k * 73856093) ^ (salt * 19349663) ^ (k * salt * 83492791)) % 1000 / 1000.0

# ============================== drawing ==============================

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
    now = time.time()
    if _state["t0"] is None:
        _state["t0"] = _state["last"] = now
    dt = min(now - _state["last"], 0.1)
    _state["last"] = now
    elapsed = now - _state["t0"]

    # ---- knobs ----
    zoom = 0.6 + eyesy.knob1 * 1.6
    steer = (eyesy.knob2 - 0.5) * 2
    speed = 4.0 + eyesy.knob3 * 16.0
    fg = eyesy.color_picker(eyesy.knob4)
    hue = colorsys.rgb_to_hsv(fg[0] / 255.0, fg[1] / 255.0, fg[2] / 255.0)[0]
    h0 = (hue + elapsed * 0.04) % 1.0                     # the palette drifts through the spectrum
    sky_base = eyesy.color_picker_bg(eyesy.knob5)

    _state["dist"] += speed * dt
    dist = _state["dist"]
    phase = dist % PERIOD
    base_index = int(dist // PERIOD)

    # ---- palette ----
    haze = lerp3(shade(sky_base, 0.9), hsv(h0 + 0.85, 0.5, 0.85), 0.45)
    sky_top = lerp3(shade(sky_base, 0.30), hsv(h0 + 0.7, 0.7, 0.25), 0.6)
    pal = {
        "path": hsv(h0 + 0.88, 0.42, 0.92), "valley": hsv(h0 + 0.75, 0.6, 0.20),
        "wall_a": hsv(h0 + 0.55, 0.48, 0.80), "wall_b": hsv(h0 + 0.32, 0.55, 0.80),
        "top": hsv(h0 + 0.10, 0.55, 0.92), "hole": hsv(h0 + 0.72, 0.55, 0.28),
        "jamb": hsv(h0 + 0.08, 0.6, 0.80), "portal": hsv(h0 + 0.62, 0.42, 0.85),
        "far": hsv(h0 + 0.42, 0.5, 0.70),
        "sun": hsv(h0 + 0.14, 0.55, 1.0), "sun_core": hsv(h0 + 0.16, 0.25, 1.0),
    }

    # ---- camera ----
    q = _lod["q"]
    nmod = 6 + int(9 * q)                                 # fewer bays ahead of you when the machine is struggling
    seg_arch = 12 if q > 0.7 else 6
    f = yres * zoom
    ox, oy = xres / 2.0, yres * HORIZON
    kappa = steer * 0.010                                 # how much the tunnel bends
    roll = math.radians(steer * 9 + 1.2 * math.sin(elapsed * 0.7))
    cr, sr = math.cos(roll), math.sin(roll)
    cam_h = CAM_H + 0.12 * math.sin(elapsed * 0.9)
    sin, cos = math.sin, math.cos
    far_z = nmod * PERIOD

    def project(pts3):
        out = []
        for x, y, z in pts3:
            if z < NEAR:
                z = NEAR
            x += kappa * z * z
            y += 0.35 * sin((z + dist) * 0.13) - cam_h    # gentle hills, moving with the world
            sx, sy = f * x / z, -f * y / z
            out.append((ox + sx * cr - sy * sr, oy + sx * sr + sy * cr))
        return out

    def rot(px, py):
        dx, dy = px - ox, py - oy
        return (ox + dx * cr - dy * sr, oy + dx * sr + dy * cr)

    fill_poly = pygame.draw.polygon

    # ---- sky (a few dozen bands rather than a line per pixel), chasm, rainbow, sunburst ----
    bands = 48 if q > 0.6 else 24
    band_h = oy / bands
    for i in range(bands):
        t = ((i + 0.5) / bands) ** 1.5
        pygame.draw.rect(screen, ic(lerp3(sky_top, haze, t)), (0, int(i * band_h), xres, int(band_h) + 2))
    pygame.draw.rect(screen, ic(haze), (0, int(oy), xres, yres - int(oy)))
    big = xres * 3
    p0 = (ox - big * cr, oy - big * sr); p1 = (ox + big * cr, oy + big * sr)
    valley_far = ic(lerp3(haze, pal["valley"], 0.5))
    fill_poly(screen, valley_far, [p0, p1, (p1[0] - sr * big, p1[1] + cr * big), (p0[0] - sr * big, p0[1] + cr * big)])

    sun_r = yres * 0.10
    sun_c = rot(ox, oy - sun_r * 1.2)
    for i, rr in enumerate((3.4, 2.5, 1.8)):                  # stepped glow rings
        pygame.draw.circle(screen, ic(lerp3(haze, pal["sun"], 0.18 + 0.2 * i)), (int(sun_c[0]), int(sun_c[1])), int(sun_r * rr))
    band_w = yres * 0.017
    r_top = oy * 0.93                                      # the rainbow's outer edge stays below the top of the screen
    rseg = 48 if q > 0.6 else 24
    bow_mid = lerp3(sky_top, haze, 0.5)
    for i, hh in enumerate((0.0, 0.08, 0.16, 0.36, 0.55, 0.75)):
        r_out = r_top - i * band_w
        r_in = r_out - band_w
        col = lerp3(bow_mid, hsv(hh, 0.55, 1.0), 0.85 + 0.15 * sin(elapsed * 1.3 + i))
        for half in (0, 1):                                    # the upper half, then the lower half: together a full circle
            a0 = math.pi * half
            outer = [rot(ox + r_out * cos(a0 + math.pi * j / rseg), oy - r_out * sin(a0 + math.pi * j / rseg)) for j in range(rseg + 1)]
            inner = [rot(ox + r_in * cos(a0 + math.pi * j / rseg), oy - r_in * sin(a0 + math.pi * j / rseg)) for j in range(rseg, -1, -1)]
            fill_poly(screen, ic(col), outer + inner)
    n = 18
    spin = elapsed * 0.25
    burst = []
    pulse = 1.0 + 0.05 * sin(elapsed * 2.2)
    for i in range(n * 2):
        a = spin + math.pi * i / n
        rr = sun_r * (1.0 if i % 2 == 0 else 0.72) * pulse
        burst.append((sun_c[0] + rr * cos(a), sun_c[1] + rr * sin(a)))
    fill_poly(screen, ic(pal["sun"]), burst)
    fill_poly(screen, OUTLINE, burst, 2)
    pygame.draw.circle(screen, ic(pal["sun_core"]), (int(sun_c[0]), int(sun_c[1])), int(sun_r * 0.5))

    # ---- the tunnel, far to near ----
    keys = ("valley", "path", "wall_a", "wall_b", "top", "hole", "jamb", "portal", "far")
    for k in range(nmod, -1, -1):
        gi = base_index + k                               # world index of this bay, so its shape stays put
        z0 = k * PERIOD - phase
        z1 = z0 + PERIOD
        if z1 < NEAR:
            continue
        zm = z0 + PERIOD / 2
        z0c = max(z0, NEAR)

        # colours for this bay, fogged once (the haze thickens with distance)
        ff = clamp((zm - 7.0) / (far_z - 7.0)) ** 1.1 * 0.9
        col = {}
        for name in keys:
            c = pal[name]
            col[name] = (int(c[0] + (haze[0] - c[0]) * ff), int(c[1] + (haze[1] - c[1]) * ff), int(c[2] + (haze[2] - c[2]) * ff))
        def dim(c, m): return (int(c[0] * m), int(c[1] * m), int(c[2] * m))
        oa = clamp((zm - 7.0) / 30.0) * 0.8
        outline_c = (int(OUTLINE[0] + (haze[0] - OUTLINE[0]) * oa), int(OUTLINE[1] + (haze[1] - OUTLINE[1]) * oa), int(OUTLINE[2] + (haze[2] - OUTLINE[2]) * oa))
        line_w = 2 if zm < 14 else 1
        outlines = zm < 26 or q > 0.6                     # the far bays are too small for an outline to matter

        def poly(pts3, color):
            pts = project(pts3)
            fill_poly(screen, color, pts)
            if outlines:
                fill_poly(screen, outline_c, pts, line_w)

        # path: a dark valley strip with a raised tile on top
        poly([(-PATH_HW, -0.6, z0c), (PATH_HW, -0.6, z0c), (PATH_HW, -0.6, z1), (-PATH_HW, -0.6, z1)], col["valley"])
        sz0, sz1 = max(z0 + 0.15, NEAR), z0 + PERIOD - 0.45
        if sz1 > NEAR:
            yt = 0.10 * ((gi * 7) % 3) - 0.05
            poly([(-PATH_HW, yt - 0.5, sz0), (PATH_HW, yt - 0.5, sz0), (PATH_HW, yt, sz0), (-PATH_HW, yt, sz0)], dim(col["path"], 0.62))
            poly([(-PATH_HW, yt, sz0), (PATH_HW, yt, sz0), (PATH_HW, yt, sz1), (-PATH_HW, yt, sz1)], col["path"])

        for s_ in (-1, 1):
            h1, h2, pick = hash01(gi, 3 + s_), hash01(gi, 5 + s_), hash01(gi, 9)
            yT1 = 0.5 + 0.5 * h1
            yT2 = yT1 + 1.2 + 0.7 * h2
            wall = col["wall_a"] if pick < 0.5 else col["wall_b"]

            # outer terrace: tall wall with two round windows
            poly([(s_ * XB, yT1, z0c), (s_ * XB, yT2, z0c), (s_ * XB, yT2, z1), (s_ * XB, yT1, z1)], dim(wall, 0.85))
            ym = (yT1 + yT2) / 2
            wseg = 12 if q > 0.7 else 8
            for zc in (z0 + PERIOD * 0.28, z0 + PERIOD * 0.72):
                if zc > NEAR:
                    poly([(s_ * XB, ym + 0.42 * sin(2 * math.pi * i / wseg), zc + 0.42 * cos(2 * math.pi * i / wseg)) for i in range(wseg)], col["hole"])
            xc, yT3 = XB + 2.6, yT2 + 2.2 + 1.2 * h1
            poly([(s_ * xc, yT2, z0c), (s_ * xc, yT3, z0c), (s_ * xc, yT3, z1), (s_ * xc, yT2, z1)], dim(col["far"], 0.9))
            yc3 = (yT2 + yT3) / 2
            if zm > NEAR:
                w3 = 16 if q > 0.7 else 10
                poly([(s_ * xc, yc3 + 0.9 * sin(2 * math.pi * i / w3), zm + 0.9 * cos(2 * math.pi * i / w3)) for i in range(w3)], col["hole"])
            if yT2 < cam_h - 0.1:                         # its flat top, when we can see it
                poly([(s_ * XB, yT2, z0c), (s_ * (XB + 2.4), yT2, z0c), (s_ * (XB + 2.4), yT2, z1), (s_ * XB, yT2, z1)], col["top"])

            # the faces that look back at you where this bay stands taller than the nearer one (otherwise you see right through)
            if z0 > NEAR:
                p1 = 0.5 + 0.5 * hash01(gi - 1, 3 + s_)
                p2 = p1 + 1.2 + 0.7 * hash01(gi - 1, 5 + s_)
                if yT1 > p1:
                    poly([(s_ * XA, p1, z0), (s_ * XB, p1, z0), (s_ * XB, yT1, z0), (s_ * XA, yT1, z0)], dim(wall, 0.7))
                if yT2 > p2:
                    poly([(s_ * XB, p2, z0), (s_ * (XB + 2.6), p2, z0), (s_ * (XB + 2.6), yT2, z0), (s_ * XB, yT2, z0)], dim(wall, 0.7))

            # inner terrace top and front, with the arched opening
            poly([(s_ * XA, yT1, z0c), (s_ * XB, yT1, z0c), (s_ * XB, yT1, z1), (s_ * XA, yT1, z1)], col["top"])
            poly([(s_ * XA, -4.0, z0c), (s_ * XA, yT1, z0c), (s_ * XA, yT1, z1), (s_ * XA, -4.0, z1)], wall)
            a, b = z0 + 0.4, z1 - 0.4
            r_arch = (b - a) / 2
            ys = yT1 - 0.15 - r_arch
            zc = (a + b) / 2
            if b > NEAR:
                arch = [(s_ * XA, -4.0, a), (s_ * XA, ys, a)]
                arch += [(s_ * XA, ys + r_arch * sin(math.pi * j / seg_arch), zc - r_arch * cos(math.pi * j / seg_arch)) for j in range(1, seg_arch)]
                arch += [(s_ * XA, ys, b), (s_ * XA, -4.0, b)]
                poly(arch, col["hole"])
                xi = s_ * (XA + 0.9)                            # a second, lighter arch set back inside the opening
                r2 = r_arch * 0.72
                a2, b2, zc2 = zc - r2 + 0.35, zc + r2 + 0.35, zc + 0.35
                inner = [(xi, -4.0, a2), (xi, ys, a2)]
                inner += [(xi, ys + r2 * sin(math.pi * j / seg_arch), zc2 - r2 * cos(math.pi * j / seg_arch)) for j in range(1, seg_arch)]
                inner += [(xi, ys, b2), (xi, -4.0, b2)]
                poly(inner, col["jamb"])

        # overhead ring every few bays
        if gi % 7 == 0 and z0 > NEAR:
            R_out, R_in, cy = 4.5, 3.9, 1.7
            pseg = 26 if q > 0.6 else 14
            outer = [(R_out * cos(math.pi * j / pseg), cy + R_out * sin(math.pi * j / pseg), z0) for j in range(pseg + 1)]
            inner = [(R_in * cos(math.pi * j / pseg), cy + R_in * sin(math.pi * j / pseg), z0) for j in range(pseg, -1, -1)]
            poly(outer + inner, col["portal"])

    # ---- fade in from black when the mode starts ----
    fade = clamp(elapsed / 2.5)
    if fade < 1.0:
        veil = _state.get("veil")
        if veil is None or veil.get_size() != (xres, yres):
            veil = _state["veil"] = pygame.Surface((xres, yres))
        veil.set_alpha(int(255 * (1 - fade)))
        screen.blit(veil, (0, 0))
