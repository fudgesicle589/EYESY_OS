# Kaleido Bloom: glowing petals, orbs and ribbons orbit inside a live kaleidoscope with mirrored wedges.
# Turn the segment knob and the whole flower re-folds itself; spin it either way; make it huge or tiny.
#
# Knob convention (same in every mode):
#   knob1 = size            (how big the petals and orbs are)
#   knob2 = main motion     (spin the kaleidoscope: 0.5 = still, left/right = spin either way, faster toward the ends)
#   knob3 = extra detail    (number of mirrored wedges, 4 to 18)
#   knob4 = foreground color (hue of the whole bloom)
#   knob5 = background color (also the color the trails fade into)
import colorsys
import math
import time
import pygame

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))

def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, clamp(s), clamp(v))
    return (int(r * 255), int(g * 255), int(b * 255))

_state = {"t": 0.0, "rot": 0.0, "last": None, "canvas": None, "fade": None, "size": None}

def setup(screen, eyesy):
    pass

def draw(screen, eyesy):
    xres, yres = eyesy.xres, eyesy.yres
    now = time.time()
    if _state["last"] is None:
        _state["last"] = now
    dt = min(now - _state["last"], 0.1)
    _state["last"] = now

    fg = eyesy.color_picker(eyesy.knob4)
    h0 = colorsys.rgb_to_hsv(fg[0] / 255.0, fg[1] / 255.0, fg[2] / 255.0)[0]
    bg = tuple(int(c) for c in eyesy.color_picker_bg(eyesy.knob5))

    if _state["size"] != (xres, yres):
        _state["size"] = (xres, yres)
        _state["canvas"] = pygame.Surface((xres, yres))
        _state["canvas"].fill(bg)
        _state["fade"] = pygame.Surface((xres, yres))

    # ---- knobs ----
    spin = (eyesy.knob2 - 0.5) * 2 * 1.6                     # radians per second
    _state["rot"] += spin * dt
    _state["t"] += dt * (0.7 + abs(spin) * 0.6)              # the petals swirl faster when you spin harder
    t, rot = _state["t"], _state["rot"]
    pairs = 2 + int(eyesy.knob3 * 7.99)                       # 2..9 mirrored pairs = 4..18 wedges
    size = 0.35 + eyesy.knob1 * 1.3

    canvas = _state["canvas"]
    fade = _state["fade"]
    fade.fill(bg)
    fade.set_alpha(36)                                        # a soft trail
    canvas.blit(fade, (0, 0))

    cx, cy = xres / 2.0, yres / 2.0
    R = min(xres, yres) * 0.5
    unit = R / 360.0

    # the petals: each one wanders in and out along its own orbit
    E = 16
    els = []
    for i in range(E):
        rr = R * (0.10 + 0.85 * (0.5 + 0.5 * math.sin(t * (0.5 + 0.09 * i) + i * 1.9)))
        aa = t * (0.35 + 0.06 * i) + i * 0.71
        s = (6 + 26 * (0.5 + 0.5 * math.sin(t * 1.3 + i))) * size * unit * 1.6
        els.append((rr, aa, s, hsv(h0 + i * 0.05 + t * 0.04, 0.85, 1.0), hsv(h0 + i * 0.05 + t * 0.04, 0.35, 1.0)))

    for m in range(pairs):
        base = rot + 2 * math.pi * m / pairs
        for mirror in (1, -1):
            pos = []
            for rr, aa, s, c1, c2 in els:
                a = base + mirror * aa
                pos.append((cx + rr * math.cos(a), cy + rr * math.sin(a), a))
            for i in range(E - 1):                              # ribbons between neighbouring petals
                if i % 2 == 0:
                    pygame.draw.line(canvas, els[i][3], pos[i][:2], pos[i + 1][:2], max(1, int(2 * size)))
            for i, (rr, aa, s, c1, c2) in enumerate(els):
                x, y, a = pos[i]
                ux, uy = math.cos(a), math.sin(a)
                vx, vy = -uy, ux
                pygame.draw.polygon(canvas, c1, [(x + ux * s * 2.2, y + uy * s * 2.2), (x + vx * s * 0.8, y + vy * s * 0.8),
                                                 (x - ux * s, y - uy * s), (x - vx * s * 0.8, y - vy * s * 0.8)])
                pygame.draw.circle(canvas, c2, (int(x), int(y)), max(2, int(s * 0.55)))

    pulse = 0.5 + 0.5 * math.sin(t * 2.0)                     # a beating core
    pygame.draw.circle(canvas, hsv(h0 + 0.5, 0.6, 1.0), (int(cx), int(cy)), int((10 + 22 * pulse) * size * unit * 1.6))
    pygame.draw.circle(canvas, hsv(h0, 0.2, 1.0), (int(cx), int(cy)), int((4 + 8 * pulse) * size * unit * 1.6))
    screen.blit(canvas, (0, 0))
