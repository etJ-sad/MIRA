import json

import httpx

from mira.check import model_devices, run_check
from mira.config import Settings

from conftest import FakeModels

LLM, EMB = "llm", "emb"


def fake_ovms(states="AVAILABLE"):
    """OVMS stand-in: /v1/config, embeddings and a streamed chat that answers from the question."""
    fake = FakeModels()

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/config":
            return httpx.Response(200, json={m: {"model_version_status": [{"version": "1", "state": states}]} for m in (LLM, EMB)})
        body = json.loads(request.content)
        if request.url.path == "/v3/embeddings":
            return httpx.Response(200, json={"data": [{"index": i, "embedding": v} for i, v in enumerate(fake.embed(body["input"]))]})
        question = body["messages"][-1]["content"].rsplit("Frage:", 1)[-1]
        reply = "Filtermatte tauschen [1]." if "E-417" in question else "Ansaugsieb reinigen [1]." if "E-126" in question else "Weiß ich nicht."
        events = [{"choices": [{"delta": {"content": w + " "}}]} for w in reply.split()] + [{"choices": [], "usage": {"completion_tokens": 3}}]
        sse = "".join(f"data: {json.dumps(e)}\n\n" for e in events) + "data: [DONE]\n\n"
        return httpx.Response(200, text=sse, headers={"content-type": "text/event-stream"})

    return httpx.MockTransport(handle)


def docs(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    (d / "codes.csv").write_text(
        "Code;Text;Abhilfe\n"
        "E-417;Übertemperatur Spindelmotor;Filtermatte am Schaltschrank tauschen, Lüfter M7 prüfen\n"
        "E-126;Kühlmittelpumpe Überlast;Ansaugsieb reinigen, Q14 zurücksetzen\n", encoding="utf-8")
    return d


def settings(tmp_path):
    return Settings(ovms_url="http://ovms/v3", llm_model=LLM, embed_model=EMB, data_dir=tmp_path / "data", min_score=0.2)


def test_check_passes_with_answers_and_dont_know(tmp_path):
    lines = []
    report = run_check(settings(tmp_path), None, docs(tmp_path), lines.append, fake_ovms())
    assert report["ok"], lines
    asked = [s for s in report["steps"] if s["step"].startswith('"')]
    assert [s["grounded"] for s in asked] == [True, True, False]
    assert asked[0]["sources"] == ["codes.csv Zeile 2"] and asked[0]["tokens"] == 3


def test_check_fails_when_a_model_is_not_loaded(tmp_path):
    report = run_check(settings(tmp_path), None, docs(tmp_path), lambda _: None, fake_ovms("LOADING"))
    assert not report["ok"]
    assert [s["ok"] for s in report["steps"] if s["step"] in ("LLM model", "embedding model")][:2] == [False, False]


def test_check_reports_unreachable_server(tmp_path):
    down = httpx.MockTransport(lambda r: (_ for _ in ()).throw(httpx.ConnectError("refused")))
    report = run_check(settings(tmp_path), None, docs(tmp_path), lambda _: None, down)
    assert not report["ok"] and report["steps"][0]["step"] == "model server"


def test_model_devices_reads_the_graph(tmp_path):
    graph = tmp_path / "OpenVINO" / "Qwen3-8B-int4-cw-ov" / "graph.pbtxt"
    graph.parent.mkdir(parents=True)
    graph.write_text('node { options { device: "NPU" } }')
    assert model_devices(tmp_path) == {"OpenVINO/Qwen3-8B-int4-cw-ov": "NPU"}
