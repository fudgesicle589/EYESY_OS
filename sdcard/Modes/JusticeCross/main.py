# OG Justice Cross
# The Justice cross, wearing their real album art. The crosses are cut out of the album photos and the backgrounds
# are the same photos with the cross painted out (art/; the source photos and the script that made it are in source/). The cross thumps to a
# beat: on every beat it swells a little and throws off an outline of itself that grows and fades out.
#
# Knob mapping (set by request, not the usual convention):
#   knob1 = CROSS look   - every twist (either direction) steps it:  Cross (black + gold)  ->  Audio/Video/Disco
#                          (concrete)  ->  Woman  ->  Hyperdrama
#   knob2 = BACKGROUND   - every twist steps it:  Cross (black with glowing orange dots)  ->  Audio/Video/Disco hillside
#                          ->  Woman liquid  ->  Hyperdrama (black with drifting white glints and rising embers).
#                          Mix and match with knob1. Every background is a square, centred, with black bars at the sides.
#                          Woman cross + Woman background together are the original album art, untouched, until
#                          the beat swells the cross.
#   knob3 = intensity    - how hard it thumps (swell of the cross, brightness and reach of the outlines)
#   knob4 = tempo        - speed of the thump, 60..180 BPM
#   knob5 = (unused)     - the cross stays at the album art's own size, so every pairing keeps lining up
# The pattern always starts on the first album (black cross / black background) wherever the knobs are sitting.
import json
import math
import os
import random
import time
import colorsys
import pygame

TAU = math.pi * 2.0
STEP = 0.08                       # knob travel per look change
NSTYLE = 4
CROSS_NAMES = ("cross", "concrete", "woman", "hyperdrama")
BG_FILES = (None, "bg_concrete.jpg", "bg_woman.jpg", None)
BASE_H = 0.80                     # cross height as a fraction of the screen's short side at default size (the album
                                  # backgrounds' own crosses are 0.74-0.84 of that, so the cross hides them)

_s = {"anchors": {}, "woman_orig": None, "size": None, "art": None, "bgs": None, "dots": None, "glints": None, "embers": None, "overlay": None,
      "acc": [0.0, 0.0], "prev": None, "idx": [0, 0], "last": None, "t": 0.0, "phase": 0.0, "env": 0.0,
      "pulses": []}

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))

def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, clamp(v))
    return (int(r * 255), int(g * 255), int(b * 255))

def art_dir(eyesy):
    here = getattr(eyesy, "mode_root", "") or os.path.dirname(os.path.abspath(__file__))
    if not os.path.isdir(os.path.join(here, "art")):
        here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "art")

def load_cross(root, name, shapes):
    """returns (surface, centre, cross height in px, outline). centre / height / outline come from shapes.json: the outline is
    a clean straight-edged polygon in units of cross height, so the beat outlines have no bumps from glow or fringe"""
    surf = pygame.image.load(os.path.join(root, "cross_%s.png" % name)).convert_alpha()
    sh = shapes[name]
    return surf, tuple(sh["c"]), float(sh["h"]), [tuple(p) for p in sh["outline"]]

def bake_bloom(u):
    """the square background for the Cross album: black with a faint warm glow in the middle"""
    bg = pygame.Surface((u, u))
    bg.fill((0, 0, 0))
    c = u // 2
    for i in range(34, 0, -1):
        f = i / 34.0
        pygame.draw.circle(bg, (int(46 * (1 - f) ** 2), int(18 * (1 - f) ** 2), int(6 * (1 - f) ** 3)),
                           (c, int(u * 0.52)), int(u * 0.62 * f))
    return bg

