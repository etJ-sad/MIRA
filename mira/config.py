"""Settings, read from environment variables (prefix MIRA_)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str) -> str:
    return os.environ.get(f"MIRA_{name}", default)


@dataclass(frozen=True)
class Settings:
    # OpenVINO Model Server, serves LLM and embeddings on the NPU
    ovms_url: str = field(default_factory=lambda: _env("OVMS_URL", "http://localhost:8000/v3"))
    llm_model: str = field(default_factory=lambda: _env("LLM_MODEL", "OpenVINO/Qwen3-8B-int4-cw-ov"))
    embed_model: str = field(default_factory=lambda: _env("EMBED_MODEL", "OpenVINO/Qwen3-Embedding-0.6B-int8-ov"))
    request_timeout: float = field(default_factory=lambda: float(_env("REQUEST_TIMEOUT", "120")))

    data_dir: Path = field(default_factory=lambda: Path(_env("DATA_DIR", "data")))
    collection: str = field(default_factory=lambda: _env("COLLECTION", "mira"))

    # Chunking in characters. Keep chunks short: the NPU embedding model runs with a small max_length.
    chunk_size: int = field(default_factory=lambda: int(_env("CHUNK_SIZE", "1200")))
    chunk_overlap: int = field(default_factory=lambda: int(_env("CHUNK_OVERLAP", "150")))

    top_k: int = field(default_factory=lambda: int(_env("TOP_K", "5")))
    # Below this cosine score MIRA answers "Weiß ich nicht" without asking the LLM
    min_score: float = field(default_factory=lambda: float(_env("MIN_SCORE", "0.35")))
    max_answer_tokens: int = field(default_factory=lambda: int(_env("MAX_ANSWER_TOKENS", "600")))

    @property
    def docs_dir(self) -> Path:
        return self.data_dir / "docs"

    @property
    def index_dir(self) -> Path:
        return self.data_dir / "index"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"


def get_settings() -> Settings:
    return Settings()
