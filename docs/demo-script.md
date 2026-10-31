# 10-Minuten-Demo

Vorbereitung: MIRA installiert, `verify.cmd` einmal mit `RESULT: OK`, MIRA läuft (Startmenü → MIRA
Wartungsassistent), Netzwerk aus. Task-Manager → Leistung → NPU offen.

1. **Die Lage (1 min).** Linie 3 steht mit E-417, 2:47 Uhr nachts. Das Handbuch hat hunderte Seiten, der Experte
   ist im Urlaub. MIRA läuft auf diesem Industrie-PC, ohne Cloud und ohne GPU.
2. **Einlesen (2 min).** Rechts die drei Demo-Dateien aus `samples\fz-300` hochladen: Handbuch FZ-300 (PDF),
   Störcodeliste (Excel), 64 alte Tickets (CSV). Hinweis: die Maschine ist erfunden, die Dateien werden genau wie
   echte Kundendokumente gelesen. Die Embeddings rechnet die NPU, im Task-Manager sichtbar.
3. **Fragen (3 min).** „Anlage 3 zeigt E-417, was tun?“ Antwort mit Schritten und Quellen [1][2], Handbuchseite
   und Störcodeliste. Unter der Antwort stehen Dokument und Seite: genau dort steht es. Dann „Was war die Ursache bei den letzten
   E-417 Tickets?“ (Antwort aus den Tickets).
4. **Ehrlich (1 min).** „Welches Anzugsmoment gilt für die Spindelmutter an Anlage 7?“ → „Weiß ich nicht“. Das LLM
   wird gar nicht gefragt, weil keine passende Stelle gefunden wurde. Eine falsche Antwort kann eine falsche
   Reparatur sein.
5. **Die NPU (2 min).** `npu-demo.cmd` starten: die NPU-Kurve steigt, die CPU bleibt fast leer und damit frei für
   die Maschinensteuerung. Dazu die Zahlen aus `verify.cmd`: Zeit bis zum ersten Wort, Tokens pro Sekunde.
6. **Abschluss (1 min).** Daumen hoch/runter als Feedback, alles bleibt lokal in `%LOCALAPPDATA%\MIRA\logs`.
   Grenzen: Antworten nur so gut wie die Dokumente, das MVP kennt keine Bilder und keine Benutzerrechte.
