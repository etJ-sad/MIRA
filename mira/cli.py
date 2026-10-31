"""Command line: index a folder, ask a question, start the server."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from .config import get_settings
from .ovms import OvmsClient
from .parsers import SUPPORTED
from .rag import Mira
from .store import VectorStore


def _mira() -> Mira:
    settings = get_settings()
    return Mira(settings, OvmsClient(settings), VectorStore.open(str(settings.index_dir), settings.collection))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mira", description="MIRA - lokaler Wartungs-Assistent auf der NPU")
    commands = parser.add_subparsers(dest="command", required=True)

    ingest = commands.add_parser("ingest", help="Dateien oder Ordner einlesen")
    ingest.add_argument("paths", nargs="+", type=Path)

    ask = commands.add_parser("ask", help="Eine Frage stellen")
    ask.add_argument("question")

    serve = commands.add_parser("serve", help="Web-UI und API starten")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8080)

    check = commands.add_parser("check", help="NPU-Prüfung: Modellserver, Modelle auf der NPU, Demo-Fragen")
    check.add_argument("--models", type=Path, default=Path(os.environ.get("MIRA_MODELS", "models")),
                       help="OVMS-Modellordner, um das Zielgerät jedes Modells zu prüfen")
    check.add_argument("--docs", type=Path, help="Ordner mit Testdokumenten (Standard: samples/fz-300)")
    check.add_argument("--report", type=Path, help="Bericht als JSON hierhin schreiben")

    demo = commands.add_parser("npu-demo", help="Antworten in Schleife, damit die NPU im Task-Manager sichtbar arbeitet")
    demo.add_argument("seconds", nargs="?", type=int, default=30)

    args = parser.parse_args(argv)

    if args.command == "check":
        from .check import run_check

        report = run_check(get_settings(), args.models, args.docs)
        target = args.report or get_settings().log_dir / f"check-{time.strftime('%Y%m%d-%H%M%S')}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"RESULT: {'OK' if report['ok'] else 'FAILED'}   report: {target}")
        return 0 if report["ok"] else 1

    if args.command == "npu-demo":
        from .check import npu_demo

        return npu_demo(get_settings(), args.seconds)

    if args.command == "serve":
        import uvicorn

        uvicorn.run("mira.app:app", factory=True, host=args.host, port=args.port)
        return 0

    mira = _mira()
    if args.command == "ingest":
        files = []
        for path in args.paths:
            files += sorted(p for p in path.rglob("*") if p.suffix.lower() in SUPPORTED) if path.is_dir() else [path]
        failed = 0
        for file in files:
            try:
                print(f"{file}: {mira.ingest_file(file)} Abschnitte")
            except Exception as error:
                failed += 1
                print(f"{file}: FEHLER {error}", file=sys.stderr)
        return 1 if failed else 0

    answer = mira.ask(args.question)
    print(answer.answer)
    for source in answer.sources:
        print(f"  [{source.number}] {source.doc_name} {source.location} (Score {source.score})")
    print(f"  {answer.seconds:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
