#!/usr/bin/env python3
"""Haystack social video renderer.

Turns a batch file (marketing/batches/*.json) into finished 1080x1920 MP4s:
stock clip scenes (Mixkit) with bold captions, a Haystack end card, and soft music.

  python3 marketing/render.py marketing/batches/batch-01.json [--only 03] [--out /tmp/hs-out]

Each video in the batch:
  {"id": "01-green-flags", "music": 657,
   "scenes": [{"clip": 4530, "start": 2.0, "dur": 3.2, "text": "Big words", "small": "optional line", "pos": "center"}],
   "end": {"line": "optional line above the App Store prompt"}}
"""
import argparse, json, os, re, subprocess, sys, textwrap, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
W, H, FPS = 1080, 1920, 30
NAVY, GOLD, GOLD_SOFT, CREAM = (31, 42, 68), (200, 146, 46), (245, 231, 204), (251, 247, 239)
FONT = {k: str(HERE / 'fonts' / f'InterDisplay-{k}.otf') for k in ('ExtraBold', 'Bold', 'SemiBold', 'Medium')}
CACHE = Path(os.environ.get('HS_CACHE', '/tmp/hs-cache'))
END_DUR, XF = 3.2, 0.35


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"command failed: {' '.join(map(str, cmd))[:300]}\n{r.stderr[-1500:]}")


def fetch(kind, i):
    CACHE.mkdir(parents=True, exist_ok=True)
    if kind == 'clip':
        p, url = CACHE / f'clip-{i}.mp4', f'https://assets.mixkit.co/videos/{i}/{i}-720.mp4'
    else:
        p, url = CACHE / f'music-{i}.mp3', f'https://assets.mixkit.co/music/{i}/{i}.mp3'
    if not p.exists() or p.stat().st_size < 10000:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=180) as r, open(p, 'wb') as f:
            f.write(r.read())
    return p


def wrap(draw, text, font, width):
    words, lines, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if draw.textlength(t, font=font) <= width or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines


EMOJI = re.compile('[\U0001F000-\U0001FFFF\u2600-\u27BF\uFE0F\u200D]')


