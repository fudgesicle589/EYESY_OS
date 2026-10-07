# Beat Rings: on every beat a shockwave ring bursts out of a pulsing core and rolls to the edge of the screen.
# Morph the ring from a triangle up to a circle, thicken it, and change the tempo. Tap `0` to fire one by hand.
#
# Knob convention (same in every mode):
#   knob1 = size            (ring thickness and core size)
#   knob2 = main motion     (tempo, 30 to 120 BPM)
#   knob3 = extra detail    (ring shape: 3 sides, 4, 5 ... up to a smooth circle at the top)
#   knob4 = foreground color (hue; each new ring steps around the color wheel)
#   knob5 = background color
import colorsys
import math
import time
import pygame

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))

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

_state = {"beats": 0.0, "last": None, "rings": [], "spawned": -1, "extra": 0.0}

def beat_clock(eyesy):
    now = time.time()
    if _state["last"] is None:
        _state["last"] = now
    dt = min(now - _state["last"], 0.1)
    _state["last"] = now
    bpm = 30 + eyesy.knob2 * 90                               # a slower, more relaxed tempo range
    ks = (eyesy.knob1, eyesy.knob2, eyesy.knob3, eyesy.knob4, eyesy.knob5)
    prev = _state.get("prev")
    move = 0.0 if prev is None else sum(abs(a - b) for a, b in zip(ks, prev))
    _state["prev"] = ks
    # turning ANY knob throws energy into the picture, and it fades away over about a second
    _state["energy"] = max(_state.get("energy", 0.0) * math.exp(-dt * 2.5), min(1.0, move * 30.0))
    energy = _state["energy"]
    _state["beats"] += dt * bpm / 60.0
    if getattr(eyesy, "trig", False):
        _state["beats"] = math.floor(_state["beats"]) + 1.0
    beats = _state["beats"]
    frac = beats % 1.0
    kick = (1.0 - frac) ** 3
    try:
        level = clamp(max(abs(v) for v in eyesy.audio_in[:100]) / 30000.0)
    except Exception:
        level = 0.0
    return dt, beats, frac, max(kick, level, energy * 0.9), bpm, energy

def setup(screen, eyesy):
    pass

def draw(screen, eyesy):
    xres, yres = eyesy.xres, eyesy.yres
    dt, beats, frac, kick, bpm, energy = beat_clock(eyesy)
    fg = eyesy.color_picker(eyesy.knob4)
    h0 = colorsys.rgb_to_hsv(fg[0] / 255.0, fg[1] / 255.0, fg[2] / 255.0)[0]
    bg = tuple(int(c) for c in eyesy.color_picker_bg(eyesy.knob5))
    screen.fill(bg)

    cx, cy = xres / 2.0, yres / 2.0
    reach = math.hypot(xres, yres) / 2.0
    sides = 3 + int(eyesy.knob3 * 8.99)                       # 3..11, and a true circle at the very top
    circle = eyesy.knob3 > 0.96
    thick = 3 + int(eyesy.knob1 * 26)

    # a ring is born on every whole beat
    b = int(math.floor(beats))
    if b != _state["spawned"]:
        _state["spawned"] = b
        _state["rings"].append({"age": 0.0, "hue": h0 + b * 0.083, "spin": (1 if b % 2 == 0 else -1)})
    if energy > 0.55 and time.time() - _state["extra"] > 0.30:      # a big knob turn fires a ring of its own
        _state["extra"] = time.time()
        _state["rings"].append({"age": 0.0, "hue": h0 + 0.5 + (beats % 1.0) * 0.4, "spin": (-1 if b % 2 == 0 else 1)})
    life = 60.0 / bpm * 3.2                                    # a ring lives a little over three beats
    for r in _state["rings"]:
        r["age"] += dt
    _state["rings"] = [r for r in _state["rings"] if r["age"] < life]

    for r in _state["rings"]:                                  # oldest (largest) first
        u = r["age"] / life
        radius = reach * 1.15 * (1 - (1 - u) ** 2)             # fast at first, then it glides out
        w = max(1, int(thick * (1.0 - u * 0.8)))
        val = 1.0 - u * 0.6
        col = hsv(r["hue"], 0.9 - 0.4 * (1 - u), val)
        if circle:
            pygame.draw.circle(screen, col, (int(cx), int(cy)), int(radius), w)
            pygame.draw.circle(screen, hsv(r["hue"] + 0.5, 0.6, val * 0.8), (int(cx), int(cy)), int(radius * 0.86), max(1, w // 3))
        else:
            rot = r["spin"] * u * 1.2 + math.pi / 2
            pts = [(cx + radius * math.cos(rot + 2 * math.pi * s / sides), cy + radius * math.sin(rot + 2 * math.pi * s / sides)) for s in range(sides)]
            pygame.draw.polygon(screen, col, pts, w)
            pts2 = [(cx + radius * 0.86 * math.cos(rot + 2 * math.pi * s / sides), cy + radius * 0.86 * math.sin(rot + 2 * math.pi * s / sides)) for s in range(sides)]
            pygame.draw.polygon(screen, hsv(r["hue"] + 0.5, 0.6, val * 0.8), pts2, max(1, w // 3))

    core = min(xres, yres) * (0.06 + 0.05 * eyesy.knob1) * (1.0 + 0.55 * kick)      # the core thumps on the kick
    if circle:
        pygame.draw.circle(screen, hsv(h0, 0.25, 1.0), (int(cx), int(cy)), int(core))
    else:
        rot = beats * 0.6
        pygame.draw.polygon(screen, hsv(h0, 0.25, 1.0), [(cx + core * math.cos(rot + 2 * math.pi * s / sides), cy + core * math.sin(rot + 2 * math.pi * s / sides)) for s in range(sides)])
    pygame.draw.circle(screen, hsv(h0 + 0.5, 0.8, 1.0), (int(cx), int(cy)), max(3, int(core * 0.35)))
