"""Client for OpenVINO Model Server (OpenAI-compatible /v3 API)."""

from __future__ import annotations

import re

import httpx

from .config import Settings

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


class OvmsClient:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self._http = httpx.Client(
            base_url=settings.ovms_url.rstrip("/"),
            timeout=settings.request_timeout,
            transport=transport,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._http.post("/embeddings", json={"model": self.settings.embed_model, "input": texts})
        response.raise_for_status()
        data = sorted(response.json()["data"], key=lambda item: item["index"])
        return [item["embedding"] for item in data]

    def chat(self, messages: list[dict], max_tokens: int) -> str:
        response = self._http.post(
            "/chat/completions",
            json={
                "model": self.settings.llm_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.1,
                "stream": False,
                # Qwen3: answer directly, no reasoning block
                "chat_template_kwargs": {"enable_thinking": False},
            },
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"] or ""
        return _THINK.sub("", content).strip()

    def health(self) -> dict:
        """Model states as reported by OVMS (/v1/config)."""
        base = str(self._http.base_url).rstrip("/")
        root = base[: -len("/v3")] if base.endswith("/v3") else base
        response = self._http.get(f"{root}/v1/config")
        response.raise_for_status()
        return response.json()
