# Build, Deploy, Test

Der ganze Ablauf von der Quelle bis zur geprüften Installation auf einem Rechner (AURORA-HP oder ein
Industrie-PC mit Intel Core Ultra). PowerShell, keine Admin-Rechte nötig.

Installiert wird nach `%LOCALAPPDATA%\Programs\MIRA`. Dokumente, Index und Logs liegen in
`%LOCALAPPDATA%\MIRA` und bleiben bei einer Neuinstallation erhalten.

## 0. Einmalig auf dem Build-Rechner

1. Aktuellen Intel NPU-Treiber installieren.
2. Modelle für die NPU laden (einige GB): `.\scripts\setup-npu.ps1`. Das Skript lädt OVMS für Windows nach
   `ovms\`, falls es fehlt.
3. Build-Venv: `py -3 -m venv .venv; .\.venv\Scripts\pip install -e ".[dev]"`

## 1. Build

```powershell
cd C:\MIRA
git pull
.\.venv\Scripts\pytest -q                  # Unit-Tests, ohne NPU
.\installer\build_release.ps1
```

Ergebnis: `build\release\MIRA\` und `build\release\MIRA-<version>-win-x64.zip` mit `.sha256`. Der Build prüft,
dass beide Modelle für die NPU kompiliert sind, und lässt die Unit-Tests im eingebetteten Python laufen.

## 2. Deploy

```powershell
Expand-Archive build\release\MIRA-0.1.0-win-x64.zip C:\temp\mira-pkg     # oder: tar -xf ... -C C:\temp\mira-pkg
powershell -ExecutionPolicy Bypass -File C:\temp\mira-pkg\MIRA\Install-MIRA.ps1 -Start
```

`Install-MIRA.ps1` beendet eine laufende Installation, kopiert alles, prüft die Laufzeit und legt im Startmenü
den Ordner **MIRA** an: *MIRA Wartungsassistent*, *MIRA beenden*, *MIRA prüfen*, *MIRA NPU-Demo*.
Mit `-Start` startet MIRA gleich: der Modellserver lädt beide Modelle auf die NPU (beim ersten Mal einige Minuten,
danach aus dem Cache), dann öffnet sich <http://localhost:8080>.

Von Tablet oder HMI aus: `Start-MIRA.ps1 -Network`, dann `http://<PC-Name>:8080` (Windows Firewall fragt einmal).

## 3. Test

```powershell
& "$env:LOCALAPPDATA\Programs\MIRA\verify.cmd"
```

1. Unit-Tests im installierten Python
2. MIRA starten, falls nötig: beide Modelle `AVAILABLE` auf der NPU, Web-UI läuft
3. NPU-Prüfung (`mira check`): Zielgerät jedes Modells laut OVMS-Graph ist `NPU`, Embeddings messen, die
   Demo-Dokumente (`samples\fz-300`) einlesen, zwei Störungsfragen mit Quellen beantworten, eine unbekannte Frage
   mit „Weiß ich nicht“. Zeit bis zum ersten Wort, Tokens pro Sekunde und CPU-Last stehen in der Ausgabe.
   Bericht als JSON in `%LOCALAPPDATA%\MIRA\logs\check-*.json`.
4. Web-UI antwortet auf `/api/health`

Am Ende steht `RESULT: OK` oder `RESULT: FAILED`.

Die NPU bei der Arbeit sehen: Task-Manager → Leistung → NPU öffnen, dann

```powershell
& "$env:LOCALAPPDATA\Programs\MIRA\npu-demo.cmd"        # 30 s, oder npu-demo.cmd 60
```

Die NPU-Kurve steigt, die CPU bleibt unten. Am Ende stehen Antworten, Tokens pro Sekunde und die mittlere CPU-Last.

## Wenn etwas hakt

| Symptom | Ursache, Abhilfe |
| --- | --- |
| `The model server stopped` | NPU-Treiber fehlt oder ist alt. Log: `%LOCALAPPDATA%\MIRA\logs\ovms.log` |
| `Models not AVAILABLE after 20 minutes` | Erste Kompilierung für die NPU hängt. Log prüfen, Rechner neu starten, erneut versuchen |
| Port 8000 oder 8080 belegt | `Start-MIRA.ps1 -OvmsPort 8001 -Port 8081` (dann auch `MIRA_OVMS_URL` setzen für `verify.cmd`) |
| Frage endet mit „Weiß ich nicht“, obwohl es im Dokument steht | `MIRA_MIN_SCORE` senken (Standard 0.35), siehe README |
| MIRA startet nicht | `%LOCALAPPDATA%\MIRA\logs\mira.err.log` |

Entfernen: `Uninstall-MIRA.ps1` (Daten bleiben, außer mit `-RemoveUserData`).
