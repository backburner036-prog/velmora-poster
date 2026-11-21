"""VELMORA poster renderer — 100% PURE STDLIB.

No PIL, no numpy, no fonts on disk, no network, no external assets.
Only: math, random, zlib, struct, hashlib, os, sys (via main.py).

Image: 1024x1024 RGB bytearray buffer. Own gradient / ellipse /
polygon / thick-line / arc helpers, own 5x7 bitmap font for VELMORA,
own PNG encoder (IHDR + IDAT zlib level 6 + IEND, no tEXt/tIME).
Deterministic: random.seed(7).
"""

import math
import random
import struct
import zlib

W = 1024
H = 1024
HORIZON = 560

# Palette (design brief, 7 colours)
SKY_TOP = (0x2B, 0x23, 0x50)    # #2B2350 deep dusk purple
CORAL = (0xFF, 0x7E, 0x5F)      # #FF7E5F sunset coral
AMBER = (0xFF, 0xB3, 0x47)      # #FFB347 sun amber / lantern light
CREAM = (0xF7, 0xE8, 0xC9)      # #F7E8C9 name + sand
TURQ = (0x2E, 0xC4, 0xB6)       # #2EC4B6 lagoon turquoise
TEAL = (0x0E, 0x6E, 0x7A)       # #0E6E7A deep teal
NAVY = (0x1D, 0x2A, 0x4A)       # #1D2A4A dark navy silhouettes
STONE = (0x8E, 0x8B, 0xA8)      # pale stone side of the tower (sunlit)


def _lerp(a, b, t):
    return int(a + (b - a) * t + 0.5)


def _mix(c1, c2, t):
    return (_lerp(c1[0], c2[0], t), _lerp(c1[1], c2[1], t),
            _lerp(c1[2], c2[2], t))


def _multi_stop(stops, t):
    """stops: list of (pos 0..1, rgb). Piecewise-linear gradient."""
    if t <= stops[0][0]:
        return stops[0][1]
    for i in range(1, len(stops)):
        p0, c0 = stops[i - 1]
        p1, c1 = stops[i]
        if t <= p1:
            f = 0.0 if p1 == p0 else (t - p0) / (p1 - p0)
            return _mix(c0, c1, f)
    return stops[-1][1]


