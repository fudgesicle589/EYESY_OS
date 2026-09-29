# Poly Portal: an endless tunnel of nested, twisting shapes with neon edges. You fall in forever.
# Step the sides from triangle to hendecagon, wind the spiral tighter and tighter, and set the speed.
#
# Knob convention (same in every mode):
#   knob1 = size            (zoom: how fast you fall into the tunnel)
#   knob2 = main motion     (twist: 0.5 = straight, left/right = spiral either way, tighter toward the ends)
#   knob3 = extra detail    (number of sides, 3 to 11)
#   knob4 = foreground color (hue that cycles along the tunnel)
#   knob5 = background color (the dark rings between the bright ones)
import colorsys
import math
import time
import pygame

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))

def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, clamp(s), clamp(v))
    return (int(r * 255), int(g * 255), int(b * 255))

_state = {"t": 0.0, "pos": 0.0, "last": None}

def setup(screen, eyesy):
    pass

def draw(screen, eyesy):
    xres, yres = eyesy.xres, eyesy.yres
    now = time.time()
    if _state["last"] is None:
        _state["last"] = now
    dt = min(now - _state["last"], 0.1)
    _state["last"] = now
    _state["t"] += dt

    # ---- knobs ----
    zoom_speed = 0.15 + eyesy.knob1 * 2.2                     # tunnel levels per second
    twist = (eyesy.knob2 - 0.5) * 2 * 0.95                    # radians of extra turn per level
    n = 3 + int(eyesy.knob3 * 8.99)                           # 3..11 sides
    fg = eyesy.color_picker(eyesy.knob4)
    h0 = colorsys.rgb_to_hsv(fg[0] / 255.0, fg[1] / 255.0, fg[2] / 255.0)[0]
    bg = tuple(int(c) for c in eyesy.color_picker_bg(eyesy.knob5))
    dark = tuple(int(c * 0.55) for c in bg)

    _state["pos"] += dt * zoom_speed
    t = _state["t"]
    pos = _state["pos"]
    g = int(math.floor(pos))
    f = pos - g

    cx, cy = xres / 2.0, yres / 2.0
    diag = math.hypot(xres, yres)
    q = 0.84                                                  # each level is this much smaller than the last
    K = 36
    R0 = diag * 0.72 * (1.0 + 0.03 * math.sin(t * 3.0))
    screen.fill(bg)
    sway = (0.05 * xres * math.sin(t * 0.6), 0.05 * yres * math.sin(t * 0.9 + 1.0))    # the tunnel sways a little

    for k in range(K):
        gi = g + k                                            # this level's permanent number, so it keeps its colour as it grows
        r = R0 * q ** (k + 1 - f)
        if r < 3:
            break
        depth = k / K
        ang = gi * twist + t * 0.35
        lit = (gi % 2 == 0)
        fill = hsv(h0 + gi * 0.037, 0.75, 0.95 - 0.35 * depth) if lit else dark
        edge = hsv(h0 + gi * 0.037 + 0.5, 0.6, 1.0)
        ox, oy = cx + sway[0] * depth, cy + sway[1] * depth
        pts = [(ox + r * math.cos(ang + 2 * math.pi * s / n), oy + r * math.sin(ang + 2 * math.pi * s / n)) for s in range(n)]
        pygame.draw.polygon(screen, fill, pts)
        pygame.draw.polygon(screen, edge, pts, max(1, int(min(6, 1 + r * 0.012))))
        if r > 12:
            for pt in pts:
                pygame.draw.circle(screen, edge, (int(pt[0]), int(pt[1])), max(2, int(r * 0.018)))
    pygame.draw.circle(screen, hsv(h0 + 0.5, 0.5, 1.0), (int(cx + sway[0]), int(cy + sway[1])), int(4 + 3 * math.sin(t * 5.0)))
