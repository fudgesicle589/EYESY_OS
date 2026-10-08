# OG Pong
# Two-player pong with a score. Each knob drives a paddle, so two people can play at once (or you can do both).
# The ball speeds up with every hit, first to 11 wins and the board flashes the winner's color, then restarts.
#
# Knob layout (this mode is a game, so it does NOT follow the usual convention):
#   knob1 = left paddle position
#   knob2 = right paddle position
#   knob3 = left paddle color
#   knob4 = right paddle color
#   knob5 = background color
import math
import random
import time
import pygame

WIN_SCORE = 11
# 7-segment layout for the score digits: a=top b=top-right c=bottom-right d=bottom e=bottom-left f=top-left g=middle
SEGS = {"0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg", "5": "acdfg",
        "6": "acdefg", "7": "abc", "8": "abcdefg", "9": "abcdfg"}

_s = {"last": None, "score": [0, 0], "ball": None, "pause": 0.0, "win": None, "win_t": 0.0, "size": None}

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))

def draw_digit(surf, ch, x, y, w, h, t, color):
    """draw one digit from rectangles; (x, y) is the top-left corner"""
    half = h // 2
    rects = {"a": (x, y, w, t), "b": (x + w - t, y, t, half + t // 2), "c": (x + w - t, y + half - t // 2, t, half + t // 2),
             "d": (x, y + h - t, w, t), "e": (x, y + half - t // 2, t, half + t // 2), "f": (x, y, t, half + t // 2),
             "g": (x, y + half - t // 2, w, t)}
    for seg in SEGS[ch]:
        pygame.draw.rect(surf, color, rects[seg])

def draw_number(surf, n, cx, y, h, color):
    text = str(n)
    w = h // 2
    t = max(3, h // 8)
    gap = t * 2
    total = len(text) * w + (len(text) - 1) * gap
    x = cx - total // 2
    for ch in text:
        draw_digit(surf, ch, x, y, w, h, t, color)
        x += w + gap

def serve(eyesy, toward):
    """put the ball in the middle heading toward player `toward` (0 = left, 1 = right)"""
    ang = (random.random() - 0.5) * 0.8
    sp = eyesy.xres * 0.45
    d = -1 if toward == 0 else 1
    _s["ball"] = {"x": eyesy.xres / 2.0, "y": eyesy.yres / 2.0, "vx": d * sp * math.cos(ang), "vy": sp * math.sin(ang)}
    _s["pause"] = 0.8

def reset(eyesy):
    _s["score"] = [0, 0]
    _s["win"] = None
    serve(eyesy, random.randint(0, 1))

def setup(screen, eyesy):
    _s["last"] = None
    _s["size"] = None

def draw(screen, eyesy):
    xres, yres = eyesy.xres, eyesy.yres
    now = time.time()
    dt = 0.0 if _s["last"] is None else min(now - _s["last"], 0.05)
    _s["last"] = now
    if _s["size"] != (xres, yres):
        _s["size"] = (xres, yres)
        reset(eyesy)

    bg = eyesy.color_picker_bg(eyesy.knob5)
    c_left = eyesy.color_picker(eyesy.knob3)
    c_right = eyesy.color_picker(eyesy.knob4)
    screen.fill(bg)

    # paddles follow their knobs directly
    pw = max(8, xres // 60)
    ph = yres // 5
    margin = xres // 24
    ys = [clamp(eyesy.knob1) * (yres - ph), clamp(eyesy.knob2) * (yres - ph)]
    xs = [margin, xres - margin - pw]

    # ball physics
    ball = _s["ball"]
    r = max(5, xres // 80)
    if _s["win"] is not None:
        _s["win_t"] -= dt
        if _s["win_t"] <= 0:
            reset(eyesy)
    elif _s["pause"] > 0:
        _s["pause"] -= dt
    else:
        ball["x"] += ball["vx"] * dt
        ball["y"] += ball["vy"] * dt
        if ball["y"] < r: ball["y"], ball["vy"] = r, abs(ball["vy"])
        if ball["y"] > yres - r: ball["y"], ball["vy"] = yres - r, -abs(ball["vy"])
        for i in (0, 1):
            hitting = (ball["vx"] < 0) if i == 0 else (ball["vx"] > 0)
            near = (ball["x"] - r <= xs[0] + pw) if i == 0 else (ball["x"] + r >= xs[1])
            inside = ys[i] - r <= ball["y"] <= ys[i] + ph + r
            if hitting and near and inside and xs[0] - pw < ball["x"] < xs[1] + 2 * pw:
                off = (ball["y"] - (ys[i] + ph / 2.0)) / (ph / 2.0)       # -1 top .. 1 bottom
                sp = min(math.hypot(ball["vx"], ball["vy"]) * 1.06, xres * 1.4)
                ang = clamp(off, -1, 1) * 1.755 * 0.5 * 0.9              # up to about 45 degrees
                ball["vx"] = (1 if i == 0 else -1) * sp * math.cos(ang)
                ball["vy"] = sp * math.sin(ang)
                ball["x"] = xs[0] + pw + r if i == 0 else xs[1] - r
        if ball["x"] < -r or ball["x"] > xres + r:                       # someone missed
            scorer = 1 if ball["x"] < 0 else 0
            _s["score"][scorer] += 1
            if _s["score"][scorer] >= WIN_SCORE:
                _s["win"] = scorer
                _s["win_t"] = 3.0
            else:
                serve(eyesy, 1 - scorer)                                 # serve toward the player who just scored

    # centre line
    dash = max(6, yres // 24)
    for y in range(0, yres, dash * 2):
        pygame.draw.rect(screen, (90, 90, 90), (xres // 2 - 2, y, 4, dash))

    # score
    dh = yres // 6
    flash = _s["win"] is not None and int(now * 6) % 2 == 0
    draw_number(screen, _s["score"][0], xres // 4, yres // 20, dh, c_left if not flash or _s["win"] == 0 else (255, 255, 255))
    draw_number(screen, _s["score"][1], xres * 3 // 4, yres // 20, dh, c_right if not flash or _s["win"] == 1 else (255, 255, 255))

    # paddles and ball
    pygame.draw.rect(screen, c_left, (xs[0], int(ys[0]), pw, ph))
    pygame.draw.rect(screen, c_right, (xs[1], int(ys[1]), pw, ph))
    if _s["win"] is None:
        pygame.draw.circle(screen, (255, 255, 255), (int(ball["x"]), int(ball["y"])), r)
