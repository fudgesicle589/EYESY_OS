# Bounce Balls
# Spinning geometric shapes bouncing round the screen, with glowing trails. Every beat they get kicked
# up off the floor, and turning any knob gives them a shove.
# Turn any knob and the picture reacts at once. Tap the `0` key on the beat to sync it by hand
# (on the real device it also locks to the audio kick).
#
# Knob convention (same in every mode):
#   knob1 = size            (shape size)
#   knob2 = main motion     (tempo, 30 to 120 BPM)
#   knob3 = extra detail    (number of shapes, 3 to 24)
#   knob4 = foreground color (hue of the shapes)
#   knob5 = bonus control    (gravity and bounce: floaty and springy up to heavy and thuddy)
import colorsys
import math
import random
import time
import pygame

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))
def ease(t): return t * t * (3 - 2 * t)

def hsv(h, s, v):
    """hue/saturation/value (0..1) to an (r, g, b) tuple; written out by hand because it is called thousands of times a frame"""
    h = (h % 1.0) * 6.0
    s = 0.0 if s < 0.0 else (1.0 if s > 1.0 else s)
    v = 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)
    i = int(h)
    f = h - i
    v255 = v * 255.0
    p = v255 * (1.0 - s)
    q = v255 * (1.0 - f * s)
    t = v255 * (1.0 - (1.0 - f) * s)
    if i == 0: r, g, b = v255, t, p
    elif i == 1: r, g, b = q, v255, p
    elif i == 2: r, g, b = p, v255, t
    elif i == 3: r, g, b = p, q, v255
    elif i == 4: r, g, b = t, p, v255
    else: r, g, b = v255, p, q
    return (int(r), int(g), int(b))

_state = {"beats": 0.0, "last": None, "prev": None, "energy": 0.0, "canvas": None, "fade": None, "size": None, "aux": {}}

def beat_clock(eyesy):
    """a beat counter at the knob's tempo; an audio hit (or the 0 key) snaps it to the next beat,
    and turning any knob adds a burst of 'energy' that fades over about a second"""
    now = time.time()
    if _state["last"] is None:
        _state["last"] = now
    dt = min(now - _state["last"], 0.1)
    _state["last"] = now
    bpm = 30 + eyesy.knob2 * 90
    _state["beats"] += dt * bpm / 60.0
    if getattr(eyesy, "trig", False):
        _state["beats"] = math.floor(_state["beats"]) + 1.0
    ks = (eyesy.knob1, eyesy.knob2, eyesy.knob3, eyesy.knob4, eyesy.knob5)
    prev = _state["prev"]
    move = 0.0 if prev is None else sum(abs(a - b) for a, b in zip(ks, prev))
    _state["prev"] = ks
    _state["energy"] = max(_state["energy"] * math.exp(-dt * 2.5), min(1.0, move * 30.0))
    beats = _state["beats"]
    frac = beats % 1.0
    kick = (1.0 - frac) ** 3
    try:
        level = clamp(max(abs(v) for v in eyesy.audio_in[:100]) / 30000.0)
    except Exception:
        level = 0.0
    energy = _state["energy"]
    return dt, beats, frac, max(kick, level, energy * 0.9), energy

def colors(eyesy):
    fg = eyesy.color_picker(eyesy.knob4)
    h0 = colorsys.rgb_to_hsv(fg[0] / 255.0, fg[1] / 255.0, fg[2] / 255.0)[0]
    bg = hsv(h0 + 0.55, 0.65, 0.10)                            # knob 5 is used for something more fun than the background
    return h0, bg

def canvas_for(eyesy, bg, alpha):
    """a persistent surface that fades toward the background each frame, for glowing trails"""
    xres, yres = eyesy.xres, eyesy.yres
    if _state["size"] != (xres, yres):
        _state["size"] = (xres, yres)
        _state["canvas"] = pygame.Surface((xres, yres))
        _state["canvas"].fill(bg)
        _state["fade"] = pygame.Surface((xres, yres))
    _state["fade"].fill(bg)
    _state["fade"].set_alpha(alpha)
    _state["canvas"].blit(_state["fade"], (0, 0))
    return _state["canvas"]

def setup(screen, eyesy):
    pass

def draw(screen, eyesy):
    xres, yres = eyesy.xres, eyesy.yres
    dt, beats, frac, kick, energy = beat_clock(eyesy)
    h0, bg = colors(eyesy)
    canvas = canvas_for(eyesy, bg, 45)
    balls = _state["aux"].setdefault("balls", [])
    want = 3 + int(eyesy.knob3 * 21.99)
    while len(balls) < want:
        balls.append({"x": random.random() * xres, "y": random.random() * yres * 0.5, "vx": (random.random() - 0.5) * 300,
                      "vy": 0.0, "sides": random.randint(3, 6), "rot": random.random() * 6.28, "spin": (random.random() - 0.5) * 3,
                      "hue": random.random() * 0.7, "rs": 0.6 + random.random() * 0.8})
    del balls[want:]

    bi = int(math.floor(beats))
    if _state["aux"].get("bi") != bi:                         # every beat: a kick up and a sideways scatter
        _state["aux"]["bi"] = bi
        for b in balls:
            b["vy"] = -(600 + 500 * random.random())
            b["vx"] += (random.random() - 0.5) * 500
    if energy > 0.5 and time.time() - _state["aux"].get("shove", 0) > 0.25:      # a big knob turn is a shove
        _state["aux"]["shove"] = time.time()
        for b in balls:
            b["vx"] += (random.random() - 0.5) * 900
            b["vy"] -= 300 * random.random()
    g = 250.0 + 2000.0 * eyesy.knob5                          # gravity
    rest = 0.45 + 0.50 * (1.0 - eyesy.knob5)                  # heavy things thud; floaty things stay bouncy
    for b in balls:
        b["vy"] += g * dt
        b["x"] += b["vx"] * dt
        b["y"] += b["vy"] * dt
        b["rot"] += b["spin"] * dt * (1 + energy * 3)
        b["vx"] *= (1 - 0.35 * dt)
        r = (14 + 46 * eyesy.knob1) * b["rs"]
        if b["x"] < r: b["x"], b["vx"] = r, abs(b["vx"]) * 0.9
        if b["x"] > xres - r: b["x"], b["vx"] = xres - r, -abs(b["vx"]) * 0.9
        if b["y"] > yres - r: b["y"], b["vy"] = yres - r, -abs(b["vy"]) * rest
        if b["y"] < r: b["y"], b["vy"] = r, abs(b["vy"]) * 0.9
        pts = [(b["x"] + r * math.cos(b["rot"] + 2 * math.pi * k / b["sides"]), b["y"] + r * math.sin(b["rot"] + 2 * math.pi * k / b["sides"])) for k in range(b["sides"])]
        pygame.draw.polygon(canvas, hsv(h0 + b["hue"], 0.85, 1.0), pts)
        pygame.draw.polygon(canvas, hsv(h0 + b["hue"] + 0.5, 0.3, 1.0), pts, 3)
    screen.blit(canvas, (0, 0))
