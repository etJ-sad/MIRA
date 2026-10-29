"""Flattens a MIRA script for syncpool: a JSON list of scenes, each a list of sentences.

usage: python video/tools/export_script.py video/script.json <syncpool>/scripts/mira-ecosystem.json
       python video/tools/export_script.py video/script-solo.json <syncpool>/scripts/mira-standalone.json
Every scene and every branch of a result-dependent line is kept (tools/check.py must see all of them); the measured
numbers stay as {placeholders}, because they change with every run.
"""
import json
import sys
from pathlib import Path

out = []
for scene in json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")):
    lines = scene["say"] if isinstance(scene, dict) else scene
    out.append([x for s in lines for x in ([s] if isinstance(s, str) else [s["say"], *([s["else"]] if s.get("else") else [])])])
Path(sys.argv[2]).write_text(json.dumps(out, indent=0, ensure_ascii=False) + "\n", encoding="utf-8")
print("exported", len(out), "scenes ->", sys.argv[2])
