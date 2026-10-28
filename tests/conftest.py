import hashlib
import math
import re

import pytest

from mira.config import Settings
from mira.rag import Mira
from mira.store import VectorStore

DIM = 256


class FakeModels:
    """Stands in for OVMS: hashed bag-of-words embeddings and a scripted LLM."""

    def __init__(self):
        self.reply = "Lüfter prüfen und Filter tauschen [1]."
        self.chats: list[list[dict]] = []

    def embed(self, texts):
        vectors = []
        for text in texts:
            text = text.split("Query: ", 1)[-1]
            vector = [0.0] * DIM
            for word in re.findall(r"\w+", text.lower()):
                vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM] += 1.0
            norm = math.sqrt(sum(v * v for v in vector)) or 1.0
            vectors.append([v / norm for v in vector])
        return vectors

    def chat(self, messages, max_tokens):
        self.chats.append(messages)
        return self.reply


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path / "data", min_score=0.2, chunk_size=300, chunk_overlap=30)


@pytest.fixture
def models():
    return FakeModels()


@pytest.fixture
def store():
    return VectorStore.open(None, "test")


@pytest.fixture
def mira(settings, models, store):
    return Mira(settings, models, store)
