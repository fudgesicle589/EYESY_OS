"""Builds the artwork in ../art from the four album photos in this folder (build-time only: the Pi never runs this).

For each album it writes:
  art/cross_<name>.png   the cross cut out of the photo (RGBA, normalised so the cross is CROSS_H px tall)
  art/bg_<name>.jpg      the square photo with the cross painted out (concrete + woman only; the other two albums
                         have plain black backgrounds). The mode shows it as a square in the middle of the screen.
Run:  python3 build.py        (needs Pillow; the mode itself only needs pygame)
"""
import json
import os
import sys
from PIL import Image, ImageChops, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "art")
sys.path.insert(0, HERE)
import polys

CROSS_H = 640          # height of the cut-out cross in the saved PNG


# ---------------------------------------------------------------- masks and cut-outs
def poly_mask(size, poly, erode=0):
    """anti-aliased polygon mask, optionally eroded a few px to drop the photo's background fringe"""
    k = 4
    m = Image.new("L", (size[0] * k, size[1] * k), 0)
    ImageDraw.Draw(m).polygon([(x * k, y * k) for x, y in poly], fill=255)
    m = m.resize(size, Image.LANCZOS)
    if erode:
        m = m.filter(ImageFilter.MinFilter(erode * 2 + 1))
    return m.filter(ImageFilter.GaussianBlur(0.8))


def flood_mask(img, thr, seed, close=0):
    """inside-the-cross mask for the gold cross: flood the dark interior from `seed`, then grow it so the
    sprayed outline is included"""
    bw = img.convert("L").point(lambda v: 255 if v > thr else 0)
    ImageDraw.floodfill(bw, seed, 128)
    interior = bw.point(lambda v: 255 if v == 128 else 0)
    if close:
        interior = interior.filter(ImageFilter.MaxFilter(close * 2 + 1))
    return interior


def glow_alpha(img, gain):
    r, g, b = img.split()
    mx = ImageChops.lighter(ImageChops.lighter(r, g), b)
    return mx.point(lambda v: min(255, int(v * gain)))


def bbox_of(mask):
    return mask.point(lambda v: 255 if v > 128 else 0).getbbox()


META = {}


def cut_out(name, img, inside, glow=None, margin=0, height=CROSS_H, outline=None):
    alpha = inside if glow is None else ImageChops.lighter(inside, glow)
    rgba = img.convert("RGBA")
    rgba.putalpha(alpha)
    x0, y0, x1, y1 = bbox_of(inside)
    box = (max(0, x0 - margin), max(0, y0 - margin), min(img.width, x1 + margin), min(img.height, y1 + margin))
    rgba = rgba.crop(box)
    s = height / float(y1 - y0)
    rgba = rgba.resize((int(rgba.width * s), int(rgba.height * s)), Image.LANCZOS)
    rgba.save(os.path.join(OUT, "cross_%s.png" % name), optimize=True)
    # clean beat-outline: a straight-edged polygon (never the pixel edge, which has glow / fringe bumps), stored relative
    # to the cross's own centre and height so the mode can scale it with the cross
    cx, cy, hh = ((x0 + x1) / 2.0 - box[0]) * s, ((y0 + y1) / 2.0 - box[1]) * s, (y1 - y0) * s
    pts = [(((x - box[0]) * s - cx) / hh, ((y - box[1]) * s - cy) / hh) for x, y in outline]
    META[name] = {"c": [cx, cy], "h": hh, "outline": [[round(a, 4), round(b, 4)] for a, b in pts]}
    print(name, "cross", rgba.size)


