# Radial Bars
# A circular equalizer: bars ring a thumping core, mirrored left and right. Bass kicks the bars near the
# bottom, hats flicker at the top, and the whole ring slowly turns.
# Turn any knob and the picture reacts at once. Tap the `0` key on the beat to sync it by hand
# (on the real device it also locks to the audio kick).
#
# Knob convention (same in every mode):
#   knob1 = size            (radius of the ring)
#   knob2 = main motion     (tempo, 30 to 120 BPM)
#   knob3 = extra detail    (number of bars, 16 to 96)
#   knob4 = foreground color (hue around the ring)
#   knob5 = bonus control    (swirl: bend the bars into curved turbine blades)
import colorsys
import math
import random
import time
import pygame

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))
def ease(t): return t * t * (3 - 2 * t)

def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, clamp(s), clamp(v))
    return (int(r * 255), int(g * 255), int(b * 255))

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
    screen.fill(bg)
    cx, cy = xres / 2.0, yres / 2.0
    nb = 16 + 2 * int(eyesy.knob3 * 40.99)
    r0 = min(xres, yres) * (0.10 + 0.20 * eyesy.knob1)
    max_len = min(xres, yres) * 0.30
    rot = beats * 0.03 - math.pi / 2
    swirl = eyesy.knob5 * 1.6
    hs, pk = _state["aux"].setdefault("hs", [0.0] * 200), _state["aux"].setdefault("pk", [0.0] * 200)
    try:
        audio = [abs(v) / 30000.0 for v in eyesy.audio_in[:100]]
    except Exception:
        audio = [0.0] * 100
    live = max(audio) > 0.02
    for i in range(nb):
        u = i / float(nb)
        m = min(u, 1.0 - u) * 2.0                              # 0 at the top, 1 at the bottom: the ring is mirrored
        bass = kick * m ** 1.5
        hats = (1.0 - ((beats * 2.0) % 1.0)) ** 2 * (1.0 - m) * 0.8
        wave = 0.5 + 0.5 * math.sin(m * 8.0 - beats * 2.2) * math.sin(m * 3.0 + beats * 0.6)
        jitter = 0.5 + 0.5 * math.sin(i * 12.9898 + beats * 5.0)
        target = clamp(0.10 + 0.85 * bass + 0.5 * hats + 0.35 * wave + energy * 0.6 * jitter)
        if live:
            target = clamp(max(target * 0.35, audio[int(m * 99)] * 1.6))
        hs[i] = max(target, hs[i] - dt * 1.2)
        pk[i] = max(hs[i], pk[i] - dt * 0.5)
        a = rot + 2 * math.pi * u
        ca, sa = math.cos(a), math.sin(a)
        r1 = r0 + 6 + hs[i] * max_len
        half = math.pi * r0 / nb * 0.8
        px, py = -sa * half, ca * half
        a2 = a + swirl * hs[i]                                 # the blade bends further the longer it is
        c2, s2 = math.cos(a2), math.sin(a2)
        qx, qy = -s2 * half, c2 * half
        col = hsv(h0 + m * 0.5, 0.85, 0.55 + 0.45 * hs[i])
        pygame.draw.polygon(screen, col, [(cx + ca * (r0 + 6) + px, cy + sa * (r0 + 6) + py), (cx + c2 * r1 + qx, cy + s2 * r1 + qy),
                                          (cx + c2 * r1 - qx, cy + s2 * r1 - qy), (cx + ca * (r0 + 6) - px, cy + sa * (r0 + 6) - py)])
        rp = r0 + 12 + pk[i] * max_len
        a3 = a + swirl * pk[i]
        pygame.draw.circle(screen, hsv(h0 + m * 0.5, 0.2, 1.0), (int(cx + math.cos(a3) * rp), int(cy + math.sin(a3) * rp)), max(2, int(half * 0.9)))
    pygame.draw.circle(screen, hsv(h0 + 0.5, 0.5, 1.0), (int(cx), int(cy)), int(r0 * (0.75 + 0.30 * kick)), 4)
    pygame.draw.circle(screen, hsv(h0, 0.3, 1.0), (int(cx), int(cy)), int(r0 * (0.28 + 0.22 * kick)))
