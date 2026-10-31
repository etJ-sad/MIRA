"""Real MIRA results on the NPU for the story video: ingest, search, streamed answers, CPU load, the real web UI.

usage: python video/tools/assets.py <work dir>              needs OVMS running with LLM and embeddings on the NPU
       python video/tools/assets.py <work dir> --preview    no NPU: simulated models, every number is a placeholder
writes <work>/assets.json, <work>/assets/app_answer.jpg and <work>/assets/source_page.png

The race runs the same LLM files with the same prompt on the CPU (openvino_genai), the way it would run on a PC
without an NPU. Power is the SoC package power from the Windows "Energy Meter" counters (CPU, GPU and NPU share
the package), sampled once a second; without those counters the video leaves power out.

Run with the video venv, which has MIRA installed (pip install -e .). The demo documents in samples/fz-300 are
read exactly like customer documents; the answers shown in the video are the ones MIRA gives here.
"""
import json
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import psutil

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from mira.app import create_app  # noqa: E402
from mira.config import Settings  # noqa: E402
from mira.ovms import _THINK, OvmsClient  # noqa: E402
from mira.rag import Mira  # noqa: E402
from mira.store import VectorStore  # noqa: E402

W = Path(sys.argv[1]).resolve()
PREVIEW = "--preview" in sys.argv
A = W / "assets"
A.mkdir(parents=True, exist_ok=True)
DOCS = ROOT / "samples" / "fz-300"

HERO = "Anlage 3 zeigt E-417, was tun?"
UNKNOWN = "Welches Anzugsmoment gilt für die Spindelmutter an Anlage 7?"
SERIES = [
    "Was bedeutet E-126 und wie behebe ich das?",
    "Wie oft muss ich die Filtermatten am Schaltschrank prüfen?",
    "Welches Fett kommt in die Zentralschmierung?",
    "Werkzeugwechsler meldet E-203, was tun?",
    "Wie prüfe ich die Werkzeugspannung?",
    "Was war die Ursache bei den letzten E-417 Tickets?",
    "Druckluft zu niedrig, wo suche ich?",
    "Darf ich E-418 einfach quittieren?",
    "Welche Batterie muss bei E-612 getauscht werden und worauf achte ich?",
    "Hydrauliköl zu heiß, was prüfe ich?",
]


class TimedOvms(OvmsClient):
    """The MIRA client, but chat() streams so the first token and every following one get a timestamp."""

    def __init__(self, settings):
        super().__init__(settings)
        self.last = {}

    def chat(self, messages, max_tokens):
        self.messages = messages
        body = {"model": self.settings.llm_model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.1,
                "stream": True, "stream_options": {"include_usage": True}, "chat_template_kwargs": {"enable_thinking": False}}
        t0, stamps, parts, usage = time.perf_counter(), [], [], None
        with self._http.stream("POST", "/chat/completions", json=body) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line.startswith("data:") or line.strip() == "data: [DONE]":
                    continue
                ev = json.loads(line[5:])
                usage = ev.get("usage") or usage
                for ch in ev.get("choices", []):
                    piece = (ch.get("delta") or {}).get("content")
                    if piece:
                        stamps.append(time.perf_counter() - t0)
                        parts.append(piece)
        tokens = (usage or {}).get("completion_tokens") or len(stamps)
        prompt = (usage or {}).get("prompt_tokens")
        gen = stamps[-1] - stamps[0] if len(stamps) > 1 else 0
        self.last = {"ttft_s": round(stamps[0], 3) if stamps else None, "total_s": round(time.perf_counter() - t0, 3),
                     "tokens": tokens, "prompt_tokens": prompt, "tokens_per_s": round((tokens - 1) / gen, 2) if gen else None,
                     "stamps": [round(s, 3) for s in stamps]}
        return _THINK.sub("", "".join(parts)).strip()