# ---------------------------------------------------------------- symmetric concrete cross
# The concrete photo is shot at an angle (slanted foot, uneven arms). We rebuild it as a straight-on, symmetric cross
# with the same proportions as the others by re-mapping each real face of the photo onto a template.
C = 528.0
# (template quad TL, TR, BR, BL), (photo quad TL, TR, BR, BL); template y-edges are horizontal
FACES = [
    # stem
    (((C - 38, 185), (C + 38, 185), (C + 56, 268), (C - 56, 268)), ((466, 102), (574, 102), (591, 192), (449, 192))),
    # top band: the arm tops and the top of the body
    (((C - 197, 268), (C + 197, 268), (C + 237, 330), (C - 237, 330)), ((288, 204), (762, 204), (790, 272), (262, 272))),
    # left arm side
    (((C - 237, 330), (C - 70, 330), (C - 102, 450), (C - 216, 450)), ((262, 282), (416, 282), (392, 394), (272, 380))),
    # right arm side
    (((C + 70, 330), (C + 237, 330), (C + 216, 450), (C + 102, 450)), ((630, 284), (788, 280), (786, 366), (656, 398))),
    # body
    (((C - 70, 330), (C + 70, 330), (C + 171, 705), (C - 171, 705)), ((424, 284), (620, 284), (722, 716), (326, 724))),
    # foot
    (((C - 171, 705), (C + 171, 705), (C + 135, 835), (C - 135, 835)), ((330, 736), (724, 728), (714, 792), (356, 868))),
]


def concrete_symmetric(photo):
    """returns (RGB image, mask) of the rebuilt cross on a 1056x1056 canvas (template coordinates)"""
    k = 2                                           # supersample
    W = 1056
    out = Image.new("RGB", (W * k, W * k), (0, 0, 0))
    mask = Image.new("L", (W * k, W * k), 0)
    po = out.load()
    px = photo.load()
    pw, ph = photo.size
    md = ImageDraw.Draw(mask)

    def lerp(a, b, t): return a + (b - a) * t

    def sample(x, y):                               # bilinear photo sample
        x = min(max(x, 0), pw - 1.001)
        y = min(max(y, 0), ph - 1.001)
        ix, iy = int(x), int(y)
        fx, fy = x - ix, y - iy
        a, b, c, d = px[ix, iy], px[ix + 1, iy], px[ix, iy + 1], px[ix + 1, iy + 1]
        return tuple(int(lerp(lerp(a[i], b[i], fx), lerp(c[i], d[i], fx), fy)) for i in range(3))

    for (t, s) in FACES:
        (tl, tr, br, bl), (stl, str_, sbr, sbl) = t, s
        y0, y1 = tl[1], bl[1]
        for yy in range(int(y0 * k), int(y1 * k)):
            v = (yy / float(k) - y0) / (y1 - y0)
            xl, xr = lerp(tl[0], bl[0], v), lerp(tr[0], br[0], v)
            slx, sly = lerp(stl[0], sbl[0], v), lerp(stl[1], sbl[1], v)
            srx, sry = lerp(str_[0], sbr[0], v), lerp(str_[1], sbr[1], v)
            for xx in range(int(xl * k), int(xr * k) + 1):
                u = (xx / float(k) - xl) / max(1e-6, xr - xl)
                po[xx, yy] = sample(lerp(slx, srx, u), lerp(sly, sry, u))
        md.polygon([(x * k, y * k) for x, y in t], fill=255)
    out = out.resize((W, W), Image.LANCZOS)
    mask = mask.resize((W, W), Image.LANCZOS).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
    return out, mask


