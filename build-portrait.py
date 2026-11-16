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


def face_box(im):
    """Find the face with YuNet (downloaded once); None if it cannot."""
    import subprocess
    import cv2
    model = Path('/tmp/yunet.onnx')
    if not model.exists():
        subprocess.run(['curl', '-sL', '--max-time', '90', '-o', str(model),
                        'https://github.com/opencv/opencv_zoo/raw/main/models/'
                        'face_detection_yunet/face_detection_yunet_2023mar.onnx'],
                       check=False)
    if not model.exists():
        return None
    img = cv2.imread(str(im.filename)) if getattr(im, 'filename', None) else None
    if img is None:
        arr = np.asarray(im.convert('RGB'))[:, :, ::-1]
        img = np.ascontiguousarray(arr)
    h, w = img.shape[:2]
    det = cv2.FaceDetectorYN.create(str(model), '', (w, h), 0.45, 0.3, 5000)
    _, faces = det.detect(img)
    if faces is None or len(faces) == 0:
        return None
    f = max(faces, key=lambda r: r[2] * r[3])
    return float(f[0]), float(f[1]), float(f[2]), float(f[3]), float(f[-1])


TARGET = (COLS * DX) / (ROWS * DY)      # 0.618, the portrait box aspect


def crop(im):
    """Head-and-shoulders crop on the portrait aspect, centred on the face."""
    w, h = im.size
    box = face_box(im)
    if box:
        fx, fy, fw, fh, score = box
        cx, cy = fx + fw / 2, fy + fh / 2
        nw = int(round(min(max(fw * 3.1, 120), w)))
        nh = int(round(nw / TARGET))
        if nh > h:
            nh, nw = h, int(round(h * TARGET))
        x = int(round(cx - nw / 2))
        y = int(round(cy + fh * 0.10 - nh * 0.42))
        src = 'face %.2f' % score
    else:
        # no detectable face: a headshot is brightest at the face, so centre the
        # crop on the bright pixels and zoom in on them
        grey = np.asarray(im.convert('L'), dtype=np.float64)
        top = grey >= np.percentile(grey, 98)
        ys, xs = np.nonzero(top)
        wgt = (grey[top] - np.median(grey)) ** 2
        cx = float((xs * wgt).sum() / wgt.sum())
        cy = float((ys * wgt).sum() / wgt.sum())
        nw = int(round(0.48 * min(w, h)))
        nh = int(round(nw / TARGET))
        if nh > h:
            nh, nw = h, int(round(h * TARGET))
        x = int(round(cx - nw / 2))
        y = int(round(cy - nh * 0.46))
        src = 'bright-centroid'
    x = min(max(x, 0), w - nw)
    y = min(max(y, 0), h - nh)
    return im.crop((x, y, x + nw, y + nh)), (x, y, nw, nh), src


def clahe(im, clip=3.0, tiles=8):
    """Local contrast, so a dim photo still reads as a face in the glyph grid."""
    import cv2
    a = np.asarray(im.convert('L'))
    eq = cv2.createCLAHE(clipLimit=clip, tileGridSize=(tiles, tiles)).apply(a)
    return Image.fromarray(eq)


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
    im.filename = str(src)
    cropped, box, how = crop(im)
    print('source %dx%d -> crop %s (aspect %.3f) via %s'
          % (im.size[0], im.size[1], box, box[2] / box[3], how))
    enhanced = clahe(cropped)
    enhanced.save('/tmp/portrait_crop.png')
    vals = sample(enhanced)
    # a backlit subject is darker than its surround; the card wants the subject
    # bright on black, so invert when that is the case
    hh, ww = vals.shape
    centre = vals[hh // 4:hh * 3 // 4, ww // 4:ww * 3 // 4]
    if centre.mean() < vals.mean():
        vals = 1.0 - vals
        print('inverted: subject was darker than the frame (backlit)')
    # smooth the cell field: the reference portrait is all soft gradients, and a
    # 57 x 76 grid is too coarse to carry per-cell photo noise
    from scipy import ndimage
    vals = ndimage.gaussian_filter(vals, 1.2)
    # break exact ties, otherwise equal cells get tones in raster order and the
    # grid shows flat diagonal banding
    vals = vals + np.random.default_rng(7).uniform(0, 1e-6, vals.shape)
    print('cells: mean %.2f  p10 %.2f  p50 %.2f  p90 %.2f'
          % (vals.mean(), np.percentile(vals, 10), np.percentile(vals, 50), np.percentile(vals, 90)))
    order, tone = cells(vals)
    for theme in ('dark', 'light'):
        g = glyphs(order, tone, theme)
        assert len(g) == 3036, '%s: expected 3036 glyphs, got %d' % (theme, len(g))
        (ASSETS / ('portrait-%s.json' % theme)).write_text(json.dumps(g))
        ones = sum(1 for x in g if x['ch'] == '1')
        print('%s: %d glyphs (%d ones) -> assets/portrait-%s.json' % (theme, len(g), ones, theme))


if __name__ == '__main__':
    main()
