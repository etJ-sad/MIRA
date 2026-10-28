from fastapi.testclient import TestClient

from mira.app import create_app


def client(settings, models, store):
    return TestClient(create_app(settings, models, store))


def test_upload_ask_feedback_delete(settings, models, store):
    http = client(settings, models, store)
    csv = "Code;Beschreibung\nE-417;Übertemperatur Spindel, Lüfter prüfen\n".encode("utf-8")

    uploaded = http.post("/api/documents", files={"file": ("codes.csv", csv, "text/csv")}).json()
    assert uploaded["chunks"] == 1
    assert [d["name"] for d in http.get("/api/documents").json()] == ["codes.csv"]

    answer = http.post("/api/ask", json={"question": "E-417 Übertemperatur Spindel?"}).json()
    assert answer["grounded"] and answer["sources"][0]["doc_name"] == "codes.csv"
    assert (settings.log_dir / "questions.jsonl").exists()

    assert http.post("/api/feedback", json={"answer_id": answer["answer_id"], "helpful": True}).json() == {"ok": True}

    http.delete(f"/api/documents/{uploaded['doc_id']}")
    assert http.get("/api/documents").json() == []
    assert not (settings.docs_dir / "codes.csv").exists()


def test_rejects_unsupported_files(settings, models, store):
    response = client(settings, models, store).post("/api/documents", files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert response.status_code == 400


def test_upload_name_cannot_escape_docs_dir(settings, models, store):
    http = client(settings, models, store)
    response = http.post("/api/documents", files={"file": ("../../evil.txt", b"Wartung Lager", "text/plain")})
    assert response.json()["name"] == "evil.txt"
    assert (settings.docs_dir / "evil.txt").exists()


def test_index_page(settings, models, store):
    assert "MIRA" in client(settings, models, store).get("/").text


def test_model_server_down_is_a_clear_503(settings, store):
    import httpx

    class Down:
        def embed(self, texts):
            raise httpx.ConnectError("Connection refused")

        def chat(self, messages, max_tokens):
            raise AssertionError("not reached")

    response = client(settings, Down(), store).post("/api/ask", json={"question": "E-417?"})
    assert response.status_code == 503
    assert "OVMS" in response.json()["detail"]
