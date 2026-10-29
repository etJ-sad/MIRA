"""Fills story.html with narration timing, the measured MIRA results and fonts.

usage: build.py <work dir> [mix.mp3] [amp.json]
writes <work>/render.html (for the MP4) and <work>/preview.html (plays in a browser, audio inline when given)
Fonts: Siemens Sans from $MIRA_FONTS (default: the Kassia checkout); without them the page falls back to Segoe UI.
"""
import base64
import json
import os
import re
import sys
from pathlib import Path

from narration import script, script_path

HERE = Path(__file__).resolve().parent
w = Path(sys.argv[1])
audio = Path(sys.argv[2]) if len(sys.argv) > 2 else None
ampf = Path(sys.argv[3]) if len(sys.argv) > 3 else None
VARIANT = os.environ.get("MIRA_VARIANT", "eco")
A = w if (w / "assets.json").exists() else w.parent   # measured results are shared by both cuts

tlf = w / "voice" / "timeline.json"
vo = {"timeline": json.loads(tlf.read_text()), "tail": 0.7, "text": script(w, script_path(HERE.parent)),
      "amp": json.loads(ampf.read_text()) if ampf and ampf.exists() else None} if tlf.exists() else None

data = {"assets": json.loads((A / "assets.json").read_text(encoding="utf-8"))}
# images inline, so the canvas stays exportable (file:// images would taint it) and the page is self-contained
data["images"] = {f.name: "data:image/" + ("png" if f.suffix == ".png" else "jpeg") + ";base64," + base64.b64encode(f.read_bytes()).decode()
                  for f in sorted((A / "assets").iterdir()) if f.suffix in (".jpg", ".png")}
s = (HERE.parent / "story.html").read_text(encoding="utf-8")
s = s.replace("/*VARIANT*/'eco'", json.dumps(VARIANT)).replace("/*VO*/null", json.dumps(vo)).replace("/*DATA*/null", json.dumps(data))
fonts = Path(os.environ.get("MIRA_FONTS", r"C:\Kassia\webui\shared\assets\branding\fonts\siemens-sans-pro"))
if (fonts / "SiemensSansPro_W_Rm.woff").exists():
    b = lambda n: base64.b64encode((fonts / n).read_bytes()).decode()  # noqa: E731
    s = s.replace("/*FONT_RM*/", b("SiemensSansPro_W_Rm.woff")).replace("/*FONT_BD*/", b("SiemensSansPro_W_Bd.woff"))
else:
    s = re.sub(r"@font-face\{[^}]*\}\n", "", s)
(w / "render.html").write_text(s, encoding="utf-8")
if audio and audio.exists():
    s = s.replace("/*AUDIO*/null", json.dumps("data:audio/mpeg;base64," + base64.b64encode(audio.read_bytes()).decode()))
(w / "preview.html").write_text(s, encoding="utf-8")
print("pages ok", VARIANT, "PREVIEW (placeholder numbers)" if data["assets"].get("placeholder") else "measured", "voice" if vo else "no voice")
