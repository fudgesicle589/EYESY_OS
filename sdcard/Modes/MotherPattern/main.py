# OGMotherPattern  --  the mother of all patterns. Overstimulating on purpose. Fried on purpose.
#
# How it works: everything is drawn into a small private canvas that is fed back into itself every frame (zoomed,
# spun, faded, colour-rotated), so whatever gets drawn smears into tunnels, vortexes and melting trails. Then it is
# blown up to the screen with hard pixels. On top of that, every knob is a SELECTOR as well as a dial.
#
# Each knob's travel is cut into 7 zones. Each zone is a completely different effect, and where you sit INSIDE the
# zone is how much / how fast / which flavour. So a tiny nudge can swap the whole look. Nothing is labelled on
# screen: just twist stuff and see. The LAST zone of every knob (the final ~14%, "turning it too far") is a
# different door into the CAT DIMENSION, each one weirder than the last. The doors fade in and out smoothly, and
# you can open several at once.
#
#   knob1 = WARP     how the picture feeds back into itself
#                    zoom in | zoom out | vortex | breathing | drunk drift | mirror fold | CAT TUNNEL
#   knob2 = SOURCE   what fresh stuff gets injected each frame
#                    rings | lissajous scribble | spinning polygons | sound scope | rays | shape rain | CAT RAIN
#   knob3 = BREAK    what gets done to the picture
#                    wobble | pixelate | RGB split | mirror | tear | scanline smear | CAT KALEIDOSCOPE
#   knob4 = COLOUR   palette and colour behaviour
#                    rainbow | your colour (inside the zone, the knob picks the colour) | acid duo | fire | ice |
#                    beat strobe | CAT NEGATIVE (a giant cat flashes on the beat and the world inverts)
#   knob5 = CHAOS    the junk laid on top
#                    colour wash | TV static | tiled screens | bouncing words | googly eyes | invert bands | CAT TAKEOVER
#
# Playing it: turn a knob FAST and the whole screen shakes and flashes (the faster, the harder). On every sound
# trigger (the 0 key on the desktop) there's a beat: things pop, and sometimes a random glitch fires. With no sound
# input at all it keeps its own beat so it never sits still.
#
# The cat photos in cats/ are public domain or CC0 pictures from Wikimedia Commons.
import colorsys
import math
import os
import random
import time
import pygame

NZ = 7                                    # zones per knob (the last one is the cat zone)
BW = 640                                  # width of the private canvas; the height follows the screen's shape
WORDS = ("MEOW", "FRIED", "OVERLOAD", "WHAT", "NYA", "MAX", "???", "CAT", "DIMENSION", "!!!", "PURR", "HELP")

S = {}                                    # all the mode's state lives here


def clamp(v, lo=0.0, hi=1.0): return lo if v < lo else (hi if v > hi else v)


def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, clamp(s), clamp(v))
    return (int(r * 255), int(g * 255), int(b * 255))


def zone(v):
    z = min(NZ - 1, int(clamp(v) * NZ))
    return z, clamp(v) * NZ - z


# ---------------------------------------------------------------------------------------------------- cats
def _make_cats(here):
    cats, covers = [], []
    folder = os.path.join(here, "cats")
    names = sorted(f for f in os.listdir(folder) if f.lower().endswith((".jpg", ".png"))) if os.path.isdir(folder) else []
    for f in names:
        try:
            raw = pygame.image.load(os.path.join(folder, f)).convert()
        except Exception:
            continue
        # a soft-edged oval head for the sprites
        h = 256
        w = max(32, int(raw.get_width() * h / raw.get_height()))
        img = pygame.transform.smoothscale(raw, (w, h)).convert_alpha()
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(12):
            r = pygame.Rect(0, 0, w, h).inflate(-i * w * 0.035, -i * h * 0.035)
            pygame.draw.ellipse(mask, (255, 255, 255, int(255 * (i + 1) / 12)), r)
        img.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        cats.append(img)
        covers.append(raw)
    return cats, covers


