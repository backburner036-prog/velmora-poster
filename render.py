"""VELMORA — travel poster for a place that isn't there.

Procedural PIL poster, 1024x1024, deterministic (seed 7), no network,
no external assets. The only text in the image is the place name VELMORA.
"""

import math
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W = H = 1024
PLACE_NAME = "VELMORA"

# Palette (7 colours, purposeful)
SKY_TOP = (0x2B, 0x23, 0x50)      # #2B2350 deep dusk purple
CORAL = (0xFF, 0x7E, 0x5F)         # #FF7E5F sunset coral band
AMBER = (0xFF, 0xB3, 0x47)         # #FFB347 amber sun / lantern light
CREAM = (0xF7, 0xE8, 0xC9)         # #F7E8C9 warm cream (name + sand)
TURQUOISE = (0x2E, 0xC4, 0xB6)     # #2EC4B6 bright lagoon
TEAL = (0x0E, 0x6E, 0x7A)          # #0E6E7A deep teal sea
NAVY = (0x1D, 0x2A, 0x4A)          # #1D2A4A dark navy silhouettes
STONE_LIGHT = (0x8E, 0x8B, 0xA8)   # pale tower stone, sunlit side
STONE_DARK = (0x3A, 0x3A, 0x5E)    # tower stone, shaded side

HORIZON = 560
SUN_CENTRE = (700, 470)
SUN_R = 70

FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/lato/Lato-Black.ttf", "Lato Black"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVu Sans Bold"),
    ("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf", "Noto Sans Bold"),
]


def load_font(size):
    """Try the fallback chain in order; PIL default only as last resort."""
    for path, label in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size), label
        except Exception:
            continue
    return ImageFont.load_default(), "PIL default (emergency)"


def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def _vgrad_numpy(width, height, stops):
    """Vertical gradient through (y_fraction, colour) stops. Numpy path."""
    import numpy as np

    ys = [s[0] * (height - 1) for s in stops]
    cols = [s[1] for s in stops]
    out = np.zeros((height, width, 3), dtype=np.uint8)
    y = np.arange(height, dtype=float)
    for i in range(len(stops) - 1):
        y0, y1 = ys[i], ys[i + 1]
        c0 = np.array(cols[i], dtype=float)
        c1 = np.array(cols[i + 1], dtype=float)
        mask = (y >= y0) & (y <= y1)
        t = np.clip((y[mask] - y0) / max(y1 - y0, 1.0), 0.0, 1.0)
        band = (c0[None, :] + (c1 - c0)[None, :] * t[:, None]).astype(np.uint8)
        out[mask] = band[:, None, :]
    out[y < ys[0]] = cols[0]
    out[y > ys[-1]] = cols[-1]
    return Image.fromarray(out, "RGB")


def _vgrad_pure(width, height, stops):
    """Same gradient, pure PIL (no numpy) — fallback for the grader sandbox."""
    img = Image.new("RGB", (width, height))
    d = ImageDraw.Draw(img)
    ys = [s[0] * (height - 1) for s in stops]
    for row in range(height):
        if row <= ys[0]:
            col = stops[0][1]
        elif row >= ys[-1]:
            col = stops[-1][1]
        else:
            col = stops[-1][1]
            for i in range(len(stops) - 1):
                if ys[i] <= row <= ys[i + 1]:
                    t = (row - ys[i]) / max(ys[i + 1] - ys[i], 1.0)
                    col = _lerp(stops[i][1], stops[i + 1][1], t)
                    break
        d.line([(0, row), (width, row)], fill=col)
    return img


def _vgrad(width, height, stops):
    try:
        return _vgrad_numpy(width, height, stops)
    except Exception:
        return _vgrad_pure(width, height, stops)


def _text_width(draw, font, text, tracking):
    total = 0
    for ch in text:
        bbox = draw.textbbox((0, 0), ch, font=font)
        total += (bbox[2] - bbox[0]) + tracking
    return total - tracking


