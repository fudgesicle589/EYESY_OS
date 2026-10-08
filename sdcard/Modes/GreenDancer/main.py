# Green dancer crowd: plays back the 127 frames of the client's dancing-alien gif (stored in frames.png, white
# background already cut out), so every alien dances exactly like the original.
# One alien starts in the middle; turning knob 1 adds more (up to 20). New aliens appear in pseudo-random
# spots picked from 40 pre-computed positions that keep the screen balanced. Drop back to 1 alien and bring the
# crowd up again and a brand-new set of 40 spots is generated, so most of the aliens land somewhere new.
# The frames are stored as shading only and tinted at draw time, so the color knob can recolor the aliens.
# No background is drawn; the screen is just whatever the bg color is.
#
# Knobs (this mode's own set, as requested):
#   knob1 = how many aliens  (1 to 20)
#   knob2 = animation speed  (1x is the gif's own speed at the middle of the knob)
#   knob3 = rotation         (spins every alien a full 360 degrees, upright at the starting position; the gif is 2D,
#                             so this turns it in the screen plane)
#   knob4 = color            (hue sweep, starts as the gif's green)
#   knob5 = (unused)
import colorsys
import os
import random
import time
import pygame

GIF_FPS = 20.0                                  # the gif plays at 50 ms per frame
DEFAULT_HUE = 0.257                             # the gif's lime green
MAX_ALIENS = 20
NUM_SLOTS = 40
X_RANGE = (0.08, 0.92)                          # where an alien's centre may sit, as a fraction of the screen
Y_RANGE = (0.28, 0.72)

_S = {"frames": None, "n": 0, "pos": 0.0, "last": None, "w": 0, "h": 0,
      "slots": [(0.5, 0.5)] * NUM_SLOTS, "offsets": [0.0] * NUM_SLOTS, "count": 1, "rng": random.Random()}
_tint = {"key": None, "color": (128, 236, 38), "cache": {}}

def make_slots(rnd):
    """40 well-spread positions (best-candidate sampling: each new spot is the one farthest from the others,
    so the crowd never clumps or leaves holes). Slot 0 is the exact centre: the first alien always starts there."""
    slots = [(0.5, 0.5)]
    while len(slots) < NUM_SLOTS:
        best, best_d = None, -1.0
        for _ in range(60):
            x = rnd.uniform(*X_RANGE)
            y = rnd.uniform(*Y_RANGE)
            d = min(((x - sx) * 1.6) ** 2 + (y - sy) ** 2 for sx, sy in slots)     # x counts more: the screen is wide
            if d > best_d:
                best, best_d = (x, y), d
        slots.append(best)
    return slots

def reshuffle():
    """a whole new set of 40 spots (the centre stays first), in a new random order, with new dance offsets"""
    rng = _S["rng"]
    _S["slots"] = make_slots(rng)
    _S["offsets"] = [0.0] + [rng.uniform(0, _S["n"]) for _ in range(NUM_SLOTS - 1)]

def setup(screen, eyesy):
    here = getattr(eyesy, "mode_root", "") or os.path.dirname(os.path.abspath(__file__))
    if not os.path.exists(os.path.join(here, "frames.png")):
        here = os.path.dirname(os.path.abspath(__file__))
    n, cols, w, h = [int(v) for v in open(os.path.join(here, "frames.txt")).read().split()]
    sheet = pygame.image.load(os.path.join(here, "frames.png")).convert_alpha()
    _S["frames"] = [sheet.subsurface(pygame.Rect((i % cols) * w, (i // cols) * h, w, h)) for i in range(n)]
    _S.update(n=n, w=w, h=h, pos=0.0, last=None, count=1)
    _S["rng"].seed(time.time())
    reshuffle()

def tinted_frame(idx):
    t = _tint["cache"].get(idx)
    if t is None:
        t = _S["frames"][idx].copy()
        t.fill(_tint["color"], special_flags=pygame.BLEND_RGB_MULT)
        _tint["cache"][idx] = t
    return t

def draw(screen, eyesy):
    if _S["frames"] is None:
        setup(screen, eyesy)
    xres, yres = eyesy.xres, eyesy.yres
    now = time.time()
    if _S["last"] is None:
        _S["last"] = now
    dt = min(now - _S["last"], 0.1)
    _S["last"] = now

    # ---- knobs ----
    count = 1 + int(min(eyesy.knob1, 0.999) * MAX_ALIENS)       # 1 .. 20
    speed = 0.1 + eyesy.knob2 * 1.9                             # 0.1x .. 2x the gif's speed (1x at the middle)
    angle = (eyesy.knob3 - 0.2) * 360.0                       # upright at the knob's starting spot (0.2), still a full turn
    hue = (DEFAULT_HUE + (eyesy.knob4 - 0.2)) % 1.0
    eyesy.color_picker_bg(0.0)

    if count == 1 and _S["count"] != 1:                         # back to a single alien: pick new spots for next time
        reshuffle()
    _S["count"] = count

    key = round(hue, 3)
    if _tint["key"] != key:
        r, g, b = colorsys.hsv_to_rgb(hue, 0.74, 0.93)
        _tint.update(key=key, color=(int(r * 255), int(g * 255), int(b * 255)), cache={})

    _S["pos"] = (_S["pos"] + dt * GIF_FPS * speed) % _S["n"]

    # fewer aliens are drawn bigger; lower on the screen means nearer, so a little bigger and drawn on top
    base = yres * 0.86 * count ** -0.28 / _S["h"]
    slots = _S["slots"]
    chosen = sorted(range(count), key=lambda s: slots[s][1])
    for s in chosen:
        sx, sy = slots[s]
        depth = (sy - Y_RANGE[0]) / (Y_RANGE[1] - Y_RANGE[0])
        zoom = base * (0.88 + 0.24 * depth) if s else base
        idx = int(_S["pos"] + _S["offsets"][s]) % _S["n"]
        img = pygame.transform.rotozoom(tinted_frame(idx), angle, zoom)
        screen.blit(img, img.get_rect(center=(int(sx * xres), int(sy * yres))))
