"""Command line: index a folder, ask a question, start the server."""

from __future__ import annotations

import argparse
import sys
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

    args = parser.parse_args(argv)

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