class FakeOvms:
    """--preview only: hashed bag-of-words embeddings and a scripted answer, so the page can be built without the NPU."""

    def __init__(self, settings):
        self.settings, self.last = settings, {}

    def embed(self, texts):
        import hashlib
        import math
        out = []
        for t in texts:
            v = [0.0] * 256
            for w in re.findall(r"\w+", t.split("Query: ", 1)[-1].lower()):
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 256] += 1
            n = math.sqrt(sum(x * x for x in v)) or 1
            out.append([x / n for x in v])
        time.sleep(0.01 * len(texts))
        return out

    def chat(self, messages, max_tokens):
        self.messages = messages
        if "Anzugsmoment" in messages[-1]["content"]:
            return "Weiß ich nicht."
        text = ("Ursache: Übertemperatur am Spindelmotor, meist eine verstopfte Filtermatte am Schaltschranklüfter M7 [1][2].\n"
                "1. Anlage am Hauptschalter Q1 ausschalten und gegen Wiedereinschalten sichern [1].\n"
                "2. Filtermatte am Schaltschrank links prüfen und tauschen [1].\n"
                "3. Lüfter M7 auf Lauf prüfen [2].\n"
                "4. Motor 20 Minuten abkühlen lassen, dann Störung quittieren [1]. Bei früheren Fällen half der Tausch der Filtermatte [3].")
        n = len(text) // 4
        stamps = [1.2 + k / 12 for k in range(n)]
        self.last = {"ttft_s": 1.2, "total_s": stamps[-1], "tokens": n, "prompt_tokens": 1500, "tokens_per_s": 12.0,
                     "stamps": [round(s, 3) for s in stamps]}
        return text

    def health(self):
        return {}


class CpuMeter:
    """Total CPU load of the machine, sampled every 100 ms while a block runs."""

    def __init__(self):
        self.samples, self._on = [], False

    def __enter__(self):
        self._on = True
        psutil.cpu_percent(None)
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()
        return self

    def _run(self):
        while self._on:
            time.sleep(0.1)
            self.samples.append(psutil.cpu_percent(None))

    def __exit__(self, *exc):
        self._on = False
        self._t.join()


class PowerMeter:
    """SoC package power in watts, once a second, from the Windows Energy Meter counters (RAPL); empty when absent."""

    def __enter__(self):
        self.samples = []
        try:
            self._p = subprocess.Popen(["typeperf", r"\Energy Meter(*)\Power", "-si", "1"], stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL, text=True)
        except OSError:
            self._p = None
            return self
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()
        return self

    def _run(self):
        col = None
        for line in self._p.stdout:
            cells = [c.strip('"') for c in line.strip().split('","')]
            if col is None and len(cells) > 1 and "Energy Meter" in line:
                col = next((i for i, c in enumerate(cells) if "PKG" in c.upper()), None)
                continue
            if col is not None and len(cells) > col:
                try:
                    self.samples.append(round(float(cells[col]) / 1000, 2))   # mW -> W
                except ValueError:
                    pass

    def __exit__(self, *exc):
        if self._p:
            self._p.terminate()
            self._t.join(timeout=3)

    @property
    def median(self):
        return round(statistics.median(self.samples), 1) if self.samples else None