def _cover(i):
    """the whole photo, scaled and cropped to fill the canvas (made when first needed)"""
    c = S["cover_cache"].get(i)
    if c is None:
        raw = S["covers"][i % len(S["covers"])]
        k = max(BW / raw.get_width(), S["bh"] / raw.get_height())
        big = pygame.transform.smoothscale(raw, (int(raw.get_width() * k) + 1, int(raw.get_height() * k) + 1))
        c = big.subsurface(((big.get_width() - BW) // 2, (big.get_height() - S["bh"]) // 2, BW, S["bh"])).copy()
        S["cover_cache"][i] = c
    return c


def stamp(dst, i, cx, cy, h, ang=0.0, tint=None, alpha=255):
    """draw one oval cat head, centred, h pixels tall, optionally spun / tinted / see-through"""
    cats = S["cats"]
    if not cats: return
    h = clamp(h, 6, S["bh"] * 3)
    base = cats[int(i) % len(cats)]
    z = h / base.get_height()
    s = pygame.transform.rotozoom(base, ang, z)
    if tint is not None:
        s.fill(tint, special_flags=pygame.BLEND_RGB_MULT)
    if alpha < 255:
        s.set_alpha(int(alpha))
    dst.blit(s, (int(cx - s.get_width() / 2), int(cy - s.get_height() / 2)))


# ---------------------------------------------------------------------------------------------------- helpers
def pal(x, v=1.0):
    """a colour from the current palette; x is any number, it wraps"""
    z, t, tm = S["z"][3], S["t"][3], S["time"]
    x = x % 1.0
    if z == 0 or z == 6:
        return hsv(x + tm * (0.08 + 0.6 * t), 1.0, v)
    if z == 1:
        fg = S["fg"]
        k = (0.45 + 0.55 * ((x * 3) % 1.0)) * v
        return (int(fg[0] * k), int(fg[1] * k), int(fg[2] * k))
    if z == 2:
        return hsv((0.83 if int(x * 4) % 2 else 0.33) + t * 0.25, 1.0, v)
    if z == 3:
        return hsv(x * 0.16, 1.0 - 0.7 * x ** 3, v)
    if z == 4:
        return hsv(0.48 + x * 0.2, 0.85 - 0.5 * x ** 4, v)
    return hsv(S["beats"] * 0.381 + x * 0.12, 1.0, v)


def ctint(x):
    """a palette colour pushed toward white, so a tinted cat stays a cat and doesn't go muddy"""
    c = pal(x)
    return (c[0] + (255 - c[0]) * 45 // 100, c[1] + (255 - c[1]) * 45 // 100, c[2] + (255 - c[2]) * 45 // 100)


def chan_shift(surf, n):
    """rotate the colour channels (and nudge one of them a pixel sideways): the cheap, nasty hue shift"""
    data = pygame.image.tostring(surf, "RGB")
    data = data[n:] + data[:n]
    surf.blit(pygame.image.frombuffer(data, surf.get_size(), "RGB"), (0, 0))


def invert_rect(surf, rect=None):
    r = pygame.Rect(rect) if rect else surf.get_rect()
    r = r.clip(surf.get_rect())
    if r.w < 1 or r.h < 1: return
    white = S["white"].subsurface(r)
    tmp = white.copy()
    tmp.blit(surf.subsurface(r), (0, 0), special_flags=pygame.BLEND_RGB_SUB)
    surf.blit(tmp, r.topleft)


def mirror(surf, how, from_far_side=False):
    w, h = surf.get_size()
    if how in (0, 2):
        src = surf.subsurface((w // 2 if from_far_side else 0, 0, w // 2, h))
        surf.blit(pygame.transform.flip(src, True, False), (0 if from_far_side else w // 2, 0))
    if how in (1, 2):
        src = surf.subsurface((0, h // 2 if from_far_side else 0, w, h // 2))
        surf.blit(pygame.transform.flip(src, False, True), (0, 0 if from_far_side else h // 2))


def word_surf(word, size):
    key = (word, size)
    c = S["words"].get(key)
    if c is None:
        f = S["fonts"].get(size)
        if f is None:
            f = S["fonts"][size] = pygame.font.Font(None, size)
        c = S["words"][key] = f.render(word, True, (255, 255, 255))
    return c


# ---------------------------------------------------------------------------------------------------- setup
def setup(screen, eyesy):
    bh = max(120, int(BW * eyesy.yres / float(eyesy.xres)))
    S.clear()
    S.update(bh=bh, buf=pygame.Surface((BW, bh)), white=pygame.Surface((BW, bh)), time=0.0, last=time.time(),
             beat=0.0, beats=0, auto=0.0, frame=0, cat=[0.0] * 5, z=[3] * 5, t=[0.5] * 5, fg=(255, 0, 255),
             play_prev=None, play_env=[0.0] * 5, play_vel=[0.0] * 5, glitch=None, flash=0.0, catflash=0.0,
             q=1.0, avg=0.0, words={}, fonts={}, cover_cache={}, wpos=[], eyes=[])
    S["white"].fill((255, 255, 255))
    sl = pygame.Surface((BW, bh), pygame.SRCALPHA)
    for y in range(0, bh, 3):
        pygame.draw.line(sl, (0, 0, 0, 90), (0, y), (BW, y))
    S["scan"] = sl
    here = None
    for r in (getattr(eyesy, "mode_root", ""), os.path.dirname(os.path.abspath(__file__))):
        if r and os.path.isdir(os.path.join(r, "cats")):
            here = r
            break
    S["cats"], S["covers"] = _make_cats(here) if here else ([], [])
    S["wpos"] = [[random.random() * BW, random.random() * bh, random.choice((-1, 1)) * (90 + random.random() * 160),
                  random.choice((-1, 1)) * (70 + random.random() * 140), random.randrange(len(WORDS))] for _ in range(8)]
    S["buf"].fill((0, 0, 0))


# ---------------------------------------------------------------------------------------------------- the frame
def draw(screen, eyesy):
    if not S:
        setup(screen, eyesy)
    t0 = time.time()
    dt = clamp(t0 - S["last"], 0.001, 0.1)
    S["last"] = t0
    S["time"] += dt
    tm = S["time"]
    S["frame"] += 1
    buf, BH, q = S["buf"], S["bh"], S["q"]
    cx, cy = BW // 2, BH // 2

    # ---- knobs: zone + position inside zone, and how hard they are being thrashed ----
    ks = (eyesy.knob1, eyesy.knob2, eyesy.knob3, eyesy.knob4, eyesy.knob5)
    prev = S["play_prev"]
    S["play_prev"] = ks
    for i in range(5):
        S["z"][i], S["t"][i] = zone(ks[i])
        raw = 0.0 if prev is None else (ks[i] - prev[i]) / dt
        S["play_vel"][i] += (raw - S["play_vel"][i]) * min(1.0, dt * 15.0)
        S["play_env"][i] = max(S["play_env"][i] * math.exp(-dt * 3.0), min(1.0, abs(S["play_vel"][i]) / 1.2))
        S["cat"][i] += ((1.0 if S["z"][i] == NZ - 1 else 0.0) - S["cat"][i]) * min(1.0, dt * 5.0)
    z1, z2, z3, z4, z5 = S["z"]
    t1, t2, t3, t4, t5 = S["t"]
    cat1, cat2, cat3, cat4, cat5 = S["cat"]
    shake = max(S["play_env"])
    S["fg"] = eyesy.color_picker(t4) if z4 == 1 else eyesy.color_picker(0.0)

    # ---- the beat: real sound trigger, or our own metronome if there's no sound at all ----
    try:
        level = clamp(max(abs(v) for v in eyesy.audio_in[:100]) / 30000.0)
    except Exception:
        level = 0.0
    S["auto"] += dt
    hit = bool(getattr(eyesy, "trig", False))
    if level < 0.02 and S["auto"] > 0.46:
        hit = True
    if hit:
        S["auto"] = 0.0
        S["beat"] = 1.0
        S["beats"] += 1
        S["catflash"] = 1.0
        if random.random() < 0.35:
            S["glitch"] = [random.choice(("invert", "pixel", "tear", "chan", "freeze")), random.randint(2, 6)]
    S["beat"] = max(0.0, S["beat"] - dt * 3.2)
    S["catflash"] = max(0.0, S["catflash"] - dt * 2.6)
    beat = S["beat"]
    punch = clamp(beat + level + shake)

    # ---- 1. feedback (knob 1) ----
    zoom, rot, dx, dy = 1.0, 0.0, 0, 0
    if z1 == 0:   zoom, rot = 1.012 + 0.07 * t1, (t1 - 0.5) * 1.5
    elif z1 == 1: zoom, rot = 0.988 - 0.05 * t1, -(t1 - 0.5) * 3.0
    elif z1 == 2: zoom, rot = 1.02 + 0.02 * t1, 2.0 + 12.0 * t1
    elif z1 == 3: zoom, rot = 1.0 + math.sin(tm * (1.5 + 7 * t1)) * 0.06, math.sin(tm * 0.7) * 3
    elif z1 == 4:
        zoom, rot = 1.012, math.sin(tm * 1.3) * 4 * t1
        dx, dy = int(math.sin(tm * 2.1) * 26 * t1), int(math.cos(tm * 1.7) * 18 * t1)
    elif z1 == 5: zoom, rot = 1.02, math.sin(tm) * 2
    else:         zoom, rot = 1.045, 3.0 * math.sin(tm * 0.9) + 2.0 * cat1
    zoom += beat * 0.035 * (0.4 + 0.6 * t1)
    if abs(rot) < 0.05:
        sz = (max(2, int(BW * zoom)), max(2, int(BH * zoom)))
        tmp = pygame.transform.scale(buf, sz)
    else:
        tmp = pygame.transform.rotozoom(buf, rot, zoom)
    buf.blit(tmp, ((BW - tmp.get_width()) // 2 + dx, (BH - tmp.get_height()) // 2 + dy))
    if z1 == 5:
        mirror(buf, 0 if t1 < 0.33 else (1 if t1 < 0.66 else 2), S["frame"] % 2 == 0)
    fade = 240 + int(12 * math.sin(tm * 0.2) ** 2)
    buf.fill((fade, fade, fade), special_flags=pygame.BLEND_RGB_MULT)
    buf.fill((1, 1, 1), special_flags=pygame.BLEND_RGB_SUB)

    # ---- colour rotation of the feedback (knob 4) ----
    if z4 in (0, 5, 6):
        period = 3 + int(10 * (1.0 - t4)) if z4 == 0 else 5
        if S["frame"] % period == 0:
            chan_shift(buf, 1 if z4 != 5 else 2)
    elif z4 == 3 and S["frame"] % 6 == 0:
        buf.fill((8, 0, 0), special_flags=pygame.BLEND_RGB_SUB)         # fire keeps the reds, loses the blues

    # ---- tiled screens (knob 5, zone 2): the picture shrinks and repeats inside itself ----
    if z5 == 2:
        n = 2 + int(t5 * 2.99)
        small = pygame.transform.scale(buf, (BW // n, BH // n))
        for gy in range(n):
            for gx in range(n):
                buf.blit(small, (gx * (BW // n), gy * (BH // n)))

    # ---- 2. fresh stuff (knob 2) ----
    big = min(BW, BH) * 0.5
    if z2 == 0:                                                     # rings
        n = 2 + int(t2 * 5)
        for i in range(n):
            ph = (tm * (0.3 + t2) + i / n) % 1.0
            pygame.draw.circle(buf, pal(i / n + tm * 0.1, 1.0 - ph * 0.5), (cx, cy), int(8 + ph * BW * 0.6), int(2 + 12 * (1 - ph) + beat * 8))
    elif z2 == 1:                                                   # lissajous scribble
        a, b = 1 + int(t2 * 6), 2 + int(t2 * 7)
        pts = [(cx + math.sin(a * u + tm * 1.3) * BW * 0.45 * (1 + 0.2 * beat),
                cy + math.sin(b * u + tm * 0.9 + 1.0) * BH * 0.45) for u in [i * 0.03 for i in range(int(210 * (0.5 + 0.5 * q)))]]
        pygame.draw.lines(buf, pal(tm * 0.2), False, pts, 3 + int(beat * 5))
    elif z2 == 2:                                                   # spinning polygons
        sides = 3 + int(t2 * 6.99)
        for k in range(5):
            r = big * (0.25 + 0.2 * k) * (1.0 + beat * 0.3)
            a0 = tm * (0.8 + k * 0.35) * (1 if k % 2 else -1)
            pts = [(cx + math.cos(a0 + j * 2 * math.pi / sides) * r, cy + math.sin(a0 + j * 2 * math.pi / sides) * r) for j in range(sides)]
            pygame.draw.polygon(buf, pal(k * 0.2 + tm * 0.1), pts, 3 + int(beat * 4))
    elif z2 == 3:                                                   # sound scope (fake one if it's silent)
        smp = [clamp(v / 30000.0, -1, 1) for v in eyesy.audio_in[:100]]
        if level < 0.02:
            smp = [math.sin(i * 0.31 + tm * 7) * 0.5 + math.sin(i * 0.9 - tm * 3) * 0.35 for i in range(100)]
        amp = BH * (0.2 + 0.3 * t2)
        top = [(i * BW / 99.0, cy + s * amp) for i, s in enumerate(smp)]
        pygame.draw.lines(buf, pal(tm * 0.3), False, top, 5)
        pygame.draw.lines(buf, pal(tm * 0.3 + 0.5), False, [(x, 2 * cy - y) for x, y in top], 5)
    elif z2 == 4:                                                   # rays
        n = 6 + int(t2 * 22)
        for i in range(0, n, 2):
            a0 = tm * 0.9 + i * 2 * math.pi / n
            a1 = a0 + math.pi / n
            R = BW
            pygame.draw.polygon(buf, pal(i / n + tm * 0.1), [(cx, cy), (cx + math.cos(a0) * R, cy + math.sin(a0) * R), (cx + math.cos(a1) * R, cy + math.sin(a1) * R)])
    elif z2 == 5:                                                   # shape rain
        for i in range(int((3 + t2 * 26) * q) + 1):
            x, y, s = random.randrange(BW), random.randrange(BH), random.randint(6, 18 + int(60 * punch))
            c = pal(random.random())
            k = random.randrange(3)
            if k == 0: pygame.draw.rect(buf, c, (x, y, s, s))
            elif k == 1: pygame.draw.circle(buf, c, (x, y), s // 2 + 1)
            else: pygame.draw.polygon(buf, c, [(x, y - s), (x - s, y + s), (x + s, y + s)])

    # ---- cat doors, part 1: tunnel (knob 1) and rain (knob 2) ----
    if cat1 > 0.03:
        stamp(buf, S["beats"] // 2, cx, cy, BH * (0.25 + 0.3 * cat1 * (0.6 + 0.4 * math.sin(tm * 3)) + 0.25 * beat),
              tm * 40, ctint(tm * 0.3), 255)
    if cat2 > 0.03:
        n = int((6 + 26 * cat2) * q)
        for j in range(n):
            u = (j * 0.618034) % 1.0
            x = u * BW + math.sin(tm * (0.7 + j * 0.13) + j) * 40
            y = ((tm * (0.12 + 0.2 * ((j * 7) % 5) / 5) + j * 0.137) % 1.25 - 0.12) * BH
            stamp(buf, j, x, y, 40 + 70 * ((j * 3) % 5) / 5.0 + beat * 25, tm * (35 + j * 9) * (1 if j % 2 else -1), ctint(j / 9.0 + tm * 0.2), 255)

    # ---- 3. break the picture (knob 3) ----
    if z3 == 0:                                                     # wobble
        out = buf.copy()
        step = max(2, int(5 / q))
        amp, fr = 4 + 28 * t3 + 20 * beat, 0.05 + 0.1 * t3
        for y in range(0, BH, step):
            out.blit(buf, (int(math.sin(y * fr + tm * 6) * amp), y), (0, y, BW, step))
        buf.blit(out, (0, 0))
    elif z3 == 1:                                                   # pixelate
        f = 2 + int(t3 * 12) + int(beat * 5)
        small = pygame.transform.scale(buf, (max(2, BW // f), max(2, BH // f)))
        pygame.transform.scale(small, (BW, BH), buf)
    elif z3 == 2:                                                   # RGB split
        d = 2 + int(t3 * 18) + int(beat * 8)
        r, g, b = buf.copy(), buf.copy(), buf.copy()
        r.fill((255, 0, 0), special_flags=pygame.BLEND_RGB_MULT)
        g.fill((0, 255, 0), special_flags=pygame.BLEND_RGB_MULT)
        b.fill((0, 0, 255), special_flags=pygame.BLEND_RGB_MULT)
        buf.fill((0, 0, 0))
        buf.blit(r, (-d, 0))
        buf.blit(g, (0, d // 2), special_flags=pygame.BLEND_RGB_ADD)
        buf.blit(b, (d, 0), special_flags=pygame.BLEND_RGB_ADD)
    elif z3 == 3:                                                   # mirror
        mirror(buf, int(t3 * 2.99), int(tm * 0.5) % 2 == 1)
    elif z3 == 4:                                                   # tear
        for _ in range(2 + int(t3 * 8)):
            y, h = random.randrange(BH - 8), random.randint(4, 14 + int(40 * t3))
            h = min(h, BH - y)
            buf.blit(buf.subsurface((0, y, BW, h)).copy(), (random.randint(-90, 90), y))
    elif z3 == 5:                                                   # scanline smear
        buf.blit(S["scan"], (0, 0))
        buf.scroll(random.choice((-1, 1)) * int(1 + t3 * 6), int(2 + t3 * 10))
    if cat3 > 0.03:                                                 # CAT KALEIDOSCOPE: the picture is folded around the middle
        stamp(buf, S["beats"] // 3 + 3, cx, cy, BH * (0.35 + 0.3 * cat3), tm * -55, None, 255)
        side = BH
        core = buf.subsurface((cx - side // 2, 0, side, BH)).copy()
        n = 3 + int(5 * min(1.0, cat3 * 1.2) * (0.6 + 0.4 * q))
        for k in range(1, n):
            spun = pygame.transform.rotozoom(core, k * 360.0 / n + tm * 6, 1.0)
            buf.blit(spun, (cx - spun.get_width() // 2, cy - spun.get_height() // 2), special_flags=pygame.BLEND_RGB_MAX)
        k = 255 - int(40 * min(1.0, cat3))                          # the MAX blend piles up toward white, so bleed it off
        buf.fill((k, k, k), special_flags=pygame.BLEND_RGB_MULT)

    # ---- random glitch events ----
    g = S["glitch"]
    if g:
        kind = g[0]
        if kind == "invert": invert_rect(buf)
        elif kind == "pixel":
            small = pygame.transform.scale(buf, (BW // 24, BH // 24))
            pygame.transform.scale(small, (BW, BH), buf)
        elif kind == "tear":
            for _ in range(10):
                y = random.randrange(BH - 20)
                buf.blit(buf.subsurface((0, y, BW, 20)).copy(), (random.randint(-160, 160), y))
        elif kind == "chan": chan_shift(buf, random.choice((1, 2)))
        g[1] -= 1
        if g[1] <= 0: S["glitch"] = None

    # ---- 4. the junk on top (knob 5) ----
    if z5 == 1:                                                     # TV static
        for _ in range(int((120 + 500 * t5) * q)):
            x, y = random.randrange(BW), random.randrange(BH)
            s = random.choice((2, 3, 4, 6))
            pygame.draw.rect(buf, pal(random.random()), (x, y, s * random.randint(1, 5), s))
    elif z5 == 3:                                                   # bouncing words
        for i in range(1 + int(t5 * 6)):
            w = S["wpos"][i]
            w[0] += w[2] * dt
            w[1] += w[3] * dt
            if int(beat > 0.95): w[4] = random.randrange(len(WORDS))
            s = word_surf(WORDS[w[4]], int(BH * (0.12 + 0.12 * ((i * 5) % 4) / 4.0 + 0.1 * beat)))
            if w[0] < 0 or w[0] + s.get_width() > BW: w[2] = -w[2]; w[0] = clamp(w[0], 0, BW - s.get_width())
            if w[1] < 0 or w[1] + s.get_height() > BH: w[3] = -w[3]; w[1] = clamp(w[1], 0, BH - s.get_height())
            tinted = s.copy()
            tinted.fill(pal(i * 0.3 + tm * 0.2), special_flags=pygame.BLEND_RGB_MULT)
            buf.blit(tinted, (int(w[0]), int(w[1])))
    elif z5 == 4:                                                   # googly eyes
        look = (cx + math.sin(tm * 1.7) * BW * 0.5, cy + math.cos(tm * 2.3) * BH * 0.5)
        for i in range(1 + int(t5 * 8)):
            ex = (0.5 + 0.42 * math.sin(i * 2.399 + tm * 0.3)) * BW
            ey = (0.5 + 0.40 * math.cos(i * 1.7 + tm * 0.25)) * BH
            r = int(18 + 34 * ((i * 7) % 5) / 5.0 + 14 * beat)
            for sx in (-1, 1):
                p = (int(ex + sx * r * 1.1), int(ey))
                pygame.draw.circle(buf, pal(i * 0.17), p, r + 3)
                pygame.draw.circle(buf, (255, 255, 255), p, r)
                a = math.atan2(look[1] - p[1], look[0] - p[0])
                pygame.draw.circle(buf, (0, 0, 0), (int(p[0] + math.cos(a) * r * 0.45), int(p[1] + math.sin(a) * r * 0.45)), int(r * 0.5))
    elif z5 == 5:                                                   # invert bands, white flashes
        if beat > 0.5 or S["frame"] % 9 == 0:
            for _ in range(1 + int(t5 * 4)):
                y = random.randrange(BH - 6)
                invert_rect(buf, (0, y, BW, random.randint(6, 12 + int(60 * t5))))
        if beat > 0.8:
            buf.fill((int(60 * t5), int(60 * t5), int(60 * t5)), special_flags=pygame.BLEND_RGB_ADD)

    # ---- cat doors, part 2: negative flash (knob 4) and takeover (knob 5) ----
    if cat5 > 0.03:
        cols, rows = 3 + int(2 * cat5), 2 + int(cat5 * 2)
        cw, ch = BW / cols, BH / rows
        for r_ in range(rows):
            for c_ in range(cols):
                n = r_ * cols + c_
                sz = max(ch, cw * 0.8) * (0.75 + 0.25 * math.sin(tm * 4 + n * 1.3) + 0.35 * beat) * min(1.0, cat5 * 1.5)
                stamp(buf, n + S["beats"] // 4, (c_ + 0.5) * cw, (r_ + 0.5) * ch, sz, math.sin(tm * 2 + n) * 18, ctint(n / 12.0 + tm * 0.3), 255)
        if S["beats"] % 2 == 0:
            s = word_surf("MEOW", int(BH * (0.3 + 0.3 * beat)))
            s = s.copy()
            s.fill(pal(tm), special_flags=pygame.BLEND_RGB_MULT)
            buf.blit(s, (cx - s.get_width() // 2, cy - s.get_height() // 2))

    # ---- output: the canvas, plus things that only exist for one frame and never feed back ----
    view = buf
    bgadd = None
    if z5 == 0:
        bg = eyesy.color_picker_bg(t5)
        k = 0.12 + 0.3 * beat
        bgadd = (int(bg[0] * k), int(bg[1] * k), int(bg[2] * k))
    if shake > 0.05 or bgadd or cat4 > 0.03:
        view = buf.copy()
        if bgadd:
            view.fill(bgadd, special_flags=pygame.BLEND_RGB_ADD)
        if cat4 > 0.03 and S["covers"]:                             # CAT NEGATIVE: a giant cat flashes on the beat (not fed back)
            c = _cover(S["beats"] % len(S["covers"])).copy()
            c.set_alpha(int(255 * cat4 * clamp(S["catflash"] * 1.5)))
            view.blit(c, (0, 0))
            if S["beats"] % 2 == 0:
                invert_rect(view)
        if shake > 0.4:
            view.fill((int(80 * shake),) * 3, special_flags=pygame.BLEND_RGB_ADD)
            chan_shift(view, 1)
    ox = int(random.uniform(-1, 1) * 14 * shake)
    oy = int(random.uniform(-1, 1) * 10 * shake)
    sw, sh = screen.get_size()
    if (ox or oy):
        screen.fill((0, 0, 0))
        pygame.transform.scale(view, (sw, sh), S.setdefault("tmp_out", pygame.Surface((sw, sh))))
        screen.blit(S["tmp_out"], (ox * sw // BW, oy * sh // BH))
    else:
        pygame.transform.scale(view, (sw, sh), screen)

    # ---- adaptive quality: if the machine is slow, quietly do less ----
    S["avg"] += ((time.time() - t0) - S["avg"]) * 0.1
    if S["avg"] > 0.030: S["q"] = max(0.35, S["q"] - 0.02)
    elif S["avg"] < 0.018: S["q"] = min(1.0, S["q"] + 0.005)
