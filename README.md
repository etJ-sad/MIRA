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

## Paket, Installation, Test (wie Lumen und Greenforest)

```powershell
.\installer\build_release.ps1                                  # Offline-Paket: build\release\MIRA-<version>-win-x64.zip
powershell -ExecutionPolicy Bypass -File build\release\MIRA\Install-MIRA.ps1 -Start
& "$env:LOCALAPPDATA\Programs\MIRA\verify.cmd"                 # Tests + NPU-Prüfung, endet mit RESULT: OK
& "$env:LOCALAPPDATA\Programs\MIRA\npu-demo.cmd"               # 30 s NPU-Last, im Task-Manager sichtbar
```

Das Paket enthält eingebettetes Python, MIRA, OVMS, beide NPU-Modelle und die Demo-Dokumente (`samples/fz-300`),
braucht kein Internet und keine Admin-Rechte. Startmenü → MIRA → *MIRA Wartungsassistent* lädt die Modelle auf die
NPU und öffnet die Web-UI. Ablauf und Fehlersuche: [docs/build-deploy-test.md](docs/build-deploy-test.md),
Tests: [docs/testing.md](docs/testing.md), Vorführung: [docs/demo-script.md](docs/demo-script.md).

## Installation unter Windows 11 (Intel Core Ultra), aus dem Repo

1. Aktuellen Intel NPU-Treiber installieren.
2. Modelle laden und eintragen (einmalig, einige GB). Fehlt `ovms\`, lädt das Skript vorher das aktuelle
   OVMS-Paket für Windows von GitHub (`scripts\get-ovms.ps1`, eine bestimmte Version mit `-Version v2025.4`):
   ```powershell
   .\scripts\setup-npu.ps1
   ```
3. Modellserver starten (eigenes Fenster):
   ```powershell
   .\scripts\start-ovms.ps1
   ```
   Bereit, wenn `curl.exe http://localhost:8000/v1/config` für beide Modelle `AVAILABLE` meldet.
4. MIRA installieren und starten (Python 3.10 oder neuer):
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -e .
   mira serve
   ```
5. Browser öffnen: <http://localhost:8080>. Dokumente rechts hochladen, dann fragen. Zum Ausprobieren:
   die Demo-Dokumente in `samples\fz-300` und die Frage „Anlage 3 zeigt E-417, was tun?“.
6. Prüfen (drittes Fenster, Modellserver läuft): `mira check --models .\models` bestätigt, dass beide Modelle
   für die NPU kompiliert sind, liest die Demo-Dokumente, beantwortet zwei Störungsfragen mit Quellen und eine
   unbekannte mit „Weiß ich nicht“. `mira npu-demo` hält die NPU 30 s beschäftigt.

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
mira check --models ./models                  # NPU-Prüfung mit den Demo-Dokumenten
mira npu-demo 30                              # 30 s Antworten, NPU-Last im Task-Manager
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
pytest                                        # ohne NPU und ohne Modellserver (Modelle werden simuliert)
pytest -m hardware tests/hardware             # auf der NPU, Modellserver muss laufen, MIRA_MODELS=Modellordner
```

## API

| Methode | Pfad | Zweck |
| --- | --- | --- |
| `POST` | `/api/ask` | `{"question": "..."}` → Antwort, Quellen, Dauer |
| `GET` | `/api/documents` | Eingelesene Dokumente |
| `POST` | `/api/documents` | Datei hochladen (multipart, Feld `file`) |
| `DELETE` | `/api/documents/{doc_id}` | Dokument entfernen |
| `POST` | `/api/feedback` | `{"answer_id": "...", "helpful": true}` |
| `GET` | `/api/health` | Status von MIRA und OVMS |