class Canvas:
    def __init__(self, w=W, h=H):
        self.w = w
        self.h = h
        self.buf = bytearray(w * h * 3)

    # -- low level -----------------------------------------------------
    def _idx(self, x, y):
        return (y * self.w + x) * 3

    def blend_px(self, x, y, color, alpha):
        """Alpha-blend one pixel. alpha 0..255."""
        if alpha <= 0 or x < 0 or y < 0 or x >= self.w or y >= self.h:
            return
        if alpha >= 255:
            i = self._idx(x, y)
            self.buf[i] = color[0]
            self.buf[i + 1] = color[1]
            self.buf[i + 2] = color[2]
            return
        i = self._idx(x, y)
        a = alpha
        ia = 255 - a
        self.buf[i] = (color[0] * a + self.buf[i] * ia) // 255
        self.buf[i + 1] = (color[1] * a + self.buf[i + 1] * ia) // 255
        self.buf[i + 2] = (color[2] * a + self.buf[i + 2] * ia) // 255

    def fill_rect(self, x, y, rw, rh, color, alpha=255):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + rw)
        y1 = min(self.h, y + rh)
        if x1 <= x0 or y1 <= y0:
            return
        if alpha >= 255:
            row = bytes(color) * (x1 - x0)
            for yy in range(y0, y1):
                s = self._idx(x0, yy)
                self.buf[s:s + len(row)] = row
        else:
            for yy in range(y0, y1):
                for xx in range(x0, x1):
                    self.blend_px(xx, yy, color, alpha)

    def fill_row(self, y, color):
        s = y * self.w * 3
        self.buf[s:s + self.w * 3] = bytes(color) * self.w

    def vgrad(self, y0, y1, stops):
        span = max(1, y1 - y0)
        for y in range(y0, min(y1, self.h)):
            t = (y - y0) / span
            self.fill_row(y, _multi_stop(stops, t))

    # -- shapes --------------------------------------------------------
    def fill_ellipse(self, cx, cy, rx, ry, color, alpha=255):
        if rx <= 0 or ry <= 0:
            return
        for y in range(max(0, cy - ry), min(self.h, cy + ry + 1)):
            dy = (y - cy) / ry
            rem = 1.0 - dy * dy
            if rem < 0:
                continue
            dx = int(rx * math.sqrt(rem))
            x0 = max(0, cx - dx)
            x1 = min(self.w - 1, cx + dx)
            if alpha >= 255:
                row = bytes(color) * (x1 - x0 + 1)
                s = self._idx(x0, y)
                self.buf[s:s + len(row)] = row
            else:
                for xx in range(x0, x1 + 1):
                    self.blend_px(xx, y, color, alpha)

    def fill_disc(self, cx, cy, r, color, alpha=255):
        self.fill_ellipse(cx, cy, r, r, color, alpha)

    def fill_polygon(self, pts, color, alpha=255):
        """Scanline polygon fill (sorted edge intersections)."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0 = max(0, min(ys))
        y1 = min(self.h - 1, max(ys))
        n = len(pts)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x1, y1p = pts[i]
                x2, y2p = pts[(i + 1) % n]
                if y1p == y2p:
                    continue
                if (y >= min(y1p, y2p)) and (y < max(y1p, y2p)):
                    t = (y - y1p) / (y2p - y1p)
                    xs.append(x1 + t * (x2 - x1))
            if len(xs) < 2:
                continue
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                xa = max(0, int(math.ceil(xs[k])))
                xb = min(self.w - 1, int(math.floor(xs[k + 1])))
                if xb < xa:
                    continue
                if alpha >= 255:
                    row = bytes(color) * (xb - xa + 1)
                    s = self._idx(xa, y)
                    self.buf[s:s + len(row)] = row
                else:
                    for xx in range(xa, xb + 1):
                        self.blend_px(xx, y, color, alpha)

    def thick_line(self, x0, y0, x1, y1, color, width=3, alpha=255):
        """Thick line via discs stamped along the segment."""
        dx = x1 - x0
        dy = y1 - y0
        dist = math.hypot(dx, dy)
        steps = max(1, int(dist))
        r = max(1, width // 2)
        for s in range(steps + 1):
            t = s / steps
            self.fill_disc(int(x0 + dx * t), int(y0 + dy * t), r, color,
                           alpha)

    def bezier(self, p0, p1, p2, color, width=6, alpha=255, steps=80):
        prev = None
        for s in range(steps + 1):
            t = s / steps
            mt = 1 - t
            x = int(mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0])
            y = int(mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1])
            if prev is not None:
                self.thick_line(prev[0], prev[1], x, y, color, width, alpha)
            prev = (x, y)

    # -- vignette ------------------------------------------------------
    def vignette(self, max_dark=0.18):
        """Soft radial darkening, separable row/col factors (precomputed)."""
        cx = self.w / 2.0
        cy = self.h / 2.0
        fx = []
        for x in range(self.w):
            d = abs(x - cx) / cx
            fx.append(1.0 - max_dark * max(0.0, (d - 0.55) / 0.45) ** 2)
        fy = []
        for y in range(self.h):
            d = abs(y - cy) / cy
            fy.append(1.0 - max_dark * max(0.0, (d - 0.55) / 0.45) ** 2)
        buf = self.buf
        for y in range(self.h):
            fyy = fy[y]
            base = y * self.w * 3
            for x in range(self.w):
                f = fx[x] * fyy
                if f >= 0.999:
                    continue
                i = base + x * 3
                buf[i] = int(buf[i] * f)
                buf[i + 1] = int(buf[i + 1] * f)
                buf[i + 2] = int(buf[i + 2] * f)


# -- 5x7 bitmap font (own design, only the letters we need) -----------
# '#' = on, '.' = off. 5 wide, 7 tall.
GLYPHS = {
    'V': ["#...#",
          "#...#",
          "#...#",
          "#...#",
          ".#.#.",
          ".#.#.",
          "..#.."],
    'E': ["#####",
          "#....",
          "#....",
          "####.",
          "#....",
          "#....",
          "#####"],
    'L': ["#....",
          "#....",
          "#....",
          "#....",
          "#....",
          "#....",
          "#####"],
    'M': ["#...#",
          "##.##",
          "#.#.#",
          "#.#.#",
          "#...#",
          "#...#",
          "#...#"],
    'O': [".###.",
          "#...#",
          "#...#",
          "#...#",
          "#...#",
          "#...#",
          ".###."],
    'R': ["####.",
          "#...#",
          "#...#",
          "####.",
          "#.#..",
          "#..#.",
          "#...#"],
    'A': [".###.",
          "#...#",
          "#...#",
          "#####",
          "#...#",
          "#...#",
          "#...#"],
}


def draw_text(c, text, x0, y0, scale, tracking, color, shadow=None,
              shadow_dy=6, stroke=None):
    """Draw bitmap text. Returns total pixel width."""
    total = sum(5 * scale for _ in text) + tracking * (len(text) - 1)

    def _draw_at(ox, oy, col):
        x = x0 + ox
        for ch in text:
            g = GLYPHS[ch]
            for r, row in enumerate(g):
                for col_i, px in enumerate(row):
                    if px == '#':
                        c.fill_rect(x + col_i * scale, y0 + oy + r * scale,
                                    scale, scale, col)
            x += 5 * scale + tracking

    # shadow first (solid navy, offset down), then stroke (2px navy in
    # 4 directions), then the cream face.
    if shadow is not None:
        _draw_at(0, shadow_dy, shadow)
    if stroke is not None:
        for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            _draw_at(ox, oy, stroke)
    _draw_at(0, 0, color)
    return total


# -- PNG encoder (own, deterministic) ----------------------------------
def _chunk(ctype, data):
    out = struct.pack(">I", len(data)) + ctype + data
    out += struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF)
    return out


def encode_png(c):
    ihdr = struct.pack(">IIBBBBB", c.w, c.h, 8, 2, 0, 0, 0)
    raw = bytearray()
    row_bytes = c.w * 3
    for y in range(c.h):
        raw.append(0)  # filter 0 (None)
        s = y * row_bytes
        raw += c.buf[s:s + row_bytes]
    idat = zlib.compress(bytes(raw), 6)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", idat) + _chunk(b"IEND", b""))


# -- the poster --------------------------------------------------------
def render_poster():
    random.seed(7)
    c = Canvas()

    # 1. Sky: vertical 3-stop gradient purple -> coral -> amber horizon.
    c.vgrad(0, HORIZON, [
        (0.00, SKY_TOP),
        (0.55, (0x6E, 0x3D, 0x6B)),
        (0.85, CORAL),
        (1.00, AMBER),
    ])

    # 2. Sun glow (layered alpha ellipses = glow, no blur needed),
    #    then cream rim + solid amber disc at (700, 470), r 70.
    for r, a in ((180, 16), (140, 26), (105, 42)):
        c.fill_ellipse(700, 470, r, r, AMBER, a)
    c.fill_disc(700, 470, 72, CREAM, 255)
    c.fill_disc(700, 470, 70, AMBER, 255)

    # 3. Clouds: soft low-alpha cream/coral ellipses, y 150-350.
    clouds = [(200, 210, 120, 26), (330, 180, 90, 20), (880, 300, 130, 24),
              (950, 180, 80, 18), (120, 330, 100, 20), (620, 150, 90, 16)]
    for cx, cy, rx, ry in clouds:
        c.fill_ellipse(cx, cy, rx, ry, CREAM, 22)
        c.fill_ellipse(cx, cy, int(rx * 0.6), int(ry * 0.6), CORAL, 14)

    # 4. Distant headland, very low silhouette at the left horizon.
    c.fill_polygon([(0, 560), (0, 540), (90, 532), (190, 544),
                    (260, 556), (260, 560)], (0x3A, 0x2E, 0x5E), 150)

    # 5. Sea: turquoise -> deep teal gradient.
    c.vgrad(HORIZON, H, [(0.0, TURQ), (1.0, TEAL)])

    # 5b. Sea shimmer: short thin horizontal lines, seeded, alpha low.
    for _ in range(260):
        y = random.randint(HORIZON + 8, H - 10)
        x = random.randint(0, W - 120)
        ln = random.randint(18, 90)
        col = CREAM if random.random() < 0.35 else TURQ
        a = random.randint(14, 42)
        c.thick_line(x, y, x + ln, y, col, 2, a)

    # 5c. Sun reflection column under the sun (x 640-760), widening down.
    for k in range(46):
        y = HORIZON + 12 + k * 10
        half = 26 + k * 1.6
        x0 = int(700 - half + random.randint(-8, 8))
        ln = int(half * 2 * random.uniform(0.45, 0.95))
        col = AMBER if random.random() < 0.6 else CREAM
        c.thick_line(x0, y, x0 + ln, y, col, 3,
                     random.randint(30, 80))

    # 6. Needle rock (navy) x ~340-430, y 560-720.
    c.fill_polygon([(352, 720), (428, 720), (420, 640), (408, 585),
                    (392, 560), (368, 560), (352, 600), (344, 660)],
                   NAVY, 255)
    # pale sunlit edge on the rock's right side
    c.fill_polygon([(408, 585), (420, 640), (428, 720), (414, 720),
                    (406, 640), (398, 590)], STONE, 255)

    # 6b. The Lantern Spire: tapered tower y 300-700, base ~55, top ~30.
    c.fill_polygon([(357, 700), (413, 700), (398, 300), (372, 300)],
                   NAVY, 255)
    # sunlit stone face (right side of the tower)
    c.fill_polygon([(390, 700), (413, 700), (398, 300), (390, 300)],
                   STONE, 255)
    # lantern room y 270-300 + small dome, glowing amber
    c.fill_ellipse(385, 272, 26, 14, AMBER, 90)   # halo
    c.fill_rect(363, 272, 44, 30, AMBER, 255)
    c.fill_ellipse(385, 272, 24, 12, NAVY, 255)   # dome
    c.fill_rect(381, 258, 8, 8, NAVY, 255)        # finial
    # lantern glow spill
    c.fill_ellipse(385, 287, 60, 26, AMBER, 26)
    # 4 small amber windows down the tower body
    for wy in (360, 440, 520, 600):
        c.fill_rect(379, wy, 12, 18, AMBER, 255)
    # thin light beams from the lantern (very low alpha)
    c.thick_line(363, 282, 180, 240, AMBER, 2, 26)
    c.thick_line(407, 282, 590, 235, AMBER, 2, 26)

    # 7. Arched bridge: rock (430, 660) -> beach right (760, 700).
    c.bezier((430, 660), (600, 590), (760, 700), NAVY, 6, 255)
    c.thick_line(520, 648, 520, 690, NAVY, 4, 255)
    c.thick_line(650, 640, 650, 700, NAVY, 4, 255)

    # 8a. Little sailboat at (820, 640): navy hull + cream sail.
    c.thick_line(820, 600, 820, 648, NAVY, 3, 255)          # mast
    c.fill_polygon([(822, 604), (822, 644), (862, 644)], CREAM, 255)
    c.fill_polygon([(818, 610), (818, 644), (790, 644)], CREAM, 200)
    c.fill_polygon([(792, 648), (852, 648), (842, 664), (802, 664)],
                   NAVY, 255)

    # 8b. Crescent cream beach, bottom-left foreground.
    c.fill_polygon([(0, 880), (150, 858), (300, 878), (420, 918),
                    (400, 1024), (0, 1024)], CREAM, 255)
    # dune grass tufts (thin navy strokes)
    for gx, gy in ((90, 884), (150, 872), (220, 872), (300, 890),
                   (360, 908)):
        for dx in (-8, 0, 8):
            c.thick_line(gx, gy, gx + dx, gy - 22, NAVY, 2, 255)

    # 8c. Birds: small navy "v" curves, right sky (clear of the name).
    for bx, by in ((790, 300), (850, 330), (910, 295), (120, 310),
                   (180, 340)):
        c.thick_line(bx - 12, by, bx, by - 8, NAVY, 2, 255)
        c.thick_line(bx, by - 8, bx + 12, by, NAVY, 2, 255)

    # 9. Vignette (soft radial darkening, max ~18% at corners).
    c.vignette(0.18)

    # 10. Name VELMORA, top centre: bitmap 5x7, scale 18, tracking 18.
    #     Total width 7*90 + 6*18 = 738 px, height 126 px, y 110-236.
    name_w = draw_text(c, "VELMORA", 143, 110, 18, 18, CREAM,
                       shadow=NAVY, shadow_dy=6, stroke=NAVY)

    png = encode_png(c)
    info = {
        "size": (W, H),
        "name_width": name_w,
        "name_height": 7 * 18,
        "font": "bitmap-5x7 scale 18 (own, pure stdlib)",
    }
    return png, info
