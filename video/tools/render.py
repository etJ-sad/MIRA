"""Renders story frames with a headless browser (installed Edge or Chrome, no browser download; $CHROME_PATH as a fallback).

usage: render.py starts <page.html> <starts.json>                   scene start times and total length
       render.py stills <page.html> <out dir> <t> [t ...]          PNG stills at times t (seconds), prints page errors
       render.py video  <page.html> <out.mp4> <mix.wav> [logo.png] [fps]
"""
import base64
import os
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import sync_playwright


def page_for(pw, html, logo=None):
    for ch in ("msedge", "chrome", None):
        try:
            b = pw.chromium.launch(channel=ch) if ch else pw.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
            break
        except Exception:  # noqa: BLE001 - try the next installed browser
            continue
    p = b.new_page(viewport={"width": 1920, "height": 1080})
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    url = "data:image/png;base64," + base64.b64encode(Path(logo).read_bytes()).decode() if logo else None
    p.add_init_script(f"window.MIRA_RENDER=1;window.MIRA_LOGO_URL={url!r};".replace("None", "null"))
    p.goto(Path(html).resolve().as_uri())
    p.evaluate("kReady")
    return b, p, errs


def main():
    mode, html = sys.argv[1], sys.argv[2]
    with sync_playwright() as pw:
        if mode == "starts":
            b, p, errs = page_for(pw, html)
            Path(sys.argv[3]).write_text(__import__("json").dumps(p.evaluate("kStarts()")))
            print("starts ok", errs)
            b.close()
            return
        if mode == "stills":
            out = Path(sys.argv[3])
            out.mkdir(parents=True, exist_ok=True)
            b, p, errs = page_for(pw, html)
            total = p.evaluate("kLoad()")
            for t in sys.argv[4:]:
                data = p.evaluate(f"kFrame({float(t)}, .9)")
                (out / f"t{float(t):06.1f}.jpg").write_bytes(base64.b64decode(data.split(",", 1)[1]))
            print("total", round(total, 1), "errors", errs)
            b.close()
            return
        mp4, wav = sys.argv[3], sys.argv[4]
        logo = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] != "-" else None
        fps = int(sys.argv[6]) if len(sys.argv) > 6 else 30
        b, p, errs = page_for(pw, html, logo)
        total = p.evaluate("kLoad()")
        n = round(total * fps)
        ff = subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps),
                               "-c:v", "mjpeg", "-i", "-", "-i", wav, "-c:a", "aac", "-b:a", "192k", "-shortest", "-c:v", "libx264",
                               "-vf", "scale=out_range=tv,format=yuv420p", "-color_range", "tv", "-crf", "18", "-preset", "medium", "-movflags", "+faststart", mp4], stdin=subprocess.PIPE)
        for f in range(n):
            data = p.evaluate(f"kFrame({f / fps}, .94)")
            ff.stdin.write(base64.b64decode(data.split(",", 1)[1]))
            if f % 300 == 0:
                print(f"frame {f}/{n}", flush=True)
        ff.stdin.close()
        ff.wait()
        print("done", mp4, n, "frames", "errors", errs)
        b.close()


main()
