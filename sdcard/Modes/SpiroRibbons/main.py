# Spiro Ribbons: neon spirograph ribbons that react to every knob straight away.
# The ratio knob melts the shape into hundreds of different flowers, the ribbon knob snaps in more
# petals of perfect symmetry, and size changes the line thickness as well as the radius.
#
# Knob convention (same in every mode):
#   knob1 = size            (radius and line thickness)
#   knob2 = main motion     (the spirograph ratio, 1 to 13: sweep it and the whole flower morphs)
#   knob3 = extra detail    (number of ribbons, 1 to 9, spread evenly so they lock into symmetric flowers)
#   knob4 = foreground color (base hue; the ribbons fan out from it)
#   knob5 = background color (also the color the trails fade into)
import colorsys
import math
import time
import pygame

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))

def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, clamp(s), clamp(v))
    return (int(r * 255), int(g * 255), int(b * 255))

_state = {"t": 0.0, "last": None, "canvas": None, "fade": None, "size": None}

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
    t = _state["t"]

    bg = tuple(int(c) for c in eyesy.color_picker_bg(eyesy.knob5))
    if _state["size"] != (xres, yres):
        _state["size"] = (xres, yres)
        _state["canvas"] = pygame.Surface((xres, yres))
        _state["fade"] = pygame.Surface((xres, yres))
    canvas, fade = _state["canvas"], _state["fade"]
    fade.fill(bg)
    fade.set_alpha(80)                                        # short trails, so every change shows right away
    canvas.blit(fade, (0, 0))

    fg = eyesy.color_picker(eyesy.knob4)
    h0 = colorsys.rgb_to_hsv(fg[0] / 255.0, fg[1] / 255.0, fg[2] / 255.0)[0]

    # ---- knobs ----
    R = min(xres, yres) * 0.47 * (0.18 + eyesy.knob1 * 1.05)
    thick = 2 + int(eyesy.knob1 * 6)                          # bigger also means bolder lines
    ratio = 1.0 + eyesy.knob2 * 12.0 + 0.12 * math.sin(t * 0.8)    # a little wobble keeps it alive
    n = 1 + int(eyesy.knob3 * 8.99)

    cx, cy = xres / 2.0, yres / 2.0
    A = R * 0.60
    B = R * (0.40 + 0.06 * math.sin(t * 0.6))
    spin = t * 0.18
    pts_n = 320
    for i in range(n):
        off = i * (2 * math.pi / n)                           # even spacing: n ribbons make an n-fold flower
        pts = []
        for j in range(pts_n):
            u = spin + j * (math.pi * 4 / pts_n)
            v = ratio * u + off * 0.5 + t * 0.35
            pts.append((cx + A * math.cos(u + off * 0.25) + B * math.cos(v), cy + A * math.sin(u + off * 0.25) + B * math.sin(v)))
        hue = h0 + i / n * 0.7 + t * 0.03
        pygame.draw.lines(canvas, hsv(hue, 0.9, 0.55), False, pts, thick + 5)      # glow
        pygame.draw.lines(canvas, hsv(hue, 0.65, 1.0), False, pts, thick)          # bright core
        for j in range(0, pts_n, 40):                                              # beads along the ribbon
            pygame.draw.circle(canvas, hsv(hue + 0.15, 0.3, 1.0), (int(pts[j][0]), int(pts[j][1])), thick + 2)
    screen.blit(canvas, (0, 0))