def cpu_race(messages, model_dir, max_tokens):
    """The same LLM files and the same prompt on the CPU, streamed, so both runs can be shown side by side."""
    import openvino_genai as ov_genai
    pipe = ov_genai.LLMPipeline(str(model_dir), "CPU")
    tok = pipe.get_tokenizer()
    msgs = [dict(m) for m in messages]
    msgs[-1]["content"] += " /no_think"               # Qwen3: answer directly, as MIRA asks OVMS to
    prompt = tok.apply_chat_template(msgs, add_generation_prompt=True)
    cfg = ov_genai.GenerationConfig()
    cfg.max_new_tokens, cfg.do_sample = max_tokens, False
    pipe.generate("Hallo", ov_genai.GenerationConfig(max_new_tokens=4))   # warm-up, as the NPU model is warm too
    stamps, parts = [], []

    def stream(piece):
        stamps.append(time.perf_counter() - t0)
        parts.append(piece)
        return False                                   # keep going

    with CpuMeter() as cm, PowerMeter() as pm:
        t0 = time.perf_counter()
        pipe.generate(prompt, cfg, stream)
        total = time.perf_counter() - t0
    gen = stamps[-1] - stamps[0] if len(stamps) > 1 else 0
    text = _THINK.sub("", "".join(parts)).strip()
    return {"device": "CPU", "answer": text, "ttft_s": round(stamps[0], 3) if stamps else None, "total_s": round(total, 3),
            "tokens": len(stamps), "tokens_per_s": round((len(stamps) - 1) / gen, 2) if gen else None,
            "stamps": [round(x, 3) for x in stamps], "cpu_trace": cm.samples, "cpu_median": round(statistics.median(cm.samples), 1),
            "power_w": pm.median, "power_trace": pm.samples}


def source_page(pdf, page_no, code, name):
    """Renders the cited manual page and finds the band from the fault code's heading to the next code."""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf))
    page = doc[page_no - 1]
    pw, ph = page.get_size()
    scale = 1100 / pw
    page.render(scale=scale).to_pil().save(A / name)
    tp = page.get_textpage()
    text = tp.get_text_range()
    heads = [(m.start(), m.group(0)) for m in re.finditer(r"E-\d{3}\s", text)]
    box = None
    for k, (i, c) in enumerate(heads):
        if c.strip() == code:
            top = tp.get_charbox(i)[3]                                 # pdf y grows upwards
            nxt = next((j for j, c2 in heads[k + 1:] if c2.strip() != code), None)
            bottom = tp.get_charbox(nxt)[3] + 14 if nxt is not None else 60
            box = [36 * scale, (ph - top - 8) * scale, (pw - 36) * scale, (ph - bottom) * scale]
            break
    return {"file": name, "w": round(pw * scale), "h": round(ph * scale), "page": page_no, "doc": Path(pdf).name,
            "highlight": [round(v, 1) for v in box] if box else None}


def sh(cmd):
    try:
        return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def model_devices(models_dir):
    """Device each model is compiled for, as written in its OVMS graph (models\\<name>\\graph.pbtxt)."""
    out = {}
    for g in Path(models_dir).rglob("graph.pbtxt"):
        m = re.search(r'(?:target_)?device:\s*"([^"]+)"', g.read_text(errors="replace"))
        if m:
            out[g.parent.relative_to(models_dir).as_posix()] = m.group(1)
    return out


settings = Settings(data_dir=W / "mira-data")
shutil.rmtree(settings.data_dir, ignore_errors=True)
settings.docs_dir.mkdir(parents=True, exist_ok=True)
client = FakeOvms(settings) if PREVIEW else TimedOvms(settings)
store = VectorStore.open(str(settings.index_dir), settings.collection)
mira = Mira(settings, client, store)
out = {"placeholder": PREVIEW, "llm_model": settings.llm_model, "embed_model": settings.embed_model,
       "host": platform.node(), "cpu_name": sh("(Get-CimInstance Win32_Processor).Name") or platform.processor(),
       "npu_name": sh("(Get-PnpDevice -PresentOnly | Where-Object FriendlyName -like '*AI Boost*').FriendlyName") or "Intel AI Boost",
       "ovms_version": os.environ.get("OVMS_VERSION", ""), "ovms": {} if PREVIEW else client.health(),
       "devices": {} if PREVIEW else model_devices(os.environ.get("MIRA_MODELS", ROOT / "models"))}
if PREVIEW:
    out |= {"host": "PREVIEW", "cpu_name": "Intel Core Ultra 9 285HX", "npu_name": "Intel AI Boost",
            "devices": {settings.llm_model: "NPU", settings.embed_model: "NPU"}}

