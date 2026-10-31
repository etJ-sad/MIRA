"""Checks this machine end to end, like Lumen's hardware tests and Greenforest's verify.cmd:
OVMS reachable, both models AVAILABLE and compiled for the NPU, demo documents read on the NPU,
known questions answered with sources, an unknown question answered with "Weiß ich nicht".

Also the NPU demo: answers in a loop, so the NPU graph in Task Manager rises.
Neither touches the user's index; the demo documents go into an in-memory store.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import tempfile
import time
from dataclasses import replace
from pathlib import Path

import httpx

from .config import Settings
from .ovms import _THINK, OvmsClient
from .parsers import SUPPORTED
from .rag import QUERY_PREFIX, Mira
from .store import VectorStore

# question, expected: answered from the documents?, words of which one must appear in the answer
QUESTIONS = [
    ("Anlage 3 zeigt E-417, was tun?", True, ["Filtermatte", "Lüfter"]),
    ("Was bedeutet E-126 und wie behebe ich das?", True, ["Ansaugsieb", "Q14"]),
    ("Welches Anzugsmoment gilt für die Spindelmutter an Anlage 7?", False, []),
]


def _cpu():
    try:
        import psutil
    except ImportError:
        return None
    psutil.cpu_percent(None)
    return psutil


class TimedClient(OvmsClient):
    """OvmsClient whose chat streams, to measure time to the first word and tokens per second."""

    last: dict = {}

    def chat(self, messages: list[dict], max_tokens: int) -> str:
        body = {
            "model": self.settings.llm_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.1,
            "chat_template_kwargs": {"enable_thinking": False},
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        psutil = _cpu()
        started = time.perf_counter()
        first, parts, chunks, usage = None, [], 0, None
        try:
            with self._http.stream("POST", "/chat/completions", json=body) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line.startswith("data:") or line.strip() == "data: [DONE]":
                        continue
                    event = json.loads(line[5:])
                    usage = event.get("usage") or usage
                    for choice in event.get("choices") or []:
                        delta = (choice.get("delta") or {}).get("content")
                        if delta:
                            first = first or time.perf_counter() - started
                            parts.append(delta)
                            chunks += 1
        except httpx.HTTPStatusError:
            # model server without streaming support: plain request, no time to first word
            text = super().chat(messages, max_tokens)
            self.last = {"ttft_s": None, "total_s": round(time.perf_counter() - started, 2), "tokens": None, "tokens_per_s": None}
            return text
        total = time.perf_counter() - started
        tokens = (usage or {}).get("completion_tokens") or chunks
        gen = total - (first or 0)
        self.last = {
            "ttft_s": round(first, 2) if first else None,
            "total_s": round(total, 2),
            "tokens": tokens,
            "tokens_per_s": round(tokens / gen, 1) if tokens and gen > 0 else None,
            "cpu_percent": round(psutil.cpu_percent(None)) if psutil else None,
        }
        return _THINK.sub("", "".join(parts)).strip()


def model_devices(models_dir: Path) -> dict[str, str]:
    """Device each model is compiled for, as written in its OVMS graph (models/<name>/graph.pbtxt)."""
    found = {}
    for graph in Path(models_dir).rglob("graph.pbtxt"):
        match = re.search(r'(?:target_)?device:\s*"([^"]+)"', graph.read_text(errors="replace"))
        if match:
            found[graph.parent.relative_to(models_dir).as_posix()] = match.group(1)
    return found


def _states(config: dict, name: str) -> list[str]:
    return [v.get("state", "?") for v in (config.get(name) or {}).get("model_version_status", [])]


def demo_dir() -> Path | None:
    """Demo documents: $MIRA_SAMPLES, the installed package's samples, or the repository's."""
    here = Path(__file__).resolve().parent
    # repository: <repo>/samples, package: <MIRA>/runtime/app/mira -> <MIRA>/samples
    for candidate in (os.environ.get("MIRA_SAMPLES"), here.parent / "samples" / "fz-300", here.parents[2] / "samples" / "fz-300"):
        if candidate and Path(candidate).is_dir():
            return Path(candidate)
    return None


def run_check(settings: Settings, models_dir: Path | None = None, docs: Path | None = None, say=print,
              transport: httpx.BaseTransport | None = None) -> dict:
    """Runs every check, prints one line per step and returns the report. report["ok"] is the verdict."""
    report: dict = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "ovms_url": settings.ovms_url, "steps": []}

    def step(name: str, ok: bool, detail: str, **data) -> bool:
        report["steps"].append({"step": name, "ok": ok, "detail": detail, **data})
        say(f"  [{'ok' if ok else 'FAIL'}] {name}: {detail}")
        return ok

    client = TimedClient(settings, transport)
    say(f"MIRA check · {settings.ovms_url}")

    # 1. model server and both models
    try:
        config = client.health()
    except Exception as error:
        step("model server", False, f"OVMS not reachable ({error}). Start it first: Start-MIRA.ps1 or scripts\\start-ovms.ps1")
        report["ok"] = False
        return report
    step("model server", True, "reachable")
    devices = model_devices(models_dir) if models_dir and Path(models_dir).is_dir() else {}
    for role, name in (("LLM model", settings.llm_model), ("embedding model", settings.embed_model)):
        states = _states(config, name)
        device = devices.get(name)
        ok = bool(states) and all(s == "AVAILABLE" for s in states) and device in (None, "NPU")
        where = f", compiled for {device}" if device else ", graph not found (pass --models to check the device)"
        step(role, ok, f"{name} {'/'.join(states) or 'not loaded'}{where}", model=name, states=states, device=device)

    # 2. embeddings on the NPU: one query at a time, like a question
    times = []
    try:
        for _ in range(10):
            t = time.perf_counter()
            [vector] = client.embed([QUERY_PREFIX + "Spindel Übertemperatur"])
            times.append((time.perf_counter() - t) * 1000)
        step("embeddings", True, f"{len(vector)} dimensions, {statistics.median(times):.0f} ms per query (median of 10)",
             dims=len(vector), ms_median=round(statistics.median(times), 1))
    except Exception as error:
        step("embeddings", False, str(error))
        report["ok"] = False
        return report

    # 3. demo documents into a store of its own
    docs = docs or demo_dir()
    if not docs:
        step("demo documents", False, "not found (set MIRA_SAMPLES or pass --docs)")
        report["ok"] = False
        return report
    store = VectorStore.open(None, "check")
    with tempfile.TemporaryDirectory() as tmp:
        mira = Mira(replace(settings, data_dir=Path(tmp)), client, store)
        files = sorted(p for p in docs.iterdir() if p.suffix.lower() in SUPPORTED)
        t = time.perf_counter()
        chunks = sum(mira.ingest_file(f) for f in files)
        step("demo documents", chunks > 0, f"{len(files)} files, {chunks} passages read on the NPU in {time.perf_counter() - t:.1f} s",
             files=[f.name for f in files], chunks=chunks)

        # 4. questions with a known outcome
        for question, grounded, words in QUESTIONS:
            client.last = {}
            answer = mira.ask(question)
            [qv] = client.embed([QUERY_PREFIX + question])
            best = max((h.score for h in store.search(qv, 1)), default=0.0)
            stats = client.last
            if grounded:
                hit = any(w.lower() in answer.answer.lower() for w in words)
                ok = answer.grounded and bool(answer.sources) and hit
                where = ", ".join(f"{s.doc_name} {s.location}".strip() for s in answer.sources[:3])
                speed = ""
                if stats.get("ttft_s") is not None:
                    speed = f" · first word {stats['ttft_s']} s, {stats['tokens_per_s']} tok/s"
                if stats.get("cpu_percent") is not None:
                    speed += f", CPU {stats['cpu_percent']} %"
                detail = f"answered from {where}{speed} · {answer.seconds:.1f} s" if ok else f"expected an answer with sources, got: {answer.answer[:160]}"
            else:
                ok = not answer.grounded
                detail = (f"Weiß ich nicht (best score {best:.2f} < {settings.min_score})" if ok and best < settings.min_score
                          else "Weiß ich nicht (from the LLM)" if ok else f"expected 'Weiß ich nicht', got: {answer.answer[:160]}")
            step(f'"{question}"', ok, detail, answer=answer.answer, grounded=answer.grounded, best_score=round(best, 3),
                 sources=[f"{s.doc_name} {s.location}".strip() for s in answer.sources], seconds=round(answer.seconds, 2), **stats)

    report["ok"] = all(s["ok"] for s in report["steps"])
    return report


def npu_demo(settings: Settings, seconds: int, say=print) -> int:
    """Short answers in a loop for `seconds`, so the NPU graph in Task Manager rises and stays up."""
    client = TimedClient(settings)
    messages = [{"role": "user", "content": "Erkläre in fünf Sätzen, warum eine verstopfte Filtermatte am Schaltschrank "
                                            "einen Spindelmotor überhitzen kann."}]
    psutil = _cpu()
    say(f"NPU demo for {seconds} s. Open Task Manager > Performance > NPU now.")
    end, runs, tokens = time.monotonic() + seconds, 0, 0
    started = time.perf_counter()
    while time.monotonic() < end:
        client.chat(messages, 160)
        runs += 1
        tokens += client.last.get("tokens") or 0
        say(f"  answer {runs}: {client.last.get('tokens')} tokens, {client.last.get('tokens_per_s')} tok/s, "
            f"first word {client.last.get('ttft_s')} s")
    took = time.perf_counter() - started
    cpu = f", CPU {psutil.cpu_percent(None):.0f} % on average" if psutil else ""
    say(f"{runs} answers, {tokens} tokens in {took:.0f} s ({tokens / took:.1f} tok/s){cpu}. Model: {settings.llm_model}")
    return 0