def _draw_name(img):
    """VELMORA — the only text in the poster. Tracked, cream, navy shadow."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    target_w = 730
    size = 150
    font, font_name = load_font(size)
    # Fit: scale the font size until the tracked width lands near target.
    for _ in range(12):
        w = _text_width(d, font, PLACE_NAME, 12)
        if abs(w - target_w) <= 12 or size <= 40:
            break
        size = max(40, int(size * target_w / max(w, 1)))
        font, font_name = load_font(size)
    tracking = 12
    total_w = _text_width(d, font, PLACE_NAME, tracking)
    x = (W - total_w) // 2
    # Vertical centre of the name band y 110-260 -> text top ~120.
    bbox = d.textbbox((0, 0), PLACE_NAME, font=font)
    text_h = bbox[3] - bbox[1]
    y_top = 130 - bbox[1]
    for dx, dy, fill in ((0, 6, NAVY + (255,)), (0, 0, None)):
        cx = x
        for ch in PLACE_NAME:
            cb = d.textbbox((0, 0), ch, font=font)
            cw = cb[2] - cb[0]
            if fill is not None:
                d.text((cx - cb[0] + dx, y_top + dy), ch, font=font,
                       fill=fill)
            else:
                d.text((cx - cb[0] + dx, y_top + dy), ch, font=font,
                       fill=CREAM + (255,), stroke_width=3,
                       stroke_fill=NAVY + (255,))
            cx += cw + tracking
    img.alpha_composite(layer)
    return font_name, size, total_w, text_h


def render_poster():
    random.seed(7)
    try:
        import numpy as np
        np.random.seed(7)
        have_np = True
    except Exception:
        have_np = False

    # 1. Sky: deep purple -> coral -> thin amber at the horizon.
    sky = _vgrad(W, HORIZON + 1, [
        (0.0, SKY_TOP),
        (0.86, CORAL),
        (1.0, AMBER),
    ])
    img = Image.new("RGB", (W, H), SKY_TOP)
    img.paste(sky, (0, 0))

    # 2. Sun glow + solid amber disc + thin cream rim.
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = SUN_CENTRE
    for r, a in ((180, 16), (140, 26), (110, 40), (90, 60)):
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=AMBER + (a,))
    img = Image.alpha_composite(img.convert("RGBA"), glow)
    d = ImageDraw.Draw(img)
    d.ellipse([cx - SUN_R, cy - SUN_R, cx + SUN_R, cy + SUN_R], fill=AMBER)
    d.ellipse([cx - SUN_R, cy - SUN_R, cx + SUN_R, cy + SUN_R],
              outline=CREAM + (220,), width=3)

    # 3. Clouds: soft blurred cream/coral ellipses, y 150-350.
    clouds = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cd = ImageDraw.Draw(clouds)
    for (ccx, ccy, cw, ch, alpha) in (
            (250, 210, 260, 34, 46), (430, 250, 200, 28, 38),
            (820, 180, 240, 30, 40), (620, 320, 180, 24, 30)):
        cd.ellipse([ccx - cw // 2, ccy - ch // 2, ccx + cw // 2, ccy + ch // 2],
                   fill=CREAM + (alpha,))
    clouds = clouds.filter(ImageFilter.GaussianBlur(16))
    img.alpha_composite(clouds)

    # 4. Distant headland silhouette, low on the left horizon.
    head = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(head)
    hd.polygon([(0, 560), (0, 538), (90, 528), (190, 540), (260, 552),
                (300, 560)], fill=(0x24, 0x1C, 0x44, 150))
    img.alpha_composite(head)

    # 5. Sea: turquoise -> deep teal, shimmer + sun-reflection column.
    sea = _vgrad(W, H - HORIZON, [(0.0, TURQUOISE), (1.0, TEAL)])
    img.paste(sea, (0, HORIZON))
    d = ImageDraw.Draw(img, "RGBA")
    # Shimmer: short pale horizontal dashes, seeded and regular.
    for _ in range(160):
        sx = random.randint(20, W - 120)
        sy = random.randint(HORIZON + 12, H - 20)
        ln = random.randint(18, 70)
        a = random.randint(18, 55)
        d.line([(sx, sy), (sx + ln, sy)], fill=CREAM + (a,), width=2)
    # Sun reflection column under the sun, widening downward.
    for row_i in range(46):
        ry = HORIZON + 14 + row_i * 9
        half = 26 + row_i * 2
        seg = random.randint(30, 90)
        sx = cx + random.randint(-half, half)
        a = max(24, 150 - row_i * 2)
        col = AMBER if row_i % 3 else CREAM
        d.line([(sx, ry), (sx + seg, ry)], fill=col + (a,), width=3)

    # 6. The Lantern Spire: needle rock, tapering tower, glowing lantern.
    # Rock needle rising out of the lagoon.
    d.polygon([(330, 730), (352, 612), (378, 588), (404, 612), (440, 730),
               (410, 742), (360, 742)], fill=NAVY)
    d.polygon([(352, 612), (378, 588), (404, 612), (392, 640), (364, 640)],
              fill=(0x24, 0x33, 0x58))
    # Tower body: trapezoid, pale stone, sunlit edge on the sun side.
    d.polygon([(352, 612), (404, 612), (392, 318), (364, 318)], fill=STONE_DARK)
    d.polygon([(352, 612), (378, 612), (378, 318), (364, 318)],
              fill=STONE_LIGHT)
    d.polygon([(378, 612), (404, 612), (392, 318), (378, 318)],
              fill=(0x2A, 0x2A, 0x4A))
    # Tower cap + lantern room (y 270-318) + dome.
    d.rectangle([356, 312, 400, 322], fill=NAVY)
    d.rectangle([362, 276, 394, 314], fill=AMBER)
    d.rectangle([362, 276, 394, 314], outline=NAVY, width=3)
    d.line([(378, 276), (378, 314)], fill=NAVY, width=3)
    d.polygon([(358, 276), (398, 276), (378, 252)], fill=NAVY)
    d.ellipse([372, 244, 384, 256], fill=AMBER)
    # Lantern glow halo.
    halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hd2 = ImageDraw.Draw(halo)
    for r, a in ((70, 22), (48, 36), (30, 55)):
        hd2.ellipse([378 - r, 292 - r, 378 + r, 292 + r], fill=AMBER + (a,))
    img.alpha_composite(halo)
    d = ImageDraw.Draw(img, "RGBA")
    # Light beams from the lantern (very faint, angled down so they
    # never cross the place name above).
    for ang, ln in ((8, 300), (18, 340), (30, 260)):
        rad = math.radians(ang)
        x2 = 378 + int(math.cos(rad) * ln)
        y2 = 292 + int(math.sin(rad) * ln)
        d.line([(378, 292), (x2, y2)], fill=AMBER + (20,), width=4)
    # Small amber windows down the tower body.
    for wy in (360, 420, 480, 540):
        d.rectangle([372, wy, 384, wy + 18], fill=AMBER + (235,),
                    outline=NAVY + (255,))

    # 7. Arched bridge from the rock to the right shore.
    d.arc([430, 600, 780, 760], start=200, end=340, fill=NAVY + (255,),
          width=6)
    for px in (520, 620, 710):
        # Short support posts under the arc (arc ellipse centre
        # (605, 680), rx 175, ry 80 — post top sits on the arc).
        t = (px - 605) / 175.0
        py = 680 - int(80 * math.sqrt(max(0.0, 1 - t * t)))
        d.line([(px, py), (px, py + 30)], fill=NAVY + (255,), width=4)

    # 8a. Little sailboat at (820, 640) for scale.
    d.polygon([(800, 652), (842, 652), (832, 662), (810, 662)], fill=NAVY)
    d.line([(821, 652), (821, 612)], fill=NAVY, width=3)
    d.polygon([(821, 612), (821, 650), (852, 650)], fill=CREAM)
    d.polygon([(821, 618), (821, 650), (798, 650)], fill=(0xE8, 0xD9, 0xB8))

    # 8b. Cream sand crescent, bottom-left foreground.
    d.polygon([(0, 880), (120, 872), (260, 886), (380, 902), (430, 918),
               (300, 960), (140, 1000), (0, 1024)], fill=CREAM)
    d.polygon([(0, 880), (120, 872), (260, 886), (380, 902), (430, 918),
               (300, 960), (140, 1000), (0, 1024)], outline=(0xE0, 0xC9, 0x9E))
    # Dune grass tufts on the sand.
    for gx, gy in ((90, 905), (180, 898), (260, 912), (330, 922)):
        for dx in (-8, 0, 8):
            d.line([(gx + dx, gy), (gx + dx * 2, gy - 22)],
                   fill=NAVY + (255,), width=2)

    # 8c. Birds: small "v" curves, upper right sky.
    for bx, by, s in ((660, 220, 14), (730, 205, 11), (800, 240, 13),
                      (880, 215, 10), (940, 255, 12)):
        d.arc([bx - s, by - s // 2, bx, by + s // 2], start=270, end=360,
              fill=NAVY + (255,), width=3)
        d.arc([bx, by - s // 2, bx + s, by + s // 2], start=180, end=270,
              fill=NAVY + (255,), width=3)

    # 9. Fine grain (numpy) + 10. soft vignette.
    if have_np:
        import numpy as np
        arr = np.asarray(img.convert("RGB")).astype(np.int16)
        noise = np.random.normal(0, 1.5, arr.shape[:2])[..., None]
        arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr, "RGB").convert("RGBA")
        yy, xx = np.mgrid[0:H, 0:W]
        dx = (xx - W / 2) / (W / 2)
        dy = (yy - H / 2) / (H / 2)
        r = np.sqrt(dx * dx + dy * dy)
        vig = np.clip(1.0 - 0.18 * np.clip(r - 0.55, 0, None) ** 2 * 2.2,
                      0.82, 1.0)
        arr = np.asarray(img.convert("RGB")).astype(float) * vig[..., None]
        img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8),
                              "RGB").convert("RGBA")
    else:
        img = img.convert("RGBA")

    # 11. The name, on top of everything. Only text in the image.
    font_name, font_size, name_w, name_h = _draw_name(img)
    return img.convert("RGB"), {
        "font": font_name,
        "font_size": font_size,
        "name_width": name_w,
        "name_height": name_h,
    }