# --- read: every demo document, embeddings on the NPU ---------------------------------------------------------
docs = []
for f in sorted(DOCS.iterdir()):
    target = settings.docs_dir / f.name
    shutil.copy(f, target)
    t0 = time.perf_counter()
    n = mira.ingest_file(target)
    docs.append({"name": f.name, "chunks": n, "seconds": round(time.perf_counter() - t0, 2)})
chunks = sum(d["chunks"] for d in docs)
secs = sum(d["seconds"] for d in docs)
out["ingest"] = {"docs": docs, "chunks": chunks, "seconds": round(secs, 2), "chunks_per_s": round(chunks / secs, 1)}

# --- search: one query embedding on the NPU plus the vector search --------------------------------------------
from mira.rag import QUERY_PREFIX  # noqa: E402

ms = []
for _ in range(25):
    t0 = time.perf_counter()
    [v] = client.embed([QUERY_PREFIX + HERO])
    hits = store.search(v, settings.top_k)
    ms.append((time.perf_counter() - t0) * 1000)
out["search"] = {"ms": round(statistics.median(ms[5:]), 1),
                 "hits": [{"doc": h.doc_name, "location": h.location, "score": round(h.score, 3)} for h in hits]}


def ask(q):
    client.last = {}
    a = mira.ask(q)
    return {"question": q, "answer": a.answer, "grounded": a.grounded, "seconds": round(a.seconds, 2),
            "sources": [{"number": s.number, "doc": s.doc_name, "location": s.location, "score": s.score} for s in a.sources],
            "llm": client.last or None}


# --- answer: the hero question, with CPU load ------------------------------------------------------------------
ask(SERIES[0])                                        # warm-up, not shown
with CpuMeter() as idle, PowerMeter() as idle_pw:
    time.sleep(4)
with CpuMeter() as busy, PowerMeter() as npu_pw:
    out["hero"] = ask(HERO)
out["power"] = {"idle_w": idle_pw.median, "npu_w": npu_pw.median, "npu_trace": npu_pw.samples}

# --- the race: the same prompt on the CPU ----------------------------------------------------------------------
if PREVIEW:
    n = out["hero"]["llm"]["tokens"]
    out["race"] = {"device": "CPU", "answer": out["hero"]["answer"], "ttft_s": 3.4, "tokens": n, "tokens_per_s": 7.0,
                   "stamps": [round(3.4 + k / 7, 3) for k in range(n)], "total_s": round(3.4 + n / 7, 2),
                   "cpu_trace": [88 + (k * 7 % 11) for k in range(120)], "cpu_median": 93.0, "power_w": 41.0, "power_trace": []}
    out["power"] |= {"idle_w": 4.0, "npu_w": 9.0}
    busy.samples[:] = [4 + (k * 5 % 4) for k in range(len(busy.samples) or 100)]
else:
    try:
        out["race"] = cpu_race(client.messages, Path(os.environ.get("MIRA_MODELS", ROOT / "models")) / settings.llm_model,
                               settings.max_answer_tokens)
    except Exception as error:  # noqa: BLE001 - the video leaves the race out rather than showing made-up numbers
        print("race skipped:", error)
out["power"]["cpu_w"] = out["race"]["power_w"] if "race" in out else None
code = (re.search(r"E-\d{3}", HERO) or [None])[0]
pdf_src = next((s for s in out["hero"]["sources"] if s["doc"].lower().endswith(".pdf") and s["location"].startswith("Seite")), None)
if pdf_src:
    out["source"] = source_page(DOCS / pdf_src["doc"], int(pdf_src["location"].split()[-1]), code, "source_page.png") | {"number": pdf_src["number"]}
elif PREVIEW:                                         # simulated search cites tickets; show the manual page anyway
    from mira.parsers import parse_file
    pdf = next(DOCS.glob("*.pdf"))
    pg = next(int(x.location.split()[-1]) for x in parse_file(pdf) if code in x.text)
    out["source"] = source_page(pdf, pg, code, "source_page.png") | {"number": 1}
