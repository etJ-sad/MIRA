"""Vector index, embedded Qdrant on local disk (no extra server needed)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from qdrant_client import QdrantClient, models


@dataclass
class Hit:
    score: float
    text: str
    doc_id: str
    doc_name: str
    location: str


class VectorStore:
    def __init__(self, client: QdrantClient, collection: str):
        self.client = client
        self.collection = collection

    @classmethod
    def open(cls, path: str | None, collection: str) -> "VectorStore":
        client = QdrantClient(location=":memory:") if path is None else QdrantClient(path=path)
        return cls(client, collection)

    def _ensure(self, dim: int) -> None:
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                self.collection,
                vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
            )

    def _doc_filter(self, doc_id: str) -> models.Filter:
        return models.Filter(must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))])

    def replace_document(self, doc_id: str, doc_name: str, chunks: list[tuple[str, str]], vectors: list[list[float]]) -> None:
        """Store chunks of one document; an earlier version of the same document is removed first."""
        if not vectors:
            return
        self._ensure(len(vectors[0]))
        self.delete_document(doc_id)
        points = [
            models.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}/{i}")),
                vector=vector,
                payload={"doc_id": doc_id, "doc_name": doc_name, "location": location, "text": text},
            )
            for i, ((text, location), vector) in enumerate(zip(chunks, vectors))
        ]
        self.client.upsert(self.collection, points=points)

    def delete_document(self, doc_id: str) -> None:
        if self.client.collection_exists(self.collection):
            self.client.delete(self.collection, points_selector=models.FilterSelector(filter=self._doc_filter(doc_id)))

    def search(self, vector: list[float], limit: int) -> list[Hit]:
        if not self.client.collection_exists(self.collection):
            return []
        result = self.client.query_points(self.collection, query=vector, limit=limit, with_payload=True)
        return [
            Hit(
                score=point.score,
                text=point.payload["text"],
                doc_id=point.payload["doc_id"],
                doc_name=point.payload["doc_name"],
                location=point.payload["location"],
            )
            for point in result.points
        ]

    def documents(self) -> list[dict]:
        """Distinct documents with their chunk counts."""
        if not self.client.collection_exists(self.collection):
            return []
        counts: dict[str, dict] = {}
        offset = None
        while True:
            points, offset = self.client.scroll(
                self.collection, limit=512, offset=offset, with_payload=["doc_id", "doc_name"], with_vectors=False
            )
            for point in points:
                entry = counts.setdefault(point.payload["doc_id"], {"doc_id": point.payload["doc_id"], "name": point.payload["doc_name"], "chunks": 0})
                entry["chunks"] += 1
            if offset is None:
                break
        return sorted(counts.values(), key=lambda d: d["name"].lower())
