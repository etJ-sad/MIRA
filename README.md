# MIRA

**Maintenance Intelligence & Repair Assistant**: ein lokaler Wartungs-Assistent für die Industrie.
MIRA beantwortet Fragen zu Störungen und Wartung aus Handbüchern, Störmeldelisten und Tickets,
immer mit Quellenangabe. LLM und Embeddings laufen auf der **NPU** (Intel Core Ultra) über den
[OpenVINO Model Server](https://github.com/openvinotoolkit/model_server). Keine Cloud, keine GPU.

```
Dokumente ──► Ingest (PDF, Word, Excel, CSV) ──► Embeddings (NPU) ──► Vektor-Index (lokal)
                                                                            │
Frage ──► Web-UI ──► API ──► Suche ◄────────────────────────────────────────┘
                              │
                              └──► LLM (NPU) ──► Antwort mit Quellen [1][2]
```

## Was das MVP kann

- PDF (pro Seite), Word (pro Überschrift und Tabelle), Excel und CSV (pro Zeile) einlesen
- Fragen auf Deutsch oder Englisch, Antwort nur aus den Dokumenten, mit Dokument und Seite/Zeile
- „Weiß ich nicht“, wenn nichts Passendes gefunden wird (das LLM wird dann gar nicht gefragt)
- Daumen hoch/runter als Feedback, alle Fragen und Feedback als JSONL unter `data/logs/`
- Web-UI im Browser (Tablet, Industrie-PC, HMI)

## Modelle (Standard)

| Aufgabe | Modell | Gerät |
| --- | --- | --- |
| LLM | `OpenVINO/Qwen3-8B-int4-cw-ov` | NPU |
| Embeddings | `OpenVINO/Qwen3-Embedding-0.6B-int8-ov` | NPU |

Beide sind von Intel für die NPU vorbereitet. Ein kleineres LLM aus der Sammlung
[LLMs optimized for NPU](https://huggingface.co/collections/OpenVINO/llms-optimized-for-npu)
lässt sich über `-LlmModel` bzw. `MIRA_LLM_MODEL` setzen.

## Installation unter Windows 11 (Intel Core Ultra)

1. Aktuellen Intel NPU-Treiber installieren.
2. OVMS-Paket für Windows von den [Releases](https://github.com/openvinotoolkit/model_server/releases)
   laden und hier als `ovms\` entpacken. Prüfen: `.\ovms\ovms.exe --version`.
   (Bei älteren Paketen vorher `.\ovms\setupvars.ps1` ausführen.)
3. Modelle laden und eintragen (einmalig, einige GB):
   ```powershell
   .\scripts\setup-npu.ps1
   ```
4. Modellserver starten (eigenes Fenster):
   ```powershell
   .\scripts\start-ovms.ps1
   ```
   Bereit, wenn `curl.exe http://localhost:8000/v1/config` für beide Modelle `AVAILABLE` meldet.
5. MIRA installieren und starten (Python 3.10 oder neuer):
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -e .
   mira serve
   ```
6. Browser öffnen: <http://localhost:8080>. Dokumente rechts hochladen, dann fragen.

## Installation unter Linux (Docker)

```bash
./scripts/setup-npu.sh                     # Modelle laden (einmalig)
RENDER_GID=$(stat -c "%g" /dev/dri/render* | head -n 1) docker compose up -d
```

Die NPU wird über `/dev/accel` in den Container gereicht. MIRA läuft danach auf Port 8080.

## Kommandozeile

```bash
mira ingest ./handbuecher ./stoercodes.xlsx   # Dateien oder Ordner einlesen
mira ask "Anlage 3 zeigt E-417, was tun?"
mira serve --port 8080
```

Der Vektor-Index liegt als Datei unter `data/index` und kann immer nur von einem Prozess geöffnet
werden. `mira ingest` daher bei gestopptem Server ausführen, oder Dateien über die Web-UI hochladen.

## Einstellungen

Alle über Umgebungsvariablen:

| Variable | Standard | Bedeutung |
| --- | --- | --- |
| `MIRA_OVMS_URL` | `http://localhost:8000/v3` | OpenAI-kompatibler Endpunkt von OVMS |
| `MIRA_LLM_MODEL` | `OpenVINO/Qwen3-8B-int4-cw-ov` | Name des LLM in OVMS |
| `MIRA_EMBED_MODEL` | `OpenVINO/Qwen3-Embedding-0.6B-int8-ov` | Name des Embedding-Modells |
| `MIRA_DATA_DIR` | `data` | Dokumente, Index, Logs |
| `MIRA_TOP_K` | `5` | Anzahl Fundstellen pro Frage |
| `MIRA_MIN_SCORE` | `0.35` | Unter diesem Ähnlichkeitswert: „Weiß ich nicht“ |
| `MIRA_CHUNK_SIZE` | `1200` | Abschnittslänge in Zeichen |

`MIN_SCORE` und `CHUNK_SIZE` sollten mit den 20 Testfragen des Pilotkunden eingestellt werden.

## Entwicklung

```bash
pip install -e ".[dev]"
pytest
```

Die Tests laufen ohne NPU und ohne Modellserver (Modelle werden simuliert).

## API

| Methode | Pfad | Zweck |
| --- | --- | --- |
| `POST` | `/api/ask` | `{"question": "..."}` → Antwort, Quellen, Dauer |
| `GET` | `/api/documents` | Eingelesene Dokumente |
| `POST` | `/api/documents` | Datei hochladen (multipart, Feld `file`) |
| `DELETE` | `/api/documents/{doc_id}` | Dokument entfernen |
| `POST` | `/api/feedback` | `{"answer_id": "...", "helpful": true}` |
| `GET` | `/api/health` | Status von MIRA und OVMS |
