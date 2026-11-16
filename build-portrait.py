#!/usr/bin/env python3
"""Turn a photo into the binary-glyph portrait used by the hero cards.

The portrait is a 57 x 76 grid of 0/1 glyphs (3036 cells) on the same
5.34 x 6.48 grid as the reference profile. Cell brightness is rank-matched
to the reference portrait's own grey ramp, so the tone statistics of the
result are identical to the reference no matter what photo goes in.

Usage:  python3 build-portrait.py path/to/photo.jpg
Writes: assets/portrait-dark.json, assets/portrait-light.json
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ASSETS = Path(__file__).parent / 'assets'

COLS, ROWS = 57, 76
X0, Y0 = 16.0, 28.6
DX, DY = 5.337, 6.48
FONT = 9.1

# grey ramp measured off the reference portrait (chromatic glasses excluded)
RAMP = {'dark': (40, 254), 'light': (18, 218)}
# the reference draws its light portrait as the negative of the dark one
LIGHT_A, LIGHT_B = -0.9346, 254.9


def saliency_centre(grey):
    """Spectral-residual saliency, returns the centre of mass as fractions."""
    small = np.asarray(Image.fromarray(grey).resize((256, 150), Image.LANCZOS), dtype=np.float64)
    f = np.fft.fft2(small)
    logamp, phase = np.log(np.abs(f) + 1e-8), np.angle(f)
    from scipy import ndimage
    res = logamp - ndimage.uniform_filter(logamp, 3)
    sal = np.abs(np.fft.ifft2(np.exp(res + 1j * phase))) ** 2
    sal = ndimage.gaussian_filter(sal, 2.5)
    sal = (sal - sal.min()) / (sal.max() - sal.min() + 1e-9)
    ys, xs = np.mgrid[0:sal.shape[0], 0:sal.shape[1]]
    w = sal ** 2
    return float((xs * w).sum() / w.sum() / sal.shape[1]), \
           float((ys * w).sum() / w.sum() / sal.shape[0])


def crop(im):
    """Crop the photo to the portrait aspect, centred on the salient subject."""
    w, h = im.size
    grey = np.asarray(im.convert('L'))
    cx, cy = saliency_centre(grey)
    cx = min(max(cx, 0.3), 0.7)
    target = (COLS * DX) / (ROWS * DY)          # 0.618, taller than wide
    if w / h > target:                           # too wide -> trim the sides
        nw, nh = int(round(h * target)), h
    else:                                        # too tall -> trim top/bottom
        nw, nh = w, int(round(w / target))
    x = int(round(cx * w - nw / 2))
    y = int(round(cy * h - nh / 2))
    x = min(max(x, 0), w - nw)
    y = min(max(y, 0), h - nh)
    return im.crop((x, y, x + nw, y + nh)), (x, y, nw, nh)


def sample(im):
    """Cell brightness: mostly the area mean, a little of the local max."""
    a = np.asarray(im.convert('L'), dtype=np.float64) / 255.0
    h, w = a.shape
    out = np.zeros((ROWS, COLS))
    for r in range(ROWS):
        y0, y1 = int(r * h / ROWS), max(int((r + 1) * h / ROWS), int(r * h / ROWS) + 1)
        for c in range(COLS):
            x0, x1 = int(c * w / COLS), max(int((c + 1) * w / COLS), int(c * w / COLS) + 1)
            cell = a[y0:y1, x0:x1]
            out[r, c] = 0.62 * cell.mean() + 0.38 * cell.max()
    # gentle contrast stretch on percentiles, so a flat photo still reads
    lo, hi = np.percentile(out, 2), np.percentile(out, 98)
    out = np.clip((out - lo) / (hi - lo + 1e-9), 0, 1)
    return out ** 0.92


def rank_match(vals, lo, hi):
    """Give every cell the reference's tone rank -> identical histogram."""
    flat = vals.ravel()
    order = np.argsort(flat, kind='stable')
    ramp = np.linspace(lo, hi, flat.size)         # sorted target greys
    out = np.empty(flat.size)
    out[order] = ramp
    return out.reshape(vals.shape)


def char_for(r, c, lum):
    h = hashlib.md5(('%d:%d:%d' % (r, c, int(lum * 255))).encode()).digest()[0]
    return '1' if h & 1 else '0'


OCCUPANCY = 0.701      # the reference draws 3036 of the 4332 grid cells
GLYPHS = 3036          # exact count in the reference portrait


def cells(vals):
    """Brightest 70% of cells (the silhouette), tone-matched to the dark ramp."""
    lo, hi = RAMP['dark']
    flat = vals.ravel()
    order = np.argsort(flat, kind='stable')[-GLYPHS:]          # brightest cells
    order = order[np.argsort(flat[order], kind='stable')]      # dark -> bright
    tone = np.empty(flat.size)
    tone[order] = np.linspace(lo, hi, order.size)
    return order, tone


def glyphs(order, tone, theme):
    """The reference light portrait is the exact negative of the dark one."""
    out = []
    for i in order:
        r, c = divmod(int(i), COLS)
        d = float(tone[i])
        g = int(round(d if theme == 'dark' else max(0.0, min(255.0, LIGHT_A * d + LIGHT_B))))
        out.append({
            'x': round(X0 + c * DX, 1),
            'y': round(Y0 + r * DY, 1),
            'fill': '#%02x%02x%02x' % (g, g, g),
            'size': FONT,
            'ch': char_for(r, c, d),
        })
    return out


def main():
    src = Path(sys.argv[1] if len(sys.argv) > 1 else '/tmp/newpic.jpg')
    im = Image.open(src).convert('RGB')
    cropped, box = crop(im)
    print('source %dx%d -> crop %s (aspect %.3f)' % (im.size[0], im.size[1], box, box[2] / box[3]))
    vals = sample(cropped)
    print('cells: mean %.2f  p10 %.2f  p50 %.2f  p90 %.2f'
          % (vals.mean(), np.percentile(vals, 10), np.percentile(vals, 50), np.percentile(vals, 90)))
    cropped.save('/tmp/portrait_crop.png')
    order, tone = cells(vals)
    for theme in ('dark', 'light'):
        g = glyphs(order, tone, theme)
        assert len(g) == 3036, '%s: expected 3036 glyphs, got %d' % (theme, len(g))
        (ASSETS / ('portrait-%s.json' % theme)).write_text(json.dumps(g))
        ones = sum(1 for x in g if x['ch'] == '1')
        print('%s: %d glyphs (%d ones) -> assets/portrait-%s.json' % (theme, len(g), ones, theme))


if __name__ == '__main__':
    main()
