# Vortex Feedback: a screen-on-screen tunnel. Each frame the picture is zoomed and twisted back into
# itself, so paint dropped at the middle is flung into spiral arms. The knobs steer the flow live.
# Sparkles are sprinkled all over the screen so you can watch the zoom and twist react instantly.
#
# Knob convention (same in every mode):
#   knob1 = size            (brush size and how wide the arms swing)
#   knob2 = main motion     (warp: the middle is calm, either end twists and zooms harder, in opposite directions)
#   knob3 = extra detail    (number of arms, 1 to 12, and how many sparkles rain down)
#   knob4 = foreground color (base hue; the trails keep cycling through the rainbow from it)
#   knob5 = background color (what the tunnel fades into)
import colorsys
import math
import random
import time
import pygame

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))

def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, clamp(s), clamp(v))
    return (int(r * 255), int(g * 255), int(b * 255))

_state = {"t": 0.0, "last": None, "buf": None, "size": None, "prev": {}}

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

    bw, bh = max(xres // 2, 64), max(yres // 2, 64)           # the feedback runs at half size: faster, and softer
    bg = tuple(int(c) for c in eyesy.color_picker_bg(eyesy.knob5))
    if _state["size"] != (xres, yres):
        _state["size"] = (xres, yres)
        _state["buf"] = pygame.Surface((bw, bh))
        _state["buf"].fill(bg)
        _state["prev"] = {}
    buf = _state["buf"]

    fg = eyesy.color_picker(eyesy.knob4)
    h0 = colorsys.rgb_to_hsv(fg[0] / 255.0, fg[1] / 255.0, fg[2] / 255.0)[0]

    # ---- knobs ----
    warp = (eyesy.knob2 - 0.5) * 2                            # -1 .. +1
    twist = warp * 6.0                                        # degrees per frame, and which way
    zoom = 1.008 + abs(warp) * 0.07                           # the further from the middle, the harder it rushes in
    arms = 1 + int(eyesy.knob3 * 11.99)
    sparkles = 4 + int(eyesy.knob3 * 60)
    brush = 3 + eyesy.knob1 * 22                              # half-resolution pixels
    swing = 0.55 + eyesy.knob1 * 1.6                          # how far out the arms orbit

    # the whole tunnel drifts around a wandering centre, so it curves
    ox = bw / 2 + bw * 0.14 * math.sin(t * 0.55)
    oy = bh / 2 + bh * 0.14 * math.sin(t * 0.83 + 1.0)

    # ---- feedback: zoom and twist the last frame back into itself ----
    tw = math.radians(abs(twist))
    zoom = max(zoom, (math.cos(tw) + (bw / float(bh)) * math.sin(tw)) * 1.03)     # a hard twist needs a little extra zoom to avoid black corners
    rz = pygame.transform.rotozoom(buf, twist, zoom)
    tx = ox + (bw / 2.0 - ox) * zoom                          # zoom about the wandering centre, still covering the whole screen
    ty = oy + (bh / 2.0 - oy) * zoom
    buf.blit(rz, rz.get_rect(center=(int(tx), int(ty))))
    buf.fill((247, 247, 247), special_flags=pygame.BLEND_RGB_MULT)                                   # fade a little
    buf.fill((int(bg[0] * 0.009), int(bg[1] * 0.009), int(bg[2] * 0.009)), special_flags=pygame.BLEND_RGB_ADD)   # ...toward the background

    # ---- sparkles all over the screen: they get smeared along the flow, so you can see it react at once ----
    for _ in range(sparkles):
        x, y = random.random() * bw, random.random() * bh
        pygame.draw.circle(buf, hsv(h0 + random.random() * 0.4 + t * 0.1, 1.0, 1.0), (int(x), int(y)), 1 + int(brush * 0.15))

    # ---- fresh paint: fat orbiting brushes joined to where they were a moment ago ----
    R = min(bw, bh) * 0.12 * swing * (1.0 + 0.35 * math.sin(t * 0.9))
    for k in range(arms):
        a = t * (1.4 + 0.3 * math.sin(t * 0.3)) + 2 * math.pi * k / arms
        rr = R * (1.0 + 0.4 * math.sin(t * 1.7 + k * 1.3))
        x, y = ox + rr * math.cos(a), oy + rr * math.sin(a)
        hue = h0 + k / arms * 0.5 + t * 0.15                  # the rainbow keeps rolling
        prev = _state["prev"].get(k)
        if prev is not None:
            pygame.draw.line(buf, hsv(hue, 1.0, 1.0), prev, (x, y), max(2, int(brush * 1.6)))
        pygame.draw.circle(buf, hsv(hue, 0.55, 1.0), (int(x), int(y)), max(2, int(brush)))
        _state["prev"][k] = (x, y)
    for k in list(_state["prev"]):
        if k >= arms:
            del _state["prev"][k]
    pygame.draw.circle(buf, hsv(h0 + 0.5, 0.8, 1.0), (int(ox), int(oy)), int(brush * (0.7 + 0.4 * math.sin(t * 3.0))))

    screen.blit(pygame.transform.smoothscale(buf, (xres, yres)), (0, 0))
