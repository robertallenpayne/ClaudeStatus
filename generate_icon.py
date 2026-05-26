#!/usr/bin/env python3
"""Generate the Claude Status app icon at all required macOS sizes."""

import os
from PIL import Image, ImageDraw, ImageFilter

BG     = (15,  15,  26)
CARD   = (26,  26,  46)
TRACK  = (45,  45,  70)
PURPLE = (167, 139, 250)
GREEN  = (74,  222, 128)
YELLOW = (251, 191, 36)
WHITE  = (226, 232, 240)


def rounded_rect_mask(size, radius):
    """Return a grayscale mask with a white rounded rectangle."""
    mask = Image.new("L", size, 0)
    d = ImageDraw.Draw(mask)
    w, h = size
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    return mask


def solid_layer(size, color, alpha=255):
    r, g, b = color
    img = Image.new("RGBA", size, (r, g, b, alpha))
    return img


def composite_rounded(base, color, xy, radius, alpha=255):
    """Composite a rounded-rect of `color` at `alpha` onto `base` in-place."""
    x0, y0, x1, y1 = xy
    w, h = x1 - x0, y1 - y0
    layer = solid_layer((w, h), color, alpha)
    mask  = rounded_rect_mask((w, h), radius)
    base.paste(layer, (x0, y0), mask=mask)


def draw_progress_bar(img, x, y, w, h, pct, color):
    r = h // 2
    # Track
    composite_rounded(img, TRACK, (x, y, x + w, y + h), r, 255)
    # Fill
    fill_w = max(h, int(w * pct))
    composite_rounded(img, color, (x, y, x + fill_w, y + h), r, 255)


def draw_node_graph(img, cx, cy, size):
    r = max(3, size // 10)
    line_w = max(1, size // 55)

    nodes = [
        (cx,              cy - size // 5),
        (cx - size // 8,  cy),
        (cx + size // 8,  cy),
        (cx,              cy + size // 5),
    ]
    edges = [(0, 1), (0, 2), (1, 3), (2, 3), (1, 2)]

    edge_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(edge_layer)
    for i, j in edges:
        d.line([nodes[i], nodes[j]], fill=(*PURPLE, 160), width=line_w)
    img.alpha_composite(edge_layer)

    d2 = ImageDraw.Draw(img)
    for i, (nx, ny) in enumerate(nodes):
        glow = r + line_w + 1
        glow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow_layer)
        gd.ellipse([nx - glow, ny - glow, nx + glow, ny + glow],
                   fill=(*PURPLE, 80))
        img.alpha_composite(glow_layer)
        nc = PURPLE if i != 3 else GREEN
        d2.ellipse([nx - r, ny - r, nx + r, ny + r], fill=(*nc, 255))


def draw_diamond(draw, cx, cy, half, color, alpha=255):
    pts = [(cx, cy - half), (cx + half, cy), (cx, cy + half), (cx - half, cy)]
    draw.polygon(pts, fill=(*color, alpha))


def make_icon(size: int) -> Image.Image:
    s = size

    # Start fully transparent
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    # ── Background ────────────────────────────────────────────────────────────
    bg_r = int(s * 0.20)
    composite_rounded(img, BG, (0, 0, s, s), bg_r, 255)

    # ── Node graph ────────────────────────────────────────────────────────────
    node_cx = s // 2
    node_cy = int(s * 0.32)
    node_size = int(s * 0.38)
    draw_node_graph(img, node_cx, node_cy, node_size)

    # Central diamond (Claude sparkle)
    d = ImageDraw.Draw(img)
    dh = int(s * 0.065)
    draw_diamond(d, node_cx, node_cy, dh, PURPLE, 255)
    draw_diamond(d, node_cx, node_cy, max(2, int(dh * 0.42)), WHITE, 220)

    # ── Three progress bars ───────────────────────────────────────────────────
    bar_h    = max(4, int(s * 0.055))
    pad_x    = int(s * 0.13)
    bar_w    = s - pad_x * 2
    bar_gap  = int(s * 0.038)
    bars_top = int(s * 0.57)

    bars = [
        (0.52, PURPLE),
        (0.74, YELLOW),
        (0.35, GREEN),
    ]
    for i, (pct, color) in enumerate(bars):
        by = bars_top + i * (bar_h + bar_gap)
        draw_progress_bar(img, pad_x, by, bar_w, bar_h, pct, color)

    # ── API status dot ────────────────────────────────────────────────────────
    dot_r = max(3, int(s * 0.05))
    dot_x = s - pad_x - dot_r
    dot_y = int(s * 0.89)
    d2 = ImageDraw.Draw(img)
    d2.ellipse([dot_x - dot_r, dot_y - dot_r,
                dot_x + dot_r, dot_y + dot_r], fill=(*GREEN, 255))
    hi = max(1, dot_r // 3)
    d2.ellipse([dot_x - hi, dot_y - dot_r + hi,
                dot_x + hi, dot_y - dot_r + hi * 3], fill=(*WHITE, 140))

    return img


SIZES = [16, 32, 64, 128, 256, 512, 1024]


def main():
    iconset = "icon.iconset"
    os.makedirs(iconset, exist_ok=True)

    for sz in SIZES:
        icon = make_icon(sz)
        if sz <= 512:
            icon.save(f"{iconset}/icon_{sz}x{sz}.png")
        if sz >= 32:
            half = sz // 2
            icon.save(f"{iconset}/icon_{half}x{half}@2x.png")

    print(f"Saved {len(os.listdir(iconset))} PNGs to {iconset}/")
    ret = os.system("iconutil -c icns icon.iconset -o icon.icns")
    if ret == 0:
        print("Created icon.icns")
    else:
        print("iconutil failed")


if __name__ == "__main__":
    main()
