"""Renders Overload batch-2 videos (1080x1920, ~13-15 s) from batch2.json.

Each video: a 3-cut stock hook (Mixkit, graded dark and grainy like batch 1) with a headline, then app screens
captured from the real app with a caption band on top, then the batch-1 end card. Music: the licensed Mixkit
tracks already used in batch 1 (rotated), faded out at the end.

Usage: python3 batch2/render.py [video-id ...]   (needs ffmpeg, Pillow, stock clips in $CLIPS)
"""
import json, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CLIPS = os.environ.get("CLIPS", "/tmp/mk/clips")
AUDIO = os.environ.get("AUDIO", "/tmp/mk/audio")
OUT = os.path.join(HERE, "videos")
TMP = "/tmp/b2tmp"
FONT = os.path.join(ROOT, "haystack", "fonts", "InterDisplay-ExtraBold.otf")
W, H, FPS = 1080, 1920, 30
ORANGE, WHITE, BG = (255, 107, 26), (255, 255, 255), (14, 16, 18)
os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True)

def run(args):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode: raise SystemExit(f"ffmpeg failed: {' '.join(args)[:300]}\n{r.stderr[-1500:]}")

def italic_text(lines, size=78, width=W, pad=40):
    """Heavy italic headline: line 1 white, line 2 orange, centered, soft shadow. Returns RGBA image."""
    font = ImageFont.truetype(FONT, size)
    lh = int(size * 1.18)
    img = Image.new("RGBA", (width + 200, lh * len(lines) + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, (txt, col) in enumerate(lines):
        tw = d.textlength(txt, font=font)
        d.text(((img.width - tw) / 2, pad + i * lh), txt, font=font, fill=col)
    # shear for italic
    shear = 0.18
    img = img.transform(img.size, Image.AFFINE, (1, shear, -shear * img.height / 2, 0, 1, 0), Image.BICUBIC)
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0)); shadow.paste((0, 0, 0, 200), mask=img.split()[3])
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    out = Image.new("RGBA", img.size, (0, 0, 0, 0)); out.alpha_composite(shadow, (0, 6)); out.alpha_composite(img)
    return out.crop((100, 0, 100 + width, out.height))

def fit_lines(a, b, size=78):
    font = ImageFont.truetype(FONT, size)
    while max(font.getlength(a), font.getlength(b)) > W - 110 and size > 48:
        size -= 2; font = ImageFont.truetype(FONT, size)
    return size

def hook_segment(v, k):
    """3 quick stock cuts with the headline over them."""
    parts = []
    for j, c in enumerate(v["hook"]["clips"]):
        src = os.path.join(CLIPS, f"{c['id']}.mp4"); dur = c.get("dur", 0.97)
        info = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height", "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip().split(",")
        sw, sh = int(info[0]), int(info[1])
        if sw > sh:  # landscape → 9:16 crop around the subject
            cw = int(sh * 9 / 16); x = max(0, min(sw - cw, int(sw * c.get("x", 0.5) - cw / 2)))
            crop = f"crop={cw}:{sh}:{x}:0,"
        else:
            crop = ""
        o = f"{TMP}/{k}_h{j}.mp4"
        vf = (f"{crop}scale={W}:{H}:flags=lanczos,setsar=1,fps={FPS},"
              "eq=brightness=-0.07:contrast=1.12:saturation=0.55,vignette=PI/4,noise=alls=10:allf=t,format=yuv420p")
        run(["ffmpeg", "-v", "error", "-y", "-ss", str(c["t"]), "-t", str(dur), "-i", src, "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", o])
        parts.append(o)
    lst = f"{TMP}/{k}_hl.txt"; open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
    joined = f"{TMP}/{k}_hj.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
    a, b = v["hook"]["text"]; size = fit_lines(a, b, 82)
    t = italic_text([(a, WHITE), (b, ORANGE)], size=size); tp = f"{TMP}/{k}_ht.png"
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0)); canvas.alpha_composite(t, (0, int(H * 0.42 - t.height / 2))); canvas.save(tp)
    o = f"{TMP}/{k}_hook.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", joined, "-i", tp, "-filter_complex", "[0:v][1:v]overlay=0:0,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(FPS), o])
    return o

def screen_segment(v, k, i, s):
    """App screen under a caption band, with a slow push-in."""
    shot = Image.open(os.path.join(HERE, "screens", s["img"])).convert("RGB")
    scale = W / shot.width; shot = shot.resize((W, int(shot.height * scale)), Image.LANCZOS)
    top = int(s.get("y", 0) * scale); band = 420
    view = shot.crop((0, top, W, top + H - band))
    frame = Image.new("RGB", (W, H), BG); frame.paste(view, (0, band))
    # fade the screen into the caption band
    grad = Image.new("L", (1, 90)); [grad.putpixel((0, y), int(255 * (1 - y / 89))) for y in range(90)]
    frame.paste(Image.new("RGB", (W, 90), BG), (0, band), grad.resize((W, 90)))
    a, b = s["text"]; size = fit_lines(a, b, 72)
    t = italic_text([(a, WHITE), (b, ORANGE)], size=size)
    fr = frame.convert("RGBA"); fr.alpha_composite(t, (0, max(20, int(band / 2 - t.height / 2) + 10)))
    p = f"{TMP}/{k}_s{i}.png"; fr.convert("RGB").save(p)
    dur = s.get("dur", 3.0); n = int(dur * FPS)
    o = f"{TMP}/{k}_s{i}.mp4"
    vf = (f"scale={W*2}:{H*2},zoompan=z='1+0.035*on/{n}':x='iw/2-(iw/zoom/2)':y='ih*0.25-(ih/zoom*0.25)':d={n}:s={W}x{H}:fps={FPS},format=yuv420p")
    run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", p, "-vf", vf, "-frames:v", str(n), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", o])
    return o

def render(v, n):
    k = v["id"]
    segs = [hook_segment(v, k)] + [screen_segment(v, k, i, s) for i, s in enumerate(v["screens"])] + [os.path.join(HERE, "endcard.mp4")]
    lst = f"{TMP}/{k}_all.txt"; open(lst, "w").write("".join(f"file '{p}'\n" for p in segs))
    silent = f"{TMP}/{k}_v.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(FPS), "-pix_fmt", "yuv420p", silent])
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", silent], capture_output=True, text=True).stdout)
    track = os.path.join(AUDIO, v["music"] + ".m4a")
    out = os.path.join(OUT, f"{n:02d}-{k}.mp4")
    af = f"atrim=0:{dur},afade=t=in:d=0.15,afade=t=out:st={max(0, dur - 1.2)}:d=1.2,loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.85:level=false"
    run(["ffmpeg", "-v", "error", "-y", "-i", silent, "-stream_loop", "-1", "-i", track, "-filter_complex", f"[1:a]{af}[a]", "-map", "0:v", "-map", "[a]",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-maxrate", "6M", "-bufsize", "12M", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out])
    print(f"{out}  {dur:.1f}s")

if __name__ == "__main__":
    data = json.load(open(os.path.join(HERE, "batch2.json")))
    only = set(sys.argv[1:])
    for n, v in enumerate(data["videos"], 1):
        if not only or v["id"] in only: render(v, n)