def bake_all(eyesy, w, h):
    root = art_dir(eyesy)
    with open(os.path.join(root, "shapes.json")) as f:
        shapes = json.load(f)
    _s["art"] = [load_cross(root, n, shapes) for n in CROSS_NAMES]
    try:                                               # where each cross sat in its own album art (centre x, y, height)
        with open(os.path.join(root, "anchors.json")) as f:
            _s["anchors"] = json.load(f)
    except (IOError, ValueError):
        _s["anchors"] = {}
    u0 = min(w, h)
    orig = pygame.Surface((w, h))
    orig.fill((0, 0, 0))
    pic = pygame.image.load(os.path.join(root, "bg_woman_original.jpg")).convert()
    orig.blit(pygame.transform.smoothscale(pic, (u0, u0)), ((w - u0) // 2, (h - u0) // 2))
    _s["woman_orig"] = orig.convert()
    u = min(w, h)
    ox, oy = (w - u) // 2, (h - u) // 2
    bgs = []
    for i, f in enumerate(BG_FILES):                   # every background is a square, centred, with black bars
        bg = pygame.Surface((w, h))
        bg.fill((0, 0, 0))
        if f:
            pic = pygame.image.load(os.path.join(root, f)).convert()
            bg.blit(pygame.transform.smoothscale(pic, (u, u)), (ox, oy))
        elif i == 0:
            bg.blit(bake_bloom(u), (ox, oy))
        bgs.append(bg.convert())
    _s["bgs"] = bgs
    _s["size"] = (w, h)
    _s["overlay"] = pygame.Surface((w, h), pygame.SRCALPHA)
    r2 = random.Random(7)
    _s["dots"] = [[r2.random(), r2.random(), r2.uniform(0.04, 0.12), r2.random() * TAU] for _ in range(70)]
    _s["glints"] = [[r2.random(), r2.random(), r2.uniform(0.01, 0.035), r2.random() * TAU, r2.uniform(5, 18)]
                    for _ in range(56)]
    _s["embers"] = [[r2.random(), r2.random(), r2.uniform(0.05, 0.16), r2.random() * TAU] for _ in range(22)]

def draw_dots(screen, t, ox, oy, u):
    """Cross album: glowing orange dots twinkling and drifting up"""
    for sx, sy, sz, ph in _s["dots"]:
        tw = 0.5 + 0.5 * math.sin(t * 2.2 + ph)
        x = ox + int((sx + 0.02 * math.sin(t * 0.3 + ph)) * u)
        y = oy + int(((sy - t * sz * 0.1) % 1.0) * u)
        c = int(60 + 190 * tw)
        pygame.draw.circle(screen, (c, int(c * 0.7), int(c * 0.45)), (x, y), 1 + int(tw * 1.5))

def draw_glints(screen, t, ox, oy, u):
    """Hyperdrama: cool white four-point glints flaring like light on glass, plus a few orange embers rising"""
    for sx, sy, sz, ph, r in _s["glints"]:
        tw = max(0.0, math.sin(t * 1.3 + ph)) ** 3                 # mostly dim, flares briefly
        if tw < 0.04:
            continue
        x = ox + (sx + 0.01 * math.sin(t * 0.2 + ph)) * u
        y = oy + ((sy - t * sz * 0.1) % 1.0) * u
        ln = r * (0.4 + tw)
        c = (int(150 + 105 * tw), int(170 + 85 * tw), 255)
        dim = (c[0] // 2, c[1] // 2, c[2] // 2)
        pygame.draw.line(screen, dim, (x - ln, y), (x + ln, y), 1)
        pygame.draw.line(screen, dim, (x, y - ln), (x, y + ln), 1)
        pygame.draw.line(screen, c, (x - ln * 0.45, y), (x + ln * 0.45, y), 1)
        pygame.draw.line(screen, c, (x, y - ln * 0.45), (x, y + ln * 0.45), 1)
        pygame.draw.circle(screen, (255, 255, 255), (int(x), int(y)), 1 + int(tw * 1.5))
    for sx, sy, sp, ph in _s["embers"]:
        prog = (sy - t * sp * 0.25) % 1.0                           # 1 at the bottom, 0 at the top
        x = ox + (sx + 0.03 * math.sin(t * 0.8 + ph)) * u
        y = oy + prog * u
        a = clamp(prog * 1.6) * clamp((1.0 - prog) * 6.0)           # fade in from the top, out toward the bottom
        c = (int(255 * a), int(130 * a), int(30 * a))
        pygame.draw.circle(screen, c, (int(x), int(y)), 2)

def setup(screen, eyesy):
    _s["size"] = None
    _s["prev"] = None
    _s["acc"] = [0.0, 0.0]
    _s["idx"] = [0, 0]
    _s["last"] = None
    _s["pulses"] = []
    _s["phase"] = 0.0
    _s["env"] = 0.0

def ring_color(style, age, t):
    if style == 0: return (222, 182, 60)
    if style == 1: return (225, 224, 216)
    if style == 2: return hsv(t * 0.15 + age * 0.5, 0.55, 1.0)
    return (255, 160 + int(70 * (1 - age)), 80 + int(120 * (1 - age)))

def draw(screen, eyesy):
    w, h = eyesy.xres, eyesy.yres
    if _s["size"] != (w, h):
        bake_all(eyesy, w, h)
    now = time.time()
    dt = 1 / 30.0 if _s["last"] is None else clamp(now - _s["last"], 0.001, 0.1)
    _s["last"] = now
    _s["t"] += dt
    t = _s["t"]

    # --- knobs: twists step the looks (relative to wherever the knobs started, so we always begin on album 1)
    ks = (eyesy.knob1, eyesy.knob2)
    if _s["prev"] is not None:
        for i in range(2):
            _s["acc"][i] = clamp(_s["acc"][i] + ks[i] - _s["prev"][i], 0.0, STEP * NSTYLE - 1e-4)
    _s["prev"] = ks
    changed = False
    for i in range(2):
        n = int(_s["acc"][i] / STEP)
        if n != _s["idx"][i]:
            _s["idx"][i] = n
            changed = True
    style, bgi = _s["idx"]
    inten = clamp(eyesy.knob3)
    bpm = 60.0 + 120.0 * clamp(eyesy.knob4)
    size = 0.5                                                   # fixed: the cross is always the album art's own size

    # --- beat clock
    prev_beat = int(_s["phase"])
    _s["phase"] += dt * bpm / 60.0
    beat = int(_s["phase"]) != prev_beat
    if beat or changed:
        _s["env"] = 1.0
        _s["pulses"].append(0.0)
    _s["env"] *= math.exp(-dt * 7.0)
    life = 0.9 + 0.5 * inten
    _s["pulses"] = [a + dt / life for a in _s["pulses"] if a + dt / life < 1.0]
    env = _s["env"]

    # --- Woman cross on Woman art: put the cross back where it was in the album art
    u = min(w, h)
    cross_px = u * BASE_H * (0.55 + 0.9 * size)                  # on-screen height of the cross at rest
    cx0, cy0 = w * 0.5, h * 0.5
    anchor = _s["anchors"].get("woman") if (style == 2 and bgi == 2) else None
    on_original = False
    if anchor:
        cx0, cy0 = (w - u) // 2 + anchor[0] * u, (h - u) // 2 + anchor[1] * u
        cross_px = anchor[2] * u * (0.55 + 0.9 * size)
        on_original = True                                       # the cross only ever swells, so it covers the art's own

    # --- background
    screen.blit(_s["woman_orig"] if on_original else _s["bgs"][bgi], (0, 0))
    if bgi == 0:
        draw_dots(screen, t, (w - u) // 2, (h - u) // 2, u)
    elif bgi == 3:
        draw_glints(screen, t, (w - u) // 2, (h - u) // 2, u)

    # --- cross, centred on the screen
    art, (acx, acy), art_h, outline = _s["art"][style]
    amp = 0.012 + 0.14 * inten
    swell = 1.0 + amp * env

    # outlines thrown off by each beat
    if _s["pulses"]:
        ov = _s["overlay"]
        ov.fill((0, 0, 0, 0))
        reach = 0.12 + 0.55 * inten
        for a in _s["pulses"]:
            sc = cross_px * swell * (1.0 + reach * (1 - (1 - a) ** 2))
            alpha = int(255 * (1 - a) ** 1.6 * (0.35 + 0.65 * inten))
            col = ring_color(style, a, t) + (alpha,)
            pygame.draw.polygon(ov, col, [(cx0 + x * sc, cy0 + y * sc) for x, y in outline], max(2, int(h / 180)))
        screen.blit(ov, (0, 0))

    k = cross_px * swell / art_h                                 # art px -> screen px
    aw, ah = art.get_size()
    scaled = pygame.transform.smoothscale(art, (max(2, int(aw * k)), max(2, int(ah * k))))
    if style == 3 and env > 0.02:                                # the glass lights up on the beat
        v = int(110 * env * (0.3 + inten))
        glow = scaled.copy()
        glow.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
        scaled.blit(glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    screen.blit(scaled, (int(cx0 - acx * k), int(cy0 - acy * k)))