out["unknown"] = ask(UNKNOWN)
[v] = client.embed([QUERY_PREFIX + UNKNOWN])
out["unknown"]["best_score"] = round(max((h.score for h in store.search(v, 1)), default=0), 3)
out["unknown"]["min_score"] = settings.min_score
with CpuMeter() as busy_series:
    out["series"] = [ask(q) for q in SERIES]
cpu = busy.samples + busy_series.samples
out["cpu"] = {"idle_median": round(statistics.median(idle.samples), 1), "answer_median": round(statistics.median(cpu), 1),
              "answer_p95": round(sorted(cpu)[int(len(cpu) * .95)], 1), "trace": busy.samples, "cores": psutil.cpu_count()}
if PREVIEW:
    out["cpu"] |= {"idle_median": 2.0, "answer_median": 6.0, "answer_p95": 9.0}
sec = [r["seconds"] for r in out["series"]]
tps = [r["llm"]["tokens_per_s"] for r in out["series"] if r["llm"] and r["llm"]["tokens_per_s"]]
out["series_summary"] = {"questions": len(sec), "median_s": round(statistics.median(sec), 2), "total_s": round(sum(sec), 1),
                         "grounded": sum(r["grounded"] for r in out["series"]), "tokens_per_s_median": round(statistics.median(tps), 1) if tps else None}
if PREVIEW:
    out["hero"]["seconds"] = round(out["hero"]["llm"]["total_s"] + 0.3, 2)
    for k, r in enumerate(out["series"]):
        r["seconds"], r["grounded"] = round(6 + (k * 37 % 10) * 0.4, 1), k != 7
    out["series_summary"] |= {"median_s": 8.0, "total_s": 80.0, "grounded": 9}

# --- the real web UI, answering the hero question --------------------------------------------------------------
import uvicorn  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

srv = uvicorn.Server(uvicorn.Config(create_app(settings, client, store), host="127.0.0.1", port=8091, log_level="warning"))
threading.Thread(target=srv.run, daemon=True).start()
for _ in range(100):
    try:
        httpx.get("http://127.0.0.1:8091/api/health", timeout=1)
        break
    except httpx.HTTPError:
        time.sleep(0.1)
with sync_playwright() as pw:
    b = None
    for ch in ("msedge", "chrome", None):
        try:
            b = pw.chromium.launch(channel=ch) if ch else pw.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
            break
        except Exception:  # noqa: BLE001 - try the next installed browser
            continue
    p = b.new_page(viewport={"width": 1584, "height": 861}, device_scale_factor=1)
    p.goto("http://127.0.0.1:8091/")
    p.wait_for_selector("#docs li")
    p.fill("#question", HERO)
    with p.expect_response("**/api/ask", timeout=180000):
        p.click("#send")
    p.wait_for_selector("#chat .meta")
    p.wait_for_timeout(300)
    p.screenshot(path=str(A / "app_answer.jpg"), type="jpeg", quality=92)
    box = lambda sel: p.eval_on_selector_all(sel, "es => { const r = es[es.length - 1].getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom].map(Math.round) }")  # noqa: E731
    out["app"] = {"w": 1584, "h": 861, "status": box("#status"), "question": box("#chat .q"),
                  "answer": box("#chat .a"), "sources": box("#chat .sources") if p.query_selector("#chat .sources") else None,
                  "docs": box("#docs")}
    b.close()
srv.should_exit = True

(W / "assets.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
h = out["hero"]["llm"] or {}
print("assets ok", "PREVIEW" if PREVIEW else "", chunks, "chunks", f"search {out['search']['ms']} ms",
      f"ttft {h.get('ttft_s')} s", f"{h.get('tokens_per_s')} tok/s", f"cpu {out['cpu']['answer_median']} %", out["devices"])
