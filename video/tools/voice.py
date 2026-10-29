"""Narration with Kokoro TTS (local), one take per sentence so pauses and subtitles are exact.

usage: voice.py <models dir> <work dir>/voice
The measured numbers in script.json ("{ttft}" ...) are filled from <work dir>/assets.json first (narration.py).
writes s_NN_KK.wav (48 kHz, cleaned) and timeline.json: per scene the sentence offsets/lengths and the voice length.
"""
import json
import os
import re
import sys

from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

def up2(a):
    """2x band-limited upsampling (FFT zero padding), 24 -> 48 kHz."""
    n = len(a)
    f = np.fft.rfft(a)
    return np.fft.irfft(np.concatenate([f, np.zeros(n - len(f) + 1)]), 2 * n) * 2


HERE = os.path.dirname(os.path.abspath(__file__))
M, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
k = Kokoro(os.path.join(M, "kokoro-v1.0.onnx"), os.path.join(M, "voices-v1.0.bin"))
V = k.get_voice_style("af_heart")
SAY = {"NPU": "N P U", "CPU": "C P U", "GPU": "G P U", "PLC": "P L C", "OPC UA": "O P C U A", "MQTT": "M Q T T",
       "OpenVINO": "Open Veeno", "Lumen": "Loomen", "MIRA": "Meera", "AI": "A I", "PC": "P C", "HMI": "H M I"}
LEAD, GAP, FIRST = 0.45, 0.42, 1.6   # seconds before the first sentence, between sentences, extra lead of scene 0


def say(s):
    for a, b in SAY.items():
        s = re.sub(r"\b" + re.escape(a) + r"(?=\W|$)", b, s)
    return s


sys.path.insert(0, HERE)
from narration import script  # noqa: E402

S = script(Path(out).parent, os.path.join(HERE, "..", "script.json"))
tl = []
for i, sents in enumerate(S):
    off = LEAD + (FIRST if i == 0 else 0)
    rows = []
    for j, s in enumerate(sents):
        a, sr = k.create(say(s), voice=V, speed=0.95, lang="en-us")
        a = np.asarray(a, dtype=np.float64)
        nz = np.where(np.abs(a) > 0.008)[0]
        a = a[max(0, nz[0] - 120):nz[-1] + 1800] if len(nz) else a
        a = up2(a)
        fd = 480
        a[:fd] *= np.linspace(0, 1, fd)
        a[-fd * 4:] *= np.linspace(1, 0, fd * 4)
        sf.write(f"{out}/s_{i:02d}_{j:02d}.wav", a.astype(np.float32), 48000)
        d = len(a) / 48000
        rows.append([round(off, 3), round(d, 3)])
        off += d + GAP * (1.25 if s.endswith(("?", ".")) and len(s) > 40 else 1)
    tl.append({"sent": rows, "len": round(off - GAP, 3)})
json.dump(tl, open(f"{out}/timeline.json", "w"))
print("voice ok", round(sum(x["len"] for x in tl), 1), "s")