# ---------------------------------------------------------------- painting the cross out of the background
def diffuse_fill(img, hole):
    """coarse-to-fine diffusion of the surroundings into the hole (smooth, colour-correct, no texture)"""
    cur = None
    for div in (32, 16, 8, 4, 2, 1):
        size = (max(2, img.width // div), max(2, img.height // div))
        base = img.resize(size, Image.BOX)
        m = hole.resize(size, Image.BOX).point(lambda v: 255 if v > 0 else 0)
        if cur is None:
            cur = Image.new("RGB", size, img.resize((1, 1), Image.BOX).getpixel((0, 0)))
        else:
            cur = cur.resize(size, Image.BILINEAR)
        for _ in range(40 if div > 1 else 12):
            cur = Image.composite(cur.filter(ImageFilter.GaussianBlur(2)), base, m)
    return cur


def reflect_fill(img, hole, fallback, hrows=0, passes=8):
    """fill the hole by mirroring the photo's own surroundings into it: every missing pixel is a blend of its reflections
    across the nearest left / right / top / bottom edge of the hole (closer edges count more), so the fill is continuous
    with what surrounds it -- sky stays sky, grass stays grass -- and has no tiles or blur. Pixels too deep to reach an
    edge in one pass are filled on later passes, once the pixels around them are filled. Rows above `hrows` (sky and
    horizon) only mirror sideways, folding at the image edges, so the horizon carries across."""
    w, h = img.size
    out = img.copy()
    op = out.load()
    todo = hole.point(lambda v: 255 if v > 64 else 0)
    for _ in range(passes):
        hp = todo.load()
        ip = out.load()
        src = out.copy()                             # read from a snapshot so one pass doesn't feed itself
        sp = src.load()
        L = [[0] * w for _ in range(h)]
        R = [[0] * w for _ in range(h)]
        U = [[0] * w for _ in range(h)]
        D = [[0] * w for _ in range(h)]
        for y in range(h):
            run = 0
            for x in range(w):
                run = run + 1 if hp[x, y] else 0
                L[y][x] = run
            run = 0
            for x in range(w - 1, -1, -1):
                run = run + 1 if hp[x, y] else 0
                R[y][x] = run
        for x in range(w):
            run = 0
            for y in range(h):
                run = run + 1 if hp[x, y] else 0
                U[y][x] = run
            run = 0
            for y in range(h - 1, -1, -1):
                run = run + 1 if hp[x, y] else 0
                D[y][x] = run
        left = Image.new("L", (w, h), 0)
        lp = left.load()
        for y in range(h):
            for x in range(w):
                if not hp[x, y]:
                    continue
                dl, dr, du, dd = L[y][x], R[y][x], U[y][x], D[y][x]
                srcs = ((x - 2 * dl + 1, y, dl), (x + 2 * dr - 1, y, dr), (x, y - 2 * du + 1, du), (x, y + 2 * dd - 1, dd))
                if y < hrows:
                    srcs = srcs[:2]
                tot = r = g = b = 0.0
                for sx, sy, d in srcs:
                    if y < hrows:                    # fold at the image edges
                        sx = -sx - 1 if sx < 0 else (2 * w - sx - 1 if sx >= w else sx)
                    if 0 <= sx < w and 0 <= sy < h and not hp[sx, sy]:
                        wt = 1.0 / (d ** 4)
                        c = sp[sx, sy]
                        tot += wt
                        r += c[0] * wt
                        g += c[1] * wt
                        b += c[2] * wt
                if tot > 1e-12:
                    op[x, y] = (int(r / tot), int(g / tot), int(b / tot))
                else:
                    lp[x, y] = 255
        todo = left
        if not left.getbbox():
            break
    if todo.getbbox():                               # anything still unreachable: smooth fill
        out = Image.composite(fallback, out, todo)
    return out


def fold_y(y, h):
    y = -y - 1 if y < 0 else y
    return min(y, 2 * h - y - 1) if y >= h else y


def split_fill(img, hole, edge):
    """for art with a smooth dark side and a flowing side (Woman): the hole is filled row by row from the left (mirrored
    smoke) and from the right (mirrored liquid), joined along `edge`, a list of (y, x) points where the dark gives way to
    the liquid. Mirroring across the hole's own edge keeps both halves continuous with their surroundings."""
    w, h = img.size
    hp = hole.load()
    ip = img.load()
    out = img.copy()
    op = out.load()
    ys = [p[0] for p in edge]

    def boundary(y):
        if y <= ys[0]:
            return edge[0][1]
        for (y0, x0), (y1, x1) in zip(edge, edge[1:]):
            if y <= y1:
                return x0 + (x1 - x0) * (y - y0) / float(y1 - y0)
        return edge[-1][1]

    def fold(x):
        x = -x - 1 if x < 0 else x
        return min(x, 2 * w - x - 1) if x >= w else x

    strip, fade = 170, 150                            # width of the repeated left strip; width of the fade into the liquid
    # per column: first and last hole row, so the fill can also meet the hole's top and bottom edges cleanly
    top, bot = {}, {}
    for x in range(w):
        col = [y for y in range(h) if hp[x, y] > 64]
        if col:
            top[x], bot[x] = col[0], col[-1]
    reach = 36.0
    rowrun = {}                                      # this row's hole: first and last pixel
    for y in range(h):
        xs = [x for x in range(w) if hp[x, y] > 64]
        if xs:
            rowrun[y] = (xs[0], xs[-1])
    for y in range(h):
        for x in range(w):
            if hp[x, y] <= 64:
                continue
            a, b = rowrun[y]
            # the strip just left of the hole, repeated across it in alternating mirrored copies: the real plate texture,
            # seamless at the hole's left edge
            m = (x - a) % (2 * strip)
            m = 2 * strip - 1 - m if m >= strip else m
            cl = ip[a - 1 - m, y]
            # a narrow band along the right edge fades into the real liquid there
            cr = ip[min(w - 1, b + 1 + (b - x)), y]
            t = max(0.0, min(1.0, (x - (b - fade)) / float(fade)))
            t = t * t * (3 - 2 * t)
            c = [cl[i] * (1 - t) + cr[i] * t for i in range(3)]
            # above-right of the edge curve the river carries on across the hole: the liquid just above the hole, pulled down
            lq = ip[x, max(0, top[x] - 1 - int((y - top[x]) * 90.0 / (bot[x] - top[x] + 1)))]
            wl = max(0.0, min(1.0, (x - boundary(y)) / 80.0 * 0.5 + 0.5))
            wl = wl * wl * (3 - 2 * wl)
            c = [c[i] * (1 - wl) + lq[i] * wl for i in range(3)]
            dt, db = y - top[x], bot[x] - y
            d = min(dt, db)
            if db < reach and db < dt:               # near the bottom edge: mirror vertically across it
                if True:
                    sy = fold_y(2 * bot[x] + 1 - y, h)
                cv = ip[x, sy]
                wv = 1.0 - d / reach
                wv = wv * wv * (3 - 2 * wv)
                c = [c[i] * (1 - wv) + cv[i] * wv for i in range(3)]
            op[x, y] = (int(c[0]), int(c[1]), int(c[2]))
    return out


def tile_detail(img, patch):
    """high-pass (grain/mottling) of an untouched patch, tiled over the whole picture, centred on 128"""
    detail = ImageChops.subtract(img, img.filter(ImageFilter.GaussianBlur(4)), 1, 128).crop(patch)
    t = Image.new("RGB", img.size, (128, 128, 128))
    for y in range(0, img.height, detail.height):
        for x in range(0, img.width, detail.width):
            t.paste(detail, (x, y))
    return t


def grain(img, sigma):
    """film grain like the photos have"""
    n = Image.effect_noise(img.size, sigma).convert("RGB")
    return ImageChops.add(img, n, 1, -128)


def paint_out(img, inside, name, method, hrows=0, seams=(), edge=None, grow=17, feather=3):
    """cross-free version of the photo: 'reflect' mirrors the surroundings in (textured scenes like the hillside),
    'smooth' diffuses them in and adds grain (smooth abstract art like Woman)"""
    hole = inside.filter(ImageFilter.MaxFilter(grow)).point(lambda v: 255 if v > 64 else 0)
    smooth = diffuse_fill(img, hole)
    if method == "reflect":
        fill = reflect_fill(img, hole, grain(smooth, 14), hrows)
        # keep the mirrored texture, but take its low-frequency colour from the smooth fill so no seams show
        d = ImageChops.subtract(smooth.filter(ImageFilter.GaussianBlur(18)), fill.filter(ImageFilter.GaussianBlur(18)), 1, 128)
        fill = ImageChops.add(fill, d, 1, -128)
        if seams:                                    # soften the straight lines where the fill rules change
            band = Image.new("L", img.size, 0)
            for yy in seams:
                ImageDraw.Draw(band).rectangle((0, yy - 6, img.width, yy + 6), fill=255)
            band = ImageChops.multiply(band.filter(ImageFilter.GaussianBlur(3)), hole)
            fill = Image.composite(fill.filter(ImageFilter.GaussianBlur(4)), fill, band)
    elif method == "split":
        fill = split_fill(img, hole, edge)
        fill = ImageChops.add(fill.filter(ImageFilter.GaussianBlur(2.2)), tile_detail(img, (0, 300, 190, 900)), 1, -128)
    else:
        fill = grain(smooth, 16)
    out = Image.composite(fill, img, hole.filter(ImageFilter.GaussianBlur(feather)))
    out.save(os.path.join(OUT, "bg_%s.jpg" % name), quality=90)
    print(name, "bg", out.size)


def main():
    os.makedirs(OUT, exist_ok=True)
    load = lambda n: Image.open(os.path.join(HERE, n + ".jpg")).convert("RGB")

    anchors = {}

    # 1. Cross (Justice, gold on black): dark interior flooded from the middle, grown to take in the sprayed outline
    img = load("cross")
    gold = [(487, 185), (563, 185), (583, 268), (722, 268), (765, 330), (745, 445), (632, 452), (693, 705), (668, 835),
            (398, 835), (357, 705), (415, 462), (312, 448), (292, 330), (330, 268), (470, 268)]   # on the gold stroke
    gold = [(528 + (x - 528) * 1.034, 510 + (y - 510) * 1.025) for x, y in gold]                  # out to its outer edge
    cut_out("cross", img, flood_mask(img, 60, (524, 520), close=7), glow_alpha(img, 3.0), margin=14, outline=gold)

    # 2. Audio / Video / Disco (concrete): rebuilt straight-on + symmetric; background keeps the real photo
    img = load("concrete")
    straight, smask = concrete_symmetric(img)
    cc = [(C - 38, 185), (C + 38, 185), (C + 56, 268), (C + 197, 268), (C + 237, 330), (C + 216, 450), (C + 102, 450),
          (C + 171, 705), (C + 135, 835), (C - 135, 835), (C - 171, 705), (C - 102, 450), (C - 216, 450), (C - 237, 330),
          (C - 197, 268), (C - 56, 268)]
    cut_out("concrete", straight, smask, outline=cc)
    paint_out(img, poly_mask(img.size, polys.CONCRETE), "concrete", "reflect", hrows=405, seams=(189, 405))

    # 3. Woman: cross cut from the 1200px photo (outline traced on the 960px version, scaled up); the painted-out
    # background is made at 960px, where its settings were tuned (it is a soft fill, resolution does not matter)
    big = load("woman")
    K = big.width / 960.0
    small = big.resize((960, 960), Image.LANCZOS)
    inside = poly_mask(big.size, [(x * K, y * K) for x, y in polys.WOMAN], erode=3)
    cut_out("woman", big, inside, height=760, outline=[(x * K, y * K) for x, y in polys.WOMAN])
    big.save(os.path.join(OUT, "bg_woman_original.jpg"), quality=93)      # the untouched art, for Woman cross + Woman art
    x0, y0, x1, y1 = bbox_of(inside)                 # where the cross sits in the album art, so the mode can put it back
    anchors["woman"] = [(x0 + x1) / 2.0 / big.width, (y0 + y1) / 2.0 / big.height, (y1 - y0) / float(big.height)]
    img = small
    paint_out(img, poly_mask(img.size, polys.WOMAN), "woman", "split",
              edge=[(60, -200), (150, -120), (165, 290), (215, 450), (300, 585), (420, 700), (520, 900), (900, 900)],
              grow=9, feather=2)

    # 4. Hyperdrama: bright glass edges close the cross; everything outside is black (glow + flares kept as alpha)
    img = load("hyperdrama")
    cut_out("hyperdrama", img, poly_mask(img.size, polys.HYPERDRAMA), glow_alpha(img, 2.2), margin=110,
            outline=polys.HYPERDRAMA)

    with open(os.path.join(OUT, "anchors.json"), "w") as f:
        json.dump(anchors, f)
    with open(os.path.join(OUT, "shapes.json"), "w") as f:
        json.dump(META, f)


if __name__ == "__main__":
    main()
