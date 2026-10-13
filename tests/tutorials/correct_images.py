"""Corrects the figures of the original course notebooks for bdopt, keeping them as they are.

The originals (besos/image/ of the course folder) are not redrawn: only the words that name the old toolbox are replaced, in the
same font, at the same size and at the same place; arrows, boxes, colours and the transparency of the PNG are untouched.

    besos_surrogate_overview.png -> tutorials/image/surrogate_overview.png
        besos.parameters / .objectives / .problem   -> bdopt.parameters / .objectives / .problem
        besos.sampling                              -> bdopt.sampling
        besos.evaluator.EvaluatorEP                 -> bdopt.EnergyPlusEvaluator
        SKLearn, Tensorflow                         -> bdopt.surrogate
        besos.optimizer                             -> bdopt.optimize
    flow_diagram.PNG -> tutorials/image/flow_diagram.PNG
        "Net-zero Navigator" (a tool of the old toolbox) -> "Optimisation"

Every new name exists in bdopt 0.2.0 (checked when this was written). Run in image B (Pillow, numpy), with the original folder
and the Windows fonts mounted read-only:

    docker run --rm -v "<besos folder>/image:/img:ro" -v "C:/Windows/Fonts:/fonts:ro" -v "<repo>:/repo" \
        --entrypoint python jupyter:smartbuilding-surrogate /repo/tests/tutorials/correct_images.py
"""
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFont

IMG = Path("/img")
FONTS = Path("/fonts")
OUT = Path(os.environ.get("OUT_DIR", "/repo/tutorials/image"))

REGULAR, ITALIC = FONTS / "calibri.ttf", FONTS / "calibrii.ttf"


def ink_bbox(arr, box, dark=110):
    """Bounding box (x0, y0, x1, y1) of the dark opaque pixels inside `box` of an RGBA array."""
    x0, y0, x1, y1 = box
    sub = arr[y0:y1, x0:x1]
    luma = sub[..., :3].astype(float).mean(axis=2)
    ink = (sub[..., 3] > 128) & (luma < dark)
    ys, xs = np.where(ink)
    if not len(xs):
        raise SystemExit(f"no text in {box}")
    return x0 + xs.min(), y0 + ys.min(), x0 + xs.max() + 1, y0 + ys.max() + 1


def width(parts, size, fonts):
    return sum(ImageFont.truetype(str(fonts[italic]), size).getlength(t) for t, italic in parts)


def fit_size(parts, target, fonts):
    """The font size at which `parts` is `target` pixels wide (the size the original was drawn at)."""
    lo, hi = 8.0, 400.0
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if width(parts, mid, fonts) < target else (lo, mid)
    return (lo + hi) / 2


def retext(img, box, old, new, fonts=None, pad=6, new_box_right=None, center=False):
    """Replace the text `old` found in `box` by `new`. Both are lists of (text, italic).

    The size is the one at which `old` has the width it has in the picture; the new text starts at the same left edge and
    shares the top of the old one's ink. The area of the old text is wiped with the background of the box (opaque white or
    transparent, whichever the picture has there) before drawing.
    """
    fonts = fonts or {False: REGULAR, True: ITALIC}
    arr = np.array(img)
    x0, y0, x1, y1 = ink_bbox(arr, box)
    size = fit_size(old, x1 - x0, fonts)
    # top of the ink of the old text at this size, measured from the baseline, to keep the same vertical place
    first = ImageFont.truetype(str(fonts[old[0][1]]), size)
    top_off = first.getbbox(old[0][0], anchor="ls")[1]
    baseline = y0 - top_off
    # background: the pixel just left of the ink, outside the glyphs
    bg = arr[y0, max(x0 - pad - 4, 0)].copy()
    wipe_x1 = new_box_right or (x1 + pad)
    arr[max(y0 - pad, 0):y1 + pad + 12, max(x0 - pad, 0):wipe_x1] = bg
    out = Image.fromarray(arr)
    # draw the new text as a coverage mask, then blend black into the picture through it
    mask = Image.new("L", out.size, 0)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(mask)
    x = float(x0)
    if center:
        x = (x0 + x1) / 2 - width(new, size, fonts) / 2
    start = x
    for text, italic in new:
        font = ImageFont.truetype(str(fonts[italic]), size)
        draw.text((x, baseline), text, fill=255, font=font, anchor="ls")
        x += font.getlength(text)
    m = np.array(mask).astype(float) / 255.0
    px = np.array(out).astype(float)
    opaque_bg = bg[3] > 200
    if opaque_bg:
        for c in range(3):
            px[..., c] = px[..., c] * (1 - m)                       # black ink over the opaque background
    else:
        px[..., :3] = np.where(m[..., None] > 0, 0, px[..., :3])    # black ink on a transparent background
        px[..., 3] = np.maximum(px[..., 3], m * 255)
    result = Image.fromarray(px.round().astype(np.uint8), "RGBA")
    return result, (round(size, 1), x0, y0, x1, y1, round(x - start))


def main():
    # ------------------------------------------------------------------ the surrogate overview (start of notebook 2)
    img = Image.open(IMG / "besos_surrogate_overview.png").convert("RGBA")
    it = lambda t: (t, True)       # noqa: E731  (the toolbox name is in italics in the original)
    rg = lambda t: (t, False)      # noqa: E731
    edits = [
        # (search box, old parts, new parts)   boxes are in the pixels of the 4180 x 1920 picture
        ((2950, 20, 4060, 130), [it("besos"), rg(".parameters")], [it("bdopt"), rg(".parameters")]),
        ((2950, 140, 4060, 250), [it("besos"), rg(".objectives")], [it("bdopt"), rg(".objectives")]),
        ((2950, 262, 4060, 372), [it("besos"), rg(".problem")], [it("bdopt"), rg(".problem")]),
        ((2940, 515, 4050, 615), [it("besos"), rg(".sampling")], [it("bdopt"), rg(".sampling")]),
        ((2930, 625, 4050, 705), [it("besos"), rg(".evaluator.EvaluatorEP")], [it("bdopt"), rg(".EnergyPlusEvaluator")]),
        ((3100, 1000, 4170, 1120), [it("SKLearn, Tensorflow")], [it("bdopt"), rg(".surrogate")]),
        ((3330, 1330, 4170, 1470), [it("besos"), rg(".optimizer")], [it("bdopt"), rg(".optimize")]),
    ]
    for box, old, new in edits:
        img, info = retext(img, box, old, new)
        print("overview", "".join(t for t, _ in old), "->", "".join(t for t, _ in new), info)
    img.save(OUT / "surrogate_overview.png")

    # ------------------------------------------------------------------------ the flow diagram (start of notebook 1)
    flow = Image.open(IMG / "flow_diagram.PNG").convert("RGBA")
    font_name = sys.argv[1] if len(sys.argv) > 1 else "calibri"
    fonts = {False: FONTS / ("segoeui.ttf" if font_name == "segoe" else "calibri.ttf")}
    fonts[True] = fonts[False]
    flow, info = retext(flow, (930, 5, 1290, 45), [("Net-zero Navigator", False)], [("Optimisation", False)], fonts=fonts, pad=4, center=True)
    print("flow", info, font_name)
    flow.save(OUT / ("flow_diagram.PNG" if len(sys.argv) < 3 else sys.argv[2]))


if __name__ == "__main__":
    main()
