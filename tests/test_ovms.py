import json

import httpx

from mira.config import Settings
from mira.ovms import OvmsClient


def test_requests_match_the_ovms_openai_api():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append((request.url.path, body))
        if request.url.path == "/v3/embeddings":
            return httpx.Response(200, json={"data": [{"index": 1, "embedding": [0.0, 1.0]}, {"index": 0, "embedding": [1.0, 0.0]}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": "<think>hm</think>\nFilter tauschen [1]"}}]})

    client = OvmsClient(Settings(ovms_url="http://npu:8000/v3"), transport=httpx.MockTransport(handler))

    assert client.embed(["a", "b"]) == [[1.0, 0.0], [0.0, 1.0]]
    assert client.chat([{"role": "user", "content": "?"}], 50) == "Filter tauschen [1]"

    (embed_path, embed_body), (chat_path, chat_body) = seen
    assert embed_path == "/v3/embeddings" and embed_body["model"] == "OpenVINO/Qwen3-Embedding-0.6B-int8-ov"
    assert chat_path == "/v3/chat/completions"
    assert chat_body["chat_template_kwargs"] == {"enable_thinking": False}
