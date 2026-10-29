# "The third processor, part 2": MIRA story video

A 16:9 (1920×1080) animated video, the sequel to the Lumen story video. The NPU tells the story again: with Lumen it
learned to see, with MIRA it learns to explain. A language model with billions of parameters answers maintenance
questions on a few watts, right next to the machine. Proof of concept of what the NPU in every new industrial PC is for.
Same look, same score and the same helpers as `video/` in the Lumen repo, so the two videos belong together.

Everything shown as a result is measured on the machine that runs `make.ps1` (AURORA-HP: Intel Core Ultra 9 285HX,
OVMS with both models on the NPU); nothing is mocked up. The documents MIRA reads are demo documents for a fictional
machine (`demo/`), and the video says so.

| File | What it is |
|--|--|
| `mira-story.mp4` | The finished video (Git LFS), written by `make.ps1`. |
| `story.html` | The whole animation on one canvas: 19 scenes, time-driven (`kSeek(t)` draws any frame). Each scene has a `see:` line. |
| `script.json` | Narration, one list of sentences per scene. `{ttft}`, `{tps}` … are filled from the measurement, so the voice always quotes the real numbers. Scene length follows the voice. |
| `demo/` | `make_docs.py` and its output: a manual (PDF), a fault code list (Excel) and 64 old tickets (CSV) for the fictional FZ-300. |
| `music.*` | Optional: a licensed track (`music.wav`, `.mp3` or `.flac`). When present it replaces the generated score. |
| `make.ps1` | Rebuilds the MP4: MIRA results on the NPU → narration → timing → music/mix → pages → frames. `-Preview` runs without the NPU. |
| `tools/` | `assets.py` (runs MIRA against OVMS on the NPU, streams the answers, samples the CPU, screenshots the real web UI), `narration.py` (fills the numbers into the script), `voice.py` (Kokoro TTS, local), `mix.py` (narration track, generated score, ducking), `build.py` (data, fonts and audio into the page), `render.py` (headless Edge/Chrome frames → ffmpeg). |

## Story

1. Every new industrial PC has three processors. The CPU runs the machine, the GPU draws the screen, the third is the NPU.
2. With Lumen it learned to see. One skill is still missing: explain.
3. 02:47, line 3 stops with E-417. The manual has hundreds of pages, the expert is on holiday.
4. Answers need a language model: usually a big GPU or the cloud.
5. This time the NPU runs it: the LLM (int4) and an embedding model, both compiled for the NPU.
6. MIRA: maintenance assistant, offline, next to the machine.
7. Reading: three documents, N passages into vectors on the NPU, measured time.
8. Asking: the real top passages with their scores and the threshold, search time.
9. Answering: the real answer, replayed at its measured token timestamps, with the cited sources.
10. Speed: every token on a time axis, first token, tokens per second.
11. "Weiß ich nicht": best score below the threshold, the LLM is not even asked.
12. The real MIRA web UI with the answer (screenshot taken during the run).
13. Proof: each model's OVMS graph says `device: "NPU"`, `/v1/config` reports them `AVAILABLE`.
14. CPU load of the whole PC while the NPU writes: it stays free for the machine.
15. Ten questions in a row: seconds per answer, answered with sources or not.
16. No cloud, no telemetry, the manuals stay in the factory.
17. "Every new industrial PC already has me. With Lumen, I see. With MIRA, I explain."

## Rebuild

```powershell
.\scripts\start-ovms.ps1                      # or let make.ps1 start it
py -3.12 -m venv build\video-venv
build\video-venv\Scripts\pip install -e . playwright kokoro-onnx soundfile imageio-ffmpeg numpy psutil reportlab
video\make.ps1                                # ~15 min, writes video\mira-story.mp4
video\make.ps1 -Preview                       # without NPU: placeholder numbers, marked on every frame
```

Open `video\work\preview.html` in a browser for a scrubbable preview with sound (click to play).

## Notes

- Voice, score, mix and picture treatment are the Lumen ones (Kokoro `af_heart`, generated score 12 dB under the voice,
  -16 LUFS, crossfades, chapter titles, vignette and grain). Scene ids map onto the Lumen score in `mix.py`.
- An answer longer than its scene is replayed faster and the scene says so (`replay ×N`); the timestamps are the measured ones.
- CPU load is the whole PC (psutil, every 100 ms), not only the MIRA process.
- Siemens Sans and the Siemens logo come from a local Kassia checkout for the render only (`MIRA_FONTS`, `MIRA_LOGO`).
