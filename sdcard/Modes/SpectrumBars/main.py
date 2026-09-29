# Spectrum Bars: a chunky LED equalizer, mirrored top and bottom. On its own it dances to a house-style beat;
# on the real device it also listens to the audio input.
# Turn any knob and the picture reacts at once. Tap the `0` key on the beat to sync it by hand (on the real device it locks to the audio kick).
#
# Knob convention (same in every mode):
#   knob1 = size            (bar thickness, from thin slats to solid blocks)
#   knob2 = main motion     (tempo, 30 to 120 BPM)
#   knob3 = extra detail    (number of bars, 8 to 64)
#   knob4 = foreground color (hue that sweeps across the bars)
#   knob5 = background color
import colorsys
import math
import time
import pygame

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))

def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, clamp(s), clamp(v))
    return (int(r * 255), int(g * 255), int(b * 255))

_state = {"beats": 0.0, "last": None, "h": [0.0] * 64, "peak": [0.0] * 64}

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
    return dt, beats, frac, max(kick, level, energy * 0.9), energy

def setup(screen, eyesy):
    pass

def draw(screen, eyesy):
    xres, yres = eyesy.xres, eyesy.yres
    dt, beats, frac, kick, energy = beat_clock(eyesy)
    fg = eyesy.color_picker(eyesy.knob4)
    h0 = colorsys.rgb_to_hsv(fg[0] / 255.0, fg[1] / 255.0, fg[2] / 255.0)[0]
    bg = tuple(int(c) for c in eyesy.color_picker_bg(eyesy.knob5))
    screen.fill(bg)

    nb = 8 + int(eyesy.knob3 * 56.99)
    fill = 0.25 + eyesy.knob1 * 0.72
    slot = xres / float(nb)
    bar_w = max(2, int(slot * fill))
    seg_h = max(6, int(yres * 0.028))                         # each LED block
    gap = max(2, seg_h // 4)
    mid = yres / 2.0
    max_segs = int((yres * 0.46) / (seg_h + gap))

    try:
        audio = [abs(v) / 30000.0 for v in eyesy.audio_in[:100]]
    except Exception:
        audio = [0.0] * 100
    live_audio = max(audio) > 0.02

    hs, pk = _state["h"], _state["peak"]
    for i in range(nb):
        x = i / float(nb - 1)
        # house-style motion: a bass kick on the low bars, off-beat hats on the high ones, and a rolling wave through the middle
        bass = kick * (1.0 - x) ** 1.5
        hats = (1.0 - ((beats * 2.0) % 1.0)) ** 2 * x * 0.8
        wave = 0.5 + 0.5 * math.sin(x * 9.0 - beats * 2.4) * math.sin(x * 3.0 + beats * 0.7)
        jitter = 0.5 + 0.5 * math.sin(i * 12.9898 + beats * 5.0)                         # each bar jumps a little differently
        target = clamp(0.10 + 0.85 * bass + 0.5 * hats + 0.35 * wave + energy * 0.7 * jitter)
        if live_audio:
            target = clamp(max(target * 0.35, audio[int(x * 99)] * 1.6))
        hs[i] = max(target, hs[i] - dt * 1.1)                 # rise instantly, fall smoothly
        pk[i] = max(hs[i], pk[i] - dt * 0.5)                  # the peak cap hangs on a little longer
        segs = int(hs[i] * max_segs)
        left = int(i * slot + (slot - bar_w) / 2.0)
        for s in range(segs):
            hue = h0 + x * 0.5 + s / max_segs * 0.12
            col = hsv(hue, 0.85, 0.55 + 0.45 * (s / max(max_segs, 1)))
            off = s * (seg_h + gap)
            pygame.draw.rect(screen, col, (left, int(mid - 6 - off - seg_h), bar_w, seg_h))       # up from the middle
            pygame.draw.rect(screen, col, (left, int(mid + 6 + off), bar_w, seg_h))               # and mirrored down
        cap = int(pk[i] * max_segs)
        off = cap * (seg_h + gap)
        capc = hsv(h0 + x * 0.5, 0.2, 1.0)
        pygame.draw.rect(screen, capc, (left, int(mid - 6 - off - seg_h), bar_w, max(3, seg_h // 2)))
        pygame.draw.rect(screen, capc, (left, int(mid + 6 + off + seg_h // 2), bar_w, max(3, seg_h // 2)))
