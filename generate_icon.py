"""Generate the VS Code extension marketplace icon.

Recolors the Low Gravitas astronaut head (source lives outside this repo at
`../low-grav-head-1080.png`) to match the Low Gravitas Zen theme palette and
composites it onto a rounded square tile with a bg_raised border.

Run from repo root:
    python3 generate_icon.py

Outputs:
    low-gravitas-zen-vscode/low-grav-zen.png       (256x256, marketplace icon)
    low-gravitas-zen-vscode/low-grav-zen-1080.png  (1080x1080, high-res source)

Requires: Pillow (PIL).
"""

from PIL import Image, ImageDraw
import colorsys
import sys
from pathlib import Path


# Theme palette values (must stay in sync with palette.toml)
BG_DEEP = (0x10, 0x0c, 0x00)
BG_RAISED = (0x30, 0x23, 0x18)
THEME_BLUE = (0x55, 0x80, 0xaa)  # base blue from palette

REPO_ROOT = Path(__file__).parent
DEFAULT_SRC = REPO_ROOT.parent / "low-grav-head-1080.png"
OUT_DIR = REPO_ROOT / "low-gravitas-zen-vscode"
OUT_256 = OUT_DIR / "low-grav-zen.png"
OUT_1080 = OUT_DIR / "low-grav-zen-1080.png"


def rgb_to_hsv(r, g, b):
    return colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)


def hsv_to_rgb(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return int(round(r * 255)), int(round(g * 255)), int(round(b * 255))


def recolor_astronaut(img):
    """Hue-based recolor of the source astronaut image.

    Source palette:
      - Blue helmet interior (~#455ca7)
      - Yellow face (~#fcec21) with orange edge shadowing
      - White/gray helmet rim (~#cccccc) with shading
      - Transparent background

    Output palette (tuned to Low Gravitas Zen):
      - Helmet interior → theme base blue #5580aa, gradient preserved
      - Face → desaturated toward theme accent #ffff86, hue variation kept
        so edges still read warmer/orange
      - Helmet rim → warm cream with a power curve on value to keep shadows
    """
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size

    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue

            hue, sat, val = rgb_to_hsv(r, g, b)
            hue_deg = hue * 360

            # Blue helmet interior/visor → theme blue, preserving gradient
            if 190 <= hue_deg <= 270 and sat > 0.15:
                new_hue = 211 / 360
                # Preserve saturation variation but clamp to muted theme range
                new_sat = min(max(sat * 0.70, 0.35), 0.60)
                # Preserve value gradient but darken overall so it reads as
                # a deep theme blue rather than the original bright cobalt
                new_val = val * 0.60
                r, g, b = hsv_to_rgb(new_hue, new_sat, new_val)

            # Yellow face → preserve center→edge gradient, just desaturate.
            # Wider hue range (25°-75°) so deep-orange edge shadows get the
            # same treatment as the yellow center — otherwise pixels with
            # hue < 40° fall through untouched, creating a hard edge.
            elif 25 <= hue_deg <= 75 and sat > 0.3:
                new_hue = hue  # preserve original hue variation
                new_sat = sat * 0.57  # proportional desaturation
                new_val = val  # preserve val variation
                r, g, b = hsv_to_rgb(new_hue, new_sat, new_val)

            # White/gray helmet rim → warm cream.
            # Power curve on value stretches dark-to-light range so shadows
            # don't wash out when the warm tint is applied.
            elif sat < 0.15:
                new_hue = 35 / 360
                new_sat = 0.25
                new_val = (val ** 1.35) * 0.95
                r, g, b = hsv_to_rgb(new_hue, new_sat, new_val)

            px[x, y] = (r, g, b, a)

    return img


def make_tile(size, astronaut, border_px, corner_radius):
    """Build a square tile: bg_raised border, bg_deep fill, astronaut centered.

    Renders at 4x supersample then downscales, so rounded corners stay smooth.
    Border is drawn as two filled rounded rectangles (outer = border color,
    inner = bg fill) — this avoids the corner artifacts that come from
    stacking single-pixel rounded-rectangle outlines.
    """
    scale = 4
    s = size * scale
    b = border_px * scale
    r_outer = corner_radius * scale
    r_inner = max(r_outer - b, 1)

    hi = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(hi)

    draw.rounded_rectangle(
        [(0, 0), (s - 1, s - 1)],
        radius=r_outer,
        fill=BG_RAISED + (255,),
    )
    draw.rounded_rectangle(
        [(b, b), (s - 1 - b, s - 1 - b)],
        radius=r_inner,
        fill=BG_DEEP + (255,),
    )

    tile = hi.resize((size, size), Image.LANCZOS)

    # Composite astronaut centered with slight inset from the border
    inset = border_px + int(size * 0.02)
    inner = size - 2 * inset
    ast = astronaut.resize((inner, inner), Image.LANCZOS)
    tile.paste(ast, (inset, inset), ast)

    return tile


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SRC
    if not src.exists():
        sys.exit(f"source image not found: {src}")

    src_img = Image.open(src)
    print(f"loaded {src}: {src_img.size}")

    astronaut = recolor_astronaut(src_img)

    # 1080 tile: border ~30px (2.8%), corner radius ~140 (~13%)
    tile_1080 = make_tile(1080, astronaut, border_px=30, corner_radius=140)
    tile_1080.save(OUT_1080)
    print(f"wrote {OUT_1080}")

    # 256 tile: border/corner scaled proportionally
    tile_256 = make_tile(256, astronaut, border_px=7, corner_radius=33)
    tile_256.save(OUT_256)
    print(f"wrote {OUT_256}")


if __name__ == "__main__":
    main()