def caption_png(scene, path):
    """Big white caption with a soft dark glow, plus an optional smaller line (emoji stripped: the font has none)."""
    scene = {**scene, 'text': EMOJI.sub('', scene.get('text', '')).strip(), 'small': EMOJI.sub('', scene.get('small', '')).strip()}
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    big = scene.get('text', '')
    size = scene.get('size', 92 if len(big) < 40 else 78)
    f_big = ImageFont.truetype(FONT['ExtraBold'], size)
    f_small = ImageFont.truetype(FONT['SemiBold'], 50)
    lines = wrap(d, big, f_big, W - 150)
    small = wrap(d, scene.get('small', ''), f_small, W - 170) if scene.get('small') else []
    lh, sh = int(size * 1.14), 64
    block = len(lines) * lh + (30 + len(small) * sh if small else 0)
    pos = scene.get('pos', 'center')
    y = {'top': 300, 'center': (H - block) // 2 - 60, 'lower': H - block - 520}[pos]
    shadow = Image.new('RGBA', (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(shadow)
    # Soft dark band behind the text block so captions stay readable on bright footage.
    sd.rectangle((0, y - 90, W, y + block + 90), fill=(0, 0, 0, 120))
    yy = y
    items = [(l, f_big, lh, (255, 255, 255)) for l in lines] + ([('', None, 30, None)] if small else []) + [(l, f_small, sh, GOLD_SOFT) for l in small]
    for text, font, step, color in items:
        if font:
            x = (W - d.textlength(text, font=font)) / 2
            sd.text((x, yy), text, font=font, fill=(0, 0, 0, 200))
            d.text((x, yy), text, font=font, fill=color)
        yy += step
    shadow = shadow.filter(ImageFilter.GaussianBlur(40))
    out = Image.alpha_composite(shadow, img)
    if scene.get('pill', True):
        out = Image.alpha_composite(out, search_pill())
    out.save(path)


def search_pill():
    """Small 'App Store: Haystack Adventist Dating' tag shown on every scene.
    Sits left of TikTok's right-hand buttons and above its caption area."""
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    f1, f2 = ImageFont.truetype(FONT['SemiBold'], 34), ImageFont.truetype(FONT['Bold'], 40)
    a, b = 'App Store:  ', 'Haystack Adventist Dating'
    tw = d.textlength(a, font=f1) + d.textlength(b, font=f2)
    x0, y0 = 60, 1290
    d.rounded_rectangle((x0, y0, x0 + tw + 64, y0 + 84), 42, fill=(251, 247, 239, 235))
    d.text((x0 + 32, y0 + 24), a, font=f1, fill=(110, 110, 120))
    d.text((x0 + 32 + d.textlength(a, font=f1), y0 + 19), b, font=f2, fill=NAVY)
    return layer


def end_card(path, line=None):
    img = Image.new('RGB', (W, H), NAVY)
    icon = Image.open(HERE / 'icon.png').convert('RGB').resize((560, 560), Image.LANCZOS)
    mask = Image.new('L', (560, 560), 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, 559, 559), 120, fill=255)
    img.paste(icon, ((W - 560) // 2, 380), mask)
    d = ImageDraw.Draw(img)
    def center(t, font, y, fill):
        d.text(((W - d.textlength(t, font=font)) / 2, y), t, font=font, fill=fill)
    center('Haystack', ImageFont.truetype(FONT['ExtraBold'], 130), 1000, (255, 255, 255))
    center('Where faith finds love', ImageFont.truetype(FONT['SemiBold'], 58), 1160, GOLD)
    y = 1330
    if line:
        for l in wrap(d, line, ImageFont.truetype(FONT['Medium'], 46), W - 200):
            center(l, ImageFont.truetype(FONT['Medium'], 46), y, CREAM); y += 60
        y += 30
    center('Free on the App Store. Search:', ImageFont.truetype(FONT['SemiBold'], 46), y, GOLD); y += 80
    d.rounded_rectangle((90, y, W - 90, y + 130), 34, fill=(238, 238, 242))
    cx, cy = 160, y + 62   # magnifying glass
    d.ellipse((cx - 24, cy - 24, cx + 16, cy + 16), outline=(120, 120, 130), width=7)
    d.line((cx + 12, cy + 12, cx + 34, cy + 34), fill=(120, 120, 130), width=8)
    f = ImageFont.truetype(FONT['Bold'], 54)
    d.text((215, y + 33), 'Haystack Adventist Dating', font=f, fill=(20, 20, 30))
    d.rectangle((215 + d.textlength('Haystack Adventist Dating', font=f) + 8, y + 30, 215 + d.textlength('Haystack Adventist Dating', font=f) + 13, y + 100), fill=(0, 122, 255))
    img.save(path)


GRADE = ("eq=contrast=1.04:saturation=1.08:brightness=-0.02,"
         "colorbalance=rs=.04:gs=.01:bs=-.04:rm=.03:bm=-.03,vignette=PI/5")


def render_video(v, out_dir, work):
    work.mkdir(parents=True, exist_ok=True)
    parts = []
    for n, sc in enumerate(v['scenes']):
        src = fetch('clip', sc['clip'])
        png = work / f"{v['id']}-cap{n}.png"; caption_png(sc, png)
        seg = work / f"{v['id']}-s{n}.mp4"
        dur = sc['dur'] + XF
        # Cover-crop to 9:16 with a slow push-in, warm grade, caption fades in.
        frames = int(dur * FPS) + 2
        vf = (f"[0:v]fps={FPS},scale=-2:{H},crop={W}:{H},setsar=1,"
              f"zoompan=z='1+0.07*on/{frames}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={W}x{H}:fps={FPS},{GRADE}[bg];"
              f"[1:v]format=rgba,fade=in:st=0.15:d=0.35:alpha=1[cap];[bg][cap]overlay=0:0,format=yuv420p")
        run(['ffmpeg', '-y', '-v', 'error', '-ss', str(sc.get('start', 0)), '-t', str(dur), '-i', str(src),
             '-loop', '1', '-t', str(dur), '-i', str(png), '-filter_complex', vf, '-an',
             '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', str(seg)])
        parts.append((seg, dur))
    endpng = work / f"{v['id']}-end.png"; end_card(endpng, (v.get('end') or {}).get('line'))
    endseg = work / f"{v['id']}-end.mp4"
    run(['ffmpeg', '-y', '-v', 'error', '-loop', '1', '-t', str(END_DUR), '-i', str(endpng),
         '-vf', f"fps={FPS},zoompan=z='1+0.0006*on':d=1:s={W}x{H}:fps={FPS},format=yuv420p",
         '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', str(endseg)])
    parts.append((endseg, END_DUR))

    # Crossfade everything together, then lay music under it.
    inputs, fc, prev, offset = [], [], '0:v', 0.0
    for i, (p, d) in enumerate(parts):
        inputs += ['-i', str(p)]
    for i in range(1, len(parts)):
        offset += parts[i - 1][1] - XF
        lbl = f'x{i}'
        fc.append(f"[{prev}][{i}:v]xfade=transition=fade:duration={XF}:offset={offset:.3f}[{lbl}]")
        prev = lbl
    total = offset + parts[-1][1]
    music = fetch('music', v.get('music', 657))
    mi = len(parts)
    fc.append(f"[{mi}:a]atrim=start={v.get('music_start', 8)}:duration={total:.3f},asetpts=PTS-STARTPTS,"
              f"volume=0.55,afade=in:d=0.6,afade=out:st={total - 1.4:.3f}:d=1.4[a]")
    out = out_dir / f"{v['id']}.mp4"
    run(['ffmpeg', '-y', '-v', 'error', *inputs, '-i', str(music), '-filter_complex', ';'.join(fc),
         '-map', f'[{prev}]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
         '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', '-r', str(FPS), str(out)])
    return out, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('batch'); ap.add_argument('--only'); ap.add_argument('--out', default='/tmp/hs-out')
    a = ap.parse_args()
    batch = json.loads(Path(a.batch).read_text())
    out_dir = Path(a.out); out_dir.mkdir(parents=True, exist_ok=True)
    for v in batch['videos']:
        if a.only and not v['id'].startswith(a.only):
            continue
        out, total = render_video(v, out_dir, out_dir / 'work')
        print(f"{out}  {total:.1f}s")


if __name__ == '__main__':
    main()
