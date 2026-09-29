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

def draw(screen, eyesy):
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
    f = yres * zoom
    ox, oy = xres / 2.0, yres * HORIZON
    kappa = steer * 0.010                                 # how much the tunnel bends
    roll = math.radians(steer * 9 + 1.2 * math.sin(elapsed * 0.7))
    cr, sr = math.cos(roll), math.sin(roll)
    cam_h = CAM_H + 0.12 * math.sin(elapsed * 0.9)

    def V(x, y, z):
        z = max(z, NEAR)
        x += kappa * z * z
        y += 0.35 * math.sin((z + dist) * 0.13) - cam_h   # gentle hills, moving with the world
        sx, sy = f * x / z, -f * y / z
        return (ox + sx * cr - sy * sr, oy + sx * sr + sy * cr)

    def fog(color, z):
        return lerp3(color, haze, clamp((z - 7.0) / (NMOD * PERIOD - 7.0)) ** 1.1 * 0.9)

    def poly(pts3, color, z):
        pts = [V(*p) for p in pts3]
        c = ic(fog(color, z))
        pygame.draw.polygon(screen, c, pts)
        pygame.draw.polygon(screen, ic(lerp3(OUTLINE, haze, clamp((z - 7.0) / 30.0) * 0.8)), pts, 2 if z < 14 else 1)

    # ---- sky, rainbow, sunburst ----
    for y in range(yres):                                  # full-height so a rolled horizon never shows a gap
        t = min(y / max(oy, 1), 1.0) ** 1.5
        pygame.draw.line(screen, ic(lerp3(sky_top, haze, t)), (0, y), (xres, y))
    # everything below the horizon starts as a dark chasm (rolled with the camera)
    big = xres * 3
    p0 = (ox - big * cr, oy - big * sr); p1 = (ox + big * cr, oy + big * sr)
    valley_far = ic(lerp3(haze, pal["valley"], 0.5))
    pygame.draw.polygon(screen, valley_far, [p0, p1, (p1[0] - sr * big, p1[1] + cr * big), (p0[0] - sr * big, p0[1] + cr * big)])

    def rot(px, py):
        dx, dy = px - ox, py - oy
        return (ox + dx * cr - dy * sr, oy + dx * sr + dy * cr)

    sun_r = yres * 0.10
    sun_c = rot(ox, oy - sun_r * 1.2)
    for i, rr in enumerate((3.4, 2.5, 1.8)):                  # stepped glow rings
        pygame.draw.circle(screen, ic(lerp3(haze, pal["sun"], 0.18 + 0.2 * i)), (int(sun_c[0]), int(sun_c[1])), int(sun_r * rr))
    # rainbow: a full half-circle rising from the horizon behind the tunnel, always drawn in full
    # (it is built around the horizon point and rotated with the camera roll, so it never gets cut off)
    band_w = yres * 0.017
    r_top = oy * 0.93                                      # the outer edge stays below the top of the screen
    for i, hh in enumerate((0.0, 0.08, 0.16, 0.36, 0.55, 0.75)):
        r_out = r_top - i * band_w
        r_in = r_out - band_w
        col = lerp3(lerp3(sky_top, haze, 0.5), hsv(hh, 0.55, 1.0), 0.85 + 0.15 * math.sin(elapsed * 1.3 + i))
        outer = [rot(ox + r_out * math.cos(math.pi * j / 48), oy - r_out * math.sin(math.pi * j / 48)) for j in range(49)]
        inner = [rot(ox + r_in * math.cos(math.pi * j / 48), oy - r_in * math.sin(math.pi * j / 48)) for j in range(48, -1, -1)]
        pygame.draw.polygon(screen, ic(col), outer + inner)
    n = 18
    spin = elapsed * 0.25
    burst = []
    pulse = 1.0 + 0.05 * math.sin(elapsed * 2.2)
    for i in range(n * 2):
        a = spin + math.pi * i / n
        rr = sun_r * (1.0 if i % 2 == 0 else 0.72) * pulse
        burst.append((sun_c[0] + rr * math.cos(a), sun_c[1] + rr * math.sin(a)))
    pygame.draw.polygon(screen, ic(pal["sun"]), burst)
    pygame.draw.polygon(screen, OUTLINE, burst, 2)
    pygame.draw.circle(screen, ic(pal["sun_core"]), (int(sun_c[0]), int(sun_c[1])), int(sun_r * 0.5))

    # ---- the tunnel, far to near ----
    for k in range(NMOD, -1, -1):
        gi = base_index + k                               # world index of this bay, so its shape stays put
        z0 = k * PERIOD - phase
        z1 = z0 + PERIOD
        if z1 < NEAR:
            continue
        zm = z0 + PERIOD / 2
        z0c = max(z0, NEAR)

        # path: a dark valley strip with a raised tile on top
        poly([(-PATH_HW, -0.6, z0c), (PATH_HW, -0.6, z0c), (PATH_HW, -0.6, z1), (-PATH_HW, -0.6, z1)], pal["valley"], zm)
        sz0, sz1 = max(z0 + 0.15, NEAR), z0 + PERIOD - 0.45
        if sz1 > NEAR:
            yt = 0.10 * ((gi * 7) % 3) - 0.05
            poly([(-PATH_HW, yt - 0.5, sz0), (PATH_HW, yt - 0.5, sz0), (PATH_HW, yt, sz0), (-PATH_HW, yt, sz0)], shade(pal["path"], 0.62), sz0)
            poly([(-PATH_HW, yt, sz0), (PATH_HW, yt, sz0), (PATH_HW, yt, sz1), (-PATH_HW, yt, sz1)], pal["path"], zm)

        for s in (-1, 1):
            h1, h2, pick = hash01(gi, 3 + s), hash01(gi, 5 + s), hash01(gi, 9)
            yT1 = 0.5 + 0.5 * h1
            yT2 = yT1 + 1.2 + 0.7 * h2
            wall = pal["wall_a"] if pick < 0.5 else pal["wall_b"]

            # outer terrace: tall wall with two round windows
            poly([(s * XB, yT1, z0c), (s * XB, yT2, z0c), (s * XB, yT2, z1), (s * XB, yT1, z1)], shade(wall, 0.85), zm)
            ym = (yT1 + yT2) / 2
            for zc in (z0 + PERIOD * 0.28, z0 + PERIOD * 0.72):
                if zc > NEAR:
                    poly([(s * XB, ym + 0.42 * math.sin(2 * math.pi * i / 12), zc + 0.42 * math.cos(2 * math.pi * i / 12)) for i in range(12)], pal["hole"], zc)
            xc, yT3 = XB + 2.6, yT2 + 2.2 + 1.2 * h1
            poly([(s * xc, yT2, z0c), (s * xc, yT3, z0c), (s * xc, yT3, z1), (s * xc, yT2, z1)], shade(pal["far"], 0.9), zm + 1.0)
            yc3 = (yT2 + yT3) / 2
            if zm > NEAR:
                poly([(s * xc, yc3 + 0.9 * math.sin(2 * math.pi * i / 16), zm + 0.9 * math.cos(2 * math.pi * i / 16)) for i in range(16)], pal["hole"], zm + 1.0)
            if yT2 < cam_h - 0.1:                         # its flat top, when we can see it
                poly([(s * XB, yT2, z0c), (s * (XB + 2.4), yT2, z0c), (s * (XB + 2.4), yT2, z1), (s * XB, yT2, z1)], pal["top"], zm)

            # inner terrace top and front, with the arched opening
            poly([(s * XA, yT1, z0c), (s * XB, yT1, z0c), (s * XB, yT1, z1), (s * XA, yT1, z1)], pal["top"], zm)
            poly([(s * XA, -4.0, z0c), (s * XA, yT1, z0c), (s * XA, yT1, z1), (s * XA, -4.0, z1)], wall, zm)
            a, b = z0 + 0.4, z1 - 0.4
            r_arch = (b - a) / 2
            ys = yT1 - 0.15 - r_arch
            zc = (a + b) / 2
            if b > NEAR:
                arch = [(s * XA, -4.0, a), (s * XA, ys, a)]
                arch += [(s * XA, ys + r_arch * math.sin(math.pi * j / 12), zc - r_arch * math.cos(math.pi * j / 12)) for j in range(1, 12)]
                arch += [(s * XA, ys, b), (s * XA, -4.0, b)]
                poly(arch, pal["hole"], zm)
                xi = s * (XA + 0.9)                            # a second, lighter arch set back inside the opening
                r2 = r_arch * 0.72
                a2, b2, zc2 = zc - r2 + 0.35, zc + r2 + 0.35, zc + 0.35
                inner = [(xi, -4.0, a2), (xi, ys, a2)]
                inner += [(xi, ys + r2 * math.sin(math.pi * j / 12), zc2 - r2 * math.cos(math.pi * j / 12)) for j in range(1, 12)]
                inner += [(xi, ys, b2), (xi, -4.0, b2)]
                poly(inner, pal["jamb"], zm + 0.5)

        # overhead ring every few bays
        if gi % 7 == 0 and z0 > NEAR:
            R_out, R_in, cy = 4.5, 3.9, 1.7
            outer = [(R_out * math.cos(math.pi * j / 26), cy + R_out * math.sin(math.pi * j / 26), z0) for j in range(27)]
            inner = [(R_in * math.cos(math.pi * j / 26), cy + R_in * math.sin(math.pi * j / 26), z0) for j in range(26, -1, -1)]
            poly(outer + inner, pal["portal"], z0)

    # ---- fade in from black when the mode starts ----
    fade = clamp(elapsed / 2.5)
    if fade < 1.0:
        veil = pygame.Surface((xres, yres))
        veil.set_alpha(int(255 * (1 - fade)))
        screen.blit(veil, (0, 0))
