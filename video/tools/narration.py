"""The measured values the narration quotes, so script.json never goes stale: "{ttft}" etc. are filled from assets.json.

script.json entries are a list of sentences, or {"need": "<assets key>", "say": [...]} for a scene that only exists
when that measurement exists (story.html drops the same scenes). A sentence is a string, or
{"if": "<flag>", "say": "...", "else": "..."} for a line that depends on the result ("else" may be left out).
"""
import json
import os
import re
import statistics
from pathlib import Path


def script_path(here):
    """script.json for the ecosystem cut, script-solo.json for the standalone cut ($MIRA_VARIANT)."""
    return Path(here) / ("script-solo.json" if os.environ.get("MIRA_VARIANT", "eco") == "solo" else "script.json")


def load(work):
    w = Path(work)
    w = w if (w / "assets.json").exists() else w.parent      # measured results are shared by both cuts
    return json.loads((w / "assets.json").read_text(encoding="utf-8"))


def values(a):
    h = a["hero"]["llm"] or {}
    r, pw, src = a.get("race") or {}, a.get("power") or {}, a.get("source") or {}
    tickets = next((d["chunks"] for d in a["ingest"]["docs"] if d["name"].lower().endswith(".csv")), 0)
    b = re.search(r"(\d+(?:\.\d+)?)B", a["llm_model"])
    trace = a["cpu"].get("trace") or [a["cpu"]["answer_median"]]
    return {"llm_b": b.group(1) if b else "", "chunks": a["ingest"]["chunks"], "tickets": tickets,
            "ingest_s": f"{a['ingest']['seconds']:.0f}" if a["ingest"]["seconds"] >= 10 else f"{a['ingest']['seconds']:.1f}",
            "search_ms": f"{a['search']['ms']:.0f}", "ttft": f"{h.get('ttft_s') or 0:.1f}", "tps": f"{h.get('tokens_per_s') or 0:.0f}",
            "cpu": f"{a['cpu']['answer_median']:.0f}", "race_ratio": f"{(r.get('total_s') or 0) / (h.get('total_s') or 1):.1f}", "npu_cpu": f"{statistics.median(trace):.0f}",
            "questions": a["series_summary"]["questions"], "grounded": a["series_summary"]["grounded"],
            "median": f"{a['series_summary']['median_s']:.1f}", "page": src.get("page", ""),
            "race_cpu": f"{r.get('cpu_median') or 0:.0f}", "race_tps": f"{r.get('tokens_per_s') or 0:.0f}",
            "npu_w": f"{pw.get('npu_w') or 0:.0f}", "cpu_w": f"{pw.get('cpu_w') or 0:.0f}"}


def flags(a):
    h, r, pw = a["hero"]["llm"] or {}, a.get("race") or {}, a.get("power") or {}
    return {"race": bool(r), "source": bool(a.get("source")), "power": bool(pw.get("npu_w")),
            "power_race": bool(pw.get("npu_w") and pw.get("cpu_w")),
            "npu_faster": bool(r) and (h.get("total_s") or 1e9) < (r.get("total_s") or 0)}


def script(work, path):
    a = load(work)
    v, f = values(a), flags(a)
    out = []
    for scene in json.loads(Path(path).read_text(encoding="utf-8")):
        if isinstance(scene, dict):
            if not a.get(scene["need"]):
                continue
            scene = scene["say"]
        lines = []
        for s in scene:
            if isinstance(s, dict):
                s = s["say"] if f[s["if"]] else s.get("else")
            if s:
                lines.append(s.format(**v))
        out.append(lines)
    return out
