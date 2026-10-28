"""Ingest documents and answer questions from them, with sources."""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from .chunking import split_text
from .config import Settings
from .parsers import parse_file
from .store import Hit, VectorStore

DONT_KNOW = "Weiß ich nicht. Dazu habe ich in den eingelesenen Dokumenten nichts Passendes gefunden."

SYSTEM_PROMPT = """Du bist MIRA, ein Assistent für Instandhaltung in einem Industriebetrieb.
Regeln:
- Antworte nur mit Informationen aus den nummerierten Quellen. Nutze kein eigenes Wissen.
- Belege jede Aussage mit der Quellennummer in eckigen Klammern, z. B. [1] oder [2][3].
- Wenn die Quellen die Frage nicht beantworten, antworte genau: "Weiß ich nicht." und nichts weiter.
- Gib Schritte als nummerierte Liste an. Sei kurz und konkret.
- Bei Arbeiten an der Anlage weise auf Freischalten und Sicherheitsvorschriften hin, wenn die Quellen das nennen.
- Antworte in der Sprache der Frage."""

# Qwen3-Embedding works best when queries (not documents) carry an instruction
QUERY_PREFIX = "Instruct: Finde Abschnitte aus Handbüchern, Störmeldelisten und Tickets, die diese Wartungsfrage beantworten\nQuery: "

EMBED_BATCH = 16


class ModelClient(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def chat(self, messages: list[dict], max_tokens: int) -> str: ...


@dataclass
class Source:
    number: int
    doc_name: str
    location: str
    score: float
    excerpt: str


@dataclass
class Answer:
    answer: str
    sources: list[Source]
    grounded: bool
    seconds: float


def document_id(path: Path) -> str:
    return hashlib.sha256(path.name.lower().encode("utf-8")).hexdigest()[:16]


class Mira:
    def __init__(self, settings: Settings, models: ModelClient, store: VectorStore):
        self.settings = settings
        self.models = models
        self.store = store

    def _embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH):
            vectors += self.models.embed(texts[start : start + EMBED_BATCH])
        return vectors

    def ingest_file(self, path: Path) -> int:
        """Index one file. Re-ingesting a file with the same name replaces it. Returns the chunk count."""
        chunks: list[tuple[str, str]] = []
        for section in parse_file(path):
            for piece in split_text(section.text, self.settings.chunk_size, self.settings.chunk_overlap):
                chunks.append((piece, section.location))
        if not chunks:
            return 0
        # The document name goes into the embedded text so a question naming the machine finds its manual
        vectors = self._embed([f"{path.name}\n{text}" for text, _ in chunks])
        self.store.replace_document(document_id(path), path.name, chunks, vectors)
        return len(chunks)

    def ask(self, question: str) -> Answer:
        started = time.perf_counter()
        question = question.strip()
        [query_vector] = self.models.embed([QUERY_PREFIX + question])
        hits = [h for h in self.store.search(query_vector, self.settings.top_k) if h.score >= self.settings.min_score]
        if not hits:
            return Answer(DONT_KNOW, [], False, time.perf_counter() - started)

        sources = [_source(i, hit) for i, hit in enumerate(hits, start=1)]
        context = "\n\n".join(
            f"[{s.number}] {s.doc_name}{', ' + s.location if s.location else ''}\n{hit.text}"
            for s, hit in zip(sources, hits)
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Quellen:\n{context}\n\nFrage: {question}"},
        ]
        text = self.models.chat(messages, self.settings.max_answer_tokens)
        if not text or text.lower().startswith("weiß ich nicht"):
            return Answer(DONT_KNOW, sources, False, time.perf_counter() - started)

        # Show only the sources the answer actually cites; fall back to all if it cites none
        cited = {int(n) for n in re.findall(r"\[(\d+)\]", text)}
        shown = [s for s in sources if s.number in cited] or sources
        return Answer(text, shown, True, time.perf_counter() - started)


def _source(number: int, hit: Hit) -> Source:
    excerpt = hit.text if len(hit.text) <= 400 else hit.text[:400].rstrip() + " …"
    return Source(number, hit.doc_name, hit.location, round(hit.score, 3), excerpt)


def append_log(log_dir: Path, name: str, record: dict) -> None:
    """Append-only JSONL log (questions, feedback), kept on the local machine."""
    log_dir.mkdir(parents=True, exist_ok=True)
    record = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), **record}
    with (log_dir / f"{name}.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def answer_to_dict(answer: Answer) -> dict:
    return asdict(answer)
