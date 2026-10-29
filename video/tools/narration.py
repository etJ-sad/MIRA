"""The measured values the narration quotes, so script.json never goes stale: "{ttft}" etc. are filled from assets.json."""
import json
import re
from pathlib import Path


def values(work):
    a = json.loads((Path(work) / "assets.json").read_text(encoding="utf-8"))
    h = a["hero"]["llm"] or {}
    tickets = next((d["chunks"] for d in a["ingest"]["docs"] if d["name"].lower().endswith(".csv")), 0)
    b = re.search(r"(\d+(?:\.\d+)?)B", a["llm_model"])
    return {"llm_b": b.group(1) if b else "", "chunks": a["ingest"]["chunks"], "tickets": tickets,
            "ingest_s": f"{a['ingest']['seconds']:.0f}" if a["ingest"]["seconds"] >= 10 else f"{a['ingest']['seconds']:.1f}",
            "search_ms": f"{a['search']['ms']:.0f}", "ttft": f"{h.get('ttft_s') or 0:.1f}", "tps": f"{h.get('tokens_per_s') or 0:.0f}",
            "cpu": f"{a['cpu']['answer_median']:.0f}", "questions": a["series_summary"]["questions"],
            "grounded": a["series_summary"]["grounded"], "median": f"{a['series_summary']['median_s']:.1f}"}


def script(work, path):
    v = values(work)
    return [[s.format(**v) for s in scene] for scene in json.loads(Path(path).read_text(encoding="utf-8"))]
