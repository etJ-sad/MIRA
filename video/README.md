# MIRA story videos

Two 16:9 (1920×1080) cuts of the same material, aligned with Lumen and Greenforest through `etJ-sad/syncpool`
(shared lines, phrase table, `tools/check.py`). Everything shown as a result is measured on the machine that runs
`make.ps1` (AURORA-HP: Intel Core Ultra 9 285HX, OVMS with both models on the NPU); nothing is mocked up. The documents
MIRA reads are demo documents for a fictional machine (`demo/`), and the video says so.

| Cut | File | What it is |
|--|--|--|
| Ecosystem | `mira-story-ecosystem.mp4` | "The third processor, part 2": the NPU tells the story, shares its opening, proof and closing lines with Lumen and Greenforest on purpose and ends with all three: "With Lumen, I see. With MIRA, I explain. With Greenforest, I look after the machine I live in." Script: `script.json`. |
| Standalone | `mira-story-standalone.mp4` | MIRA on its own: another voice (`bf_emma`), third-person narrator, opens with the 2:47 stop, chapters of its own ("Two forty-seven", "MIRA", "Under the hood", "On site") and no line from syncpool's `shared-lines.json`. Script: `script-solo.json`. |

| File | What it is |
|--|--|
| `mira-story-*.mp4` | The finished videos (Git LFS), written by `make.ps1`. |
| `story.html` | The whole animation on one canvas: 21 scenes, each cut picks its order (`ORDER` for `eco` / `solo`), time-driven (`kSeek(t)` draws any frame). Each scene has a `see:` line. |
| `script.json`, `script-solo.json` | Narration per cut, one list of sentences per scene. `{ttft}`, `{tps}` … are filled from the measurement, so the voice always quotes the real numbers. Scene length follows the voice. |
| `demo/` | `make_docs.py` and its output: a manual (PDF), a fault code list (Excel) and 64 old tickets (CSV) for the fictional FZ-300. |
| `music.*` | Optional: a licensed track (`music.wav`, `.mp3` or `.flac`). When present it replaces the generated score. |
| `make.ps1` | Rebuilds both MP4s (`-Variant` eco, solo or both) from one measurement: MIRA results on the NPU → narration → timing → music/mix → pages → frames. `-Preview` runs without the NPU, `-SkipAssets` reuses the last measurement. |
| `tools/` | `assets.py` (runs MIRA against OVMS on the NPU, streams the answers, races the same prompt on the CPU, samples CPU load and package power, renders the cited manual page, screenshots the real web UI), `narration.py` (fills the numbers into the script), `export_script.py` (flattens a script for syncpool), `voice.py` (Kokoro TTS, local), `mix.py` (narration track, generated score, ducking), `build.py` (data, fonts and audio into the page), `render.py` (headless Edge/Chrome frames → ffmpeg). |

## Story (ecosystem cut)

1. Every new industrial PC has three processors. The CPU runs the machine, the GPU draws the screen, the third is the NPU.
2. With Lumen it learned to see. One skill is still missing: explain.
3. 02:47, line 3 stops with E-417. The manual has hundreds of pages, the expert is on holiday.
4. Answers need a language model: usually a big GPU or the cloud.
5. This time the NPU runs it: the LLM (int4) and an embedding model, both compiled for the NPU.
6. MIRA: maintenance assistant, offline, next to the machine.
7. Reading: three documents, N passages into vectors on the NPU, measured time.
8. Asking: the real top passages with their scores and the threshold, search time.
9. Answering: the real answer, replayed at its measured token timestamps, with the cited sources.
10. The source: the cited manual page slides in, the camera pushes onto the passage the answer came from, and it lights up.
11. Speed: every token on a time axis, first token, tokens per second.
12. The race: the same model files and the same prompt on the CPU (openvino_genai), split screen on one clock,
    both answers streaming at their measured timestamps, CPU load and package watts underneath.
13. "Weiß ich nicht": best score below the threshold, the LLM is not even asked.
14. The real MIRA web UI with the answer (screenshot taken during the run).
15. Proof: each model's OVMS graph says `device: "NPU"`, `/v1/config` reports them `AVAILABLE`.
16. CPU load of the whole PC while the NPU writes: it stays free for the machine.
17. Ten questions in a row: seconds per answer, answered with sources or not.
18. No cloud, no telemetry, the manuals stay in the factory.
19. "Every new industrial PC already has me. With Lumen, I see. With MIRA, I explain. With Greenforest, I look after the machine I live in. One NPU. Three jobs."

## Rebuild

```powershell
.\scripts\start-ovms.ps1                      # or let make.ps1 start it
py -3.12 -m venv build\video-venv
build\video-venv\Scripts\pip install -e . playwright kokoro-onnx soundfile imageio-ffmpeg numpy psutil reportlab pypdfium2 openvino-genai
video\make.ps1                                # ~25 min, writes video\mira-story-ecosystem.mp4 and -standalone.mp4
video\make.ps1 -Preview                       # without NPU: placeholder numbers, marked on every frame
```

Open `video\work\preview.html` in a browser for a scrubbable preview with sound (click to play).

## Notes

- Voice, score, mix and picture treatment are the Lumen ones (Kokoro `af_heart`, generated score 12 dB under the voice,
  -16 LUFS, crossfades, chapter titles, vignette and grain). Scene ids map onto the Lumen score in `mix.py`.
- An answer longer than its scene is replayed faster and the scene says so (`replay ×N`); the timestamps are the measured ones.
- CPU load is the whole PC (psutil, every 100 ms), not only the MIRA process.
- Power is the SoC package (CPU, GPU and NPU together) from the Windows Energy Meter counters, once a second. Without
  those counters, every line about watts drops out of picture and narration; nothing is estimated.
- The race leaves the integrated GPU out on purpose: in this story it draws the HMI. The point is the PC without an NPU,
  where the AI would land on the CPU next to the machine control. If the CPU is as fast, the narration says so
  ("The CPU keeps up") and the scene leads with the CPU load instead. Scenes whose measurement failed are dropped.
- Siemens Sans and the Siemens logo come from a local Kassia checkout for the render only (`MIRA_FONTS`, `MIRA_LOGO`).

## syncpool

After changing a script, export it and check the standalone cut before pushing syncpool:

```powershell
build\video-venv\Scripts\python video\tools\export_script.py video\script.json ..\syncpool\scripts\mira-ecosystem.json
build\video-venv\Scripts\python video\tools\export_script.py video\script-solo.json ..\syncpool\scripts\mira-standalone.json
cd ..\syncpool; python tools\check.py scripts\mira-standalone.json     # must print "no repeats"
```
