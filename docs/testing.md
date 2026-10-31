# Tests

| Suite | Befehl | Was sie prüft |
| --- | --- | --- |
| Unit | `pytest` (Standard, ohne `hardware`) | Parser (PDF, Word, Excel, CSV), Chunking, Suche und Schwelle, „Weiß ich nicht“ ohne LLM-Aufruf, nur zitierte Quellen, API (Upload, Frage, Feedback, Löschen, Modellserver nicht erreichbar), die NPU-Prüfung selbst gegen einen simulierten OVMS |
| Hardware / NPU | `pytest -m hardware tests/hardware` | echter OVMS: beide Modelle `AVAILABLE`, beide laut Graph für die `NPU` kompiliert, Demo-Dokumente auf der NPU eingelesen, E-417 und E-126 mit Quellen beantwortet, die Frage nach dem Anzugsmoment mit „Weiß ich nicht“. Braucht `MIRA_MODELS` (Modellordner) und einen laufenden Modellserver |
| Installation | `verify.cmd` im Installationsordner | Unit-Tests im eingebetteten Python, Start, NPU-Prüfung (`mira check`), Web-UI |
| Sichtbar | `npu-demo.cmd` | 30 s Antworten auf der NPU, Task-Manager zeigt die NPU-Last |

`mira check` geht auch im Repo, bei laufendem Modellserver:

```powershell
.\.venv\Scripts\mira check --models .\models
```

Die Prüfung liest die Demo-Dokumente in einen eigenen Speicher im RAM, der Index der Web-UI bleibt unberührt.

Ergebnisse auf AURORA-HP: noch offen (erster Lauf auf der echten NPU steht aus).
