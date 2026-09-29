# Plasma Melt: a liquid, molten light show. Waves of color slosh and melt into each other, and you can
# stretch them, reverse time, layer them thicker, and turn smooth color into razor-sharp contour rings.
#
# Knob convention (same in every mode):
#   knob1 = size            (zoom: big lazy waves to fine ripples)
#   knob2 = main motion     (flow: 0.5 = frozen, left = backward, right = forward, faster toward the ends)
#   knob3 = extra detail    (layers and melt, plus how many color rings; at the top it goes full zebra)
#   knob4 = foreground color (hue)
#   knob5 = background color (the dark tone the plasma dips into)
import colorsys
import math
import time
import pygame

def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))

_state = {"t": 0.0, "last": None, "size": None, "dist": None, "gw": 0, "gh": 0}

W, H = 112, 63                                                # the plasma is worked out small, then scaled up smoothly

def setup(screen, eyesy):
    pass

def draw(screen, eyesy):
    xres, yres = eyesy.xres, eyesy.yres
    now = time.time()
    if _state["last"] is None:
        _state["last"] = now
    dt = min(now - _state["last"], 0.1)
    _state["last"] = now

    flow = (eyesy.knob2 - 0.5) * 2
    _state["t"] += dt * flow * 3.0
    t = _state["t"]

    if _state["dist"] is None:
        _state["dist"] = [[math.hypot((i / W - 0.5) * (W / H), j / H - 0.5) for i in range(W)] for j in range(H)]
    dist = _state["dist"]

    # ---- knobs ----
    scale = 2.0 + eyesy.knob1 * 16.0
    detail = eyesy.knob3
    layers = 2 + int(detail * 2.99)                           # 2..4 layers of waves
    melt = 0.4 + detail * 2.4                                 # how much the waves fold over themselves
    bands = 1.0 + detail * 7.0                                # how many color rings

    fg = eyesy.color_picker(eyesy.knob4)
    h0 = colorsys.rgb_to_hsv(fg[0] / 255.0, fg[1] / 255.0, fg[2] / 255.0)[0]
    bg = eyesy.color_picker_bg(eyesy.knob5)

    # ---- colour ramp, rebuilt every frame so the knobs feel instant ----
    lut = []
    for i in range(256):
        ph = i / 255.0 * bands * 2 * math.pi
        k = 0.5 + 0.5 * math.sin(ph)
        r, g, b = colorsys.hsv_to_rgb((h0 + 0.18 * math.sin(ph * 0.5) + i / 255.0 * 0.25) % 1.0, 0.85, 0.35 + 0.65 * k)
        m = 1.0 - k
        lut.append((int(clamp(r * 255 * (1 - 0.6 * m) + bg[0] * 0.6 * m, 0, 255)),
                    int(clamp(g * 255 * (1 - 0.6 * m) + bg[1] * 0.6 * m, 0, 255)),
                    int(clamp(b * 255 * (1 - 0.6 * m) + bg[2] * 0.6 * m, 0, 255))))

    # ---- the field: separable waves per column and per row, plus a radial one per pixel ----
    aspect = W / H
    cs1 = [math.sin((i / W - 0.5) * aspect * scale * 1.0 + t * 0.9) for i in range(W)]
    rs1 = [math.sin((j / H - 0.5) * scale * 1.3 - t * 0.7) for j in range(H)]
    sc = [math.sin(((i / W - 0.5) * aspect + 0.0) * scale * 0.8 + t * 0.5) for i in range(W)]
    cc = [math.cos(((i / W - 0.5) * aspect + 0.0) * scale * 0.8 + t * 0.5) for i in range(W)]
    sr = [math.sin((j / H - 0.5) * scale * 0.8) for j in range(H)]
    cr = [math.cos((j / H - 0.5) * scale * 0.8) for j in range(H)]
    buf = bytearray(W * H * 3)
    p = 0
    sin = math.sin
    for j in range(H):
        drow = dist[j]
        r1, s_r, c_r = rs1[j], sr[j], cr[j]
        for i in range(W):
            v = cs1[i] + r1
            if layers >= 3:
                v += sc[i] * c_r + cc[i] * s_r                # a diagonal wave
            if layers >= 4:
                v += sin(drow[i] * scale * 1.4 - t * 1.1)     # ripples from the middle
            v += melt * sin(v * 1.3 + t * 0.6)                # fold it over on itself
            idx = int((v * 0.16 + 0.5) * 255) & 255
            c = lut[idx]
            buf[p] = c[0]; buf[p + 1] = c[1]; buf[p + 2] = c[2]
            p += 3
    small = pygame.image.frombuffer(bytes(buf), (W, H), "RGB")
    screen.blit(pygame.transform.smoothscale(small, (xres, yres)), (0, 0))
