"""Demo documents for the story video: a machine manual (PDF), a fault code list (Excel) and old tickets (CSV).

The machine "FZ-300" and everything about it is fictional. MIRA reads these files like real customer documents;
every answer in the video comes from them.

usage: python video/demo/make_docs.py samples/fz-300      (needs reportlab and openpyxl)
"""
import csv
import random
import sys
from pathlib import Path

from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
rnd = random.Random(7)

# code, text, cause, remedy (the same list feeds the manual, the Excel list and the tickets)
FAULTS = [
    ("E-101", "Not-Halt betätigt", "Not-Halt-Taster an Bedienpult oder Schutztür gedrückt.", "Ursache klären, Taster entriegeln, Störung am Bedienpult quittieren."),
    ("E-104", "Schutztür offen", "Türschalter S12 meldet offen, Tür nicht verriegelt.", "Tür schließen, Verriegelung prüfen, Schalter S12 auf Verschmutzung prüfen."),
    ("E-112", "Druckluft zu niedrig", "Versorgungsdruck unter 5,5 bar.", "Druckregler am Wartungsgerät prüfen, Leckagen suchen, Filter des Wartungsgeräts tauschen."),
    ("E-120", "Kühlmittelstand niedrig", "Schwimmerschalter B31 im Kühlmittelbehälter.", "Kühlmittel nachfüllen (Konzentrat 6 %), Behälter auf Späne prüfen."),
    ("E-126", "Kühlmittelpumpe Überlast", "Motorschutzschalter Q14 ausgelöst, oft durch Späne im Ansaugsieb.", "Anlage freischalten, Ansaugsieb reinigen, Q14 zurücksetzen."),
    ("E-203", "Werkzeugwechsler Position unklar", "Initiator B42 meldet keine eindeutige Magazinposition.", "Magazin im Einrichtbetrieb auf Referenz fahren, B42 auf Abstand 1,5 mm prüfen."),
    ("E-207", "Werkzeug nicht gespannt", "Spannkraft der Spindel unter Sollwert.", "Druck der Lösehydraulik prüfen, Spannzange reinigen, Tellerfederpaket laut Kapitel 4.6 prüfen."),
    ("E-215", "Werkzeugbruch erkannt", "Werkzeugbruchkontrolle (Laser) hat Abweichung erkannt.", "Werkzeug tauschen, Programmzeile prüfen, Laser-Optik reinigen."),
    ("E-302", "X-Achse Schleppfehler", "Abweichung zwischen Soll- und Istposition zu groß.", "Achse auf Schwergängigkeit prüfen, Führungsbahnen schmieren, Kupplung prüfen."),
    ("E-305", "Y-Achse Endschalter", "Software- oder Hardware-Endschalter angefahren.", "Achse im Einrichtbetrieb freifahren, Nullpunkt prüfen."),
    ("E-311", "Z-Achse Bremse", "Haltebremse öffnet nicht, Spannung an Bremse fehlt.", "Sicherung F22 prüfen, Bremsenansteuerung messen (24 V)."),
    ("E-330", "Zentralschmierung leer", "Füllstand im Schmierstoffbehälter zu niedrig.", "Fett nach Schmierplan nachfüllen (Kapitel 4.3), Leitungen entlüften."),
    ("E-402", "Spindel Drehzahl nicht erreicht", "Umrichter meldet Überlast oder Drehzahlabweichung.", "Werkzeug und Schnittdaten prüfen, Umrichter-Fehlerspeicher auslesen."),
    ("E-417", "Übertemperatur Spindelmotor", "Temperatur am Spindelmotor über 95 °C. Häufigste Ursache: verstopfte Filtermatte am Schaltschranklüfter oder ausgefallener Lüfter M7.",
     "Anlage stillsetzen und gegen Wiedereinschalten sichern. Filtermatte am Schaltschrank links prüfen und tauschen (Kapitel 4.4). Lüfter M7 auf Lauf prüfen. Motor 20 Minuten abkühlen lassen, dann Störung quittieren."),
    ("E-418", "Übertemperatur Spindellager", "Lagertemperatur über 70 °C, Schmierung oder Vorspannung.", "Spindel nicht weiter betreiben, Service verständigen, Laufzeit seit letzter Spindelwartung prüfen."),
    ("E-421", "Spindelkühlung Durchfluss", "Durchflusswächter B55 im Spindelkühlkreis meldet zu wenig Durchfluss.", "Kühlaggregat prüfen, Kühlmittel im Kühlkreis nachfüllen, Schläuche auf Knicke prüfen."),
    ("E-503", "Hydraulikdruck niedrig", "Druck unter 60 bar.", "Ölstand prüfen, Pumpe auf Geräusche prüfen, Filter tauschen."),
    ("E-510", "Hydrauliköl Temperatur", "Öltemperatur über 55 °C.", "Ölkühler reinigen, Lüfter des Ölkühlers prüfen."),
    ("E-601", "Kommunikation SPS gestört", "Profinet-Verbindung zur Peripherie unterbrochen.", "Steckverbinder prüfen, Diagnose im TIA Portal, Switch neu starten."),
    ("E-612", "Batterie Absolutwertgeber", "Pufferbatterie der Geber schwach.", "Batterie bei eingeschalteter Steuerung tauschen, sonst geht die Referenz verloren."),
]

# ---------------------------------------------------------------- manual (PDF, citations by page)
ss = getSampleStyleSheet()
h1, h2, p = ss["Heading1"], ss["Heading2"], ss["BodyText"]
story = [Paragraph("Bedienungs- und Wartungsanleitung", ss["Title"]), Paragraph("Fräszentrum FZ-300 (Demo-Anlage, fiktiv)", h2),
         Spacer(1, 20), Paragraph("Ausgabe 3.2. Diese Anleitung gilt für alle FZ-300 ab Seriennummer 3000. "
                                  "Vor allen Arbeiten an der Anlage Kapitel 1 lesen.", p), PageBreak()]


def chapter(title, paras):
    story.append(Paragraph(title, h1))
    for x in paras:
        story.append(Paragraph(x[1:], h2) if x.startswith("#") else Paragraph(x, p))
        story.append(Spacer(1, 6))
    story.append(PageBreak())


chapter("1 Sicherheit", [
    "Arbeiten an der Anlage nur durch unterwiesenes Personal. Vor Wartung und Störungsbeseitigung die Anlage am Hauptschalter "
    "Q1 ausschalten und mit Vorhängeschloss gegen Wiedereinschalten sichern (Lockout/Tagout).",
    "Nach dem Abschalten können Spindel und Antriebe noch heiß sein. Spindelmotor erst nach 20 Minuten berühren.",
    "Die Schutztür darf nur im Einrichtbetrieb mit Zustimmtaster geöffnet werden.",
])
chapter("2 Aufbau der Anlage", [
    "Das FZ-300 ist ein 3-Achs-Vertikalfräszentrum mit Werkzeugmagazin für 24 Werkzeuge, Spindel 12.000 1/min, 18 kW.",
    "#2.1 Schaltschrank",
    "Der Schaltschrank steht links von der Anlage. Er wird über zwei Lüfter mit Filtermatten gekühlt: Lüfter M6 rechts für die "
    "Umrichter, Lüfter M7 links für Spindelumrichter und Spindelmotor-Fremdlüfter. Die Filtermatten sitzen hinter den Lüftungsgittern.",
    "#2.2 Spindel",
    "Die Spindel hat eine Fettschmierung auf Lebensdauer und einen eigenen Kühlkreis mit Durchflusswächter B55.",
])
chapter("3 Bedienung", [
    "Die Anlage wird über das Bedienpult mit HMI bedient. Störungen erscheinen mit Code und Klartext in der Meldezeile.",
    "Störungen werden mit der Taste RESET quittiert, nachdem die Ursache beseitigt ist. Eine Störung, die sofort wiederkommt, "
    "nicht mehrfach quittieren, sondern die Instandhaltung verständigen.",
])
chapter("4 Wartung", [
    "#4.1 Wartungsplan",
    "Täglich: Späne entfernen, Kühlmittelstand prüfen. Wöchentlich: Filtermatten Schaltschrank prüfen. Monatlich: Zentralschmierung "
    "auffüllen, Druckluftfilter prüfen. Jährlich: Hydrauliköl wechseln, Spindel-Service durch Hersteller.",
    "#4.3 Zentralschmierung",
    "Fett der Klasse NLGI 00 verwenden. Behälter bis zur Markierung MAX füllen, danach einen Schmierzyklus im Menü Service starten.",
    "#4.4 Filtermatten am Schaltschrank tauschen",
    "1. Anlage am Hauptschalter Q1 ausschalten und sichern. 2. Lüftungsgitter links (Lüfter M7) bzw. rechts (Lüfter M6) abklipsen. "
    "3. Filtermatte entnehmen. Eine graue oder verfilzte Matte immer tauschen, nicht ausklopfen. 4. Neue Matte Typ FM-120 einsetzen, "
    "Gitter aufsetzen. 5. Nach dem Einschalten prüfen, ob der Lüfter läuft (Luftstrom am Gitter fühlbar).",
    "Eine verstopfte Filtermatte ist die häufigste Ursache für Übertemperatur im Schaltschrank und am Spindelmotor.",
    "#4.6 Werkzeugspannung prüfen",
    "Spannkraft mit Messgerät SK-40 prüfen. Sollwert 18 kN plus/minus 1 kN. Bei Abweichung Tellerfederpaket durch den Service tauschen.",
])
chapter("5 Störungen und Abhilfe", ["Die folgenden Seiten listen alle Störcodes mit Ursache und Abhilfe. "
                                    "Bei Arbeiten an der Anlage immer Kapitel 1 beachten."])
for code, text, cause, remedy in FAULTS:
    story += [Paragraph(f"{code} {text}", h2), Paragraph(f"<b>Ursache:</b> {cause}", p), Spacer(1, 4),
              Paragraph(f"<b>Abhilfe:</b> {remedy}", p), Spacer(1, 14)]
    if code in ("E-126", "E-305", "E-418", "E-601"):
        story.append(PageBreak())
story.append(PageBreak())
chapter("6 Technische Daten", ["Verfahrwege X/Y/Z: 800/500/500 mm. Spindel: 12.000 1/min, 18 kW, SK40. Anschluss: 400 V, 50 Hz, 45 A. "
                               "Druckluft: 6 bar. Gewicht: 6,2 t."])
SimpleDocTemplate(str(out / "Handbuch_FZ-300.pdf"), pagesize=A4, title="Handbuch FZ-300").build(story)

# ---------------------------------------------------------------- fault code list (Excel, citations by row)
wb = Workbook()
ws = wb.active
ws.title = "Störcodes"
ws.append(["Code", "Meldung", "Ursache", "Abhilfe"])
for row in FAULTS:
    ws.append(list(row))
wb.save(out / "Stoercodes_Linie3.xlsx")

# ---------------------------------------------------------------- old tickets (CSV)
NOTES = {
    "E-417": [("Filtermatte links komplett zu, getauscht. Danach läuft die Spindel normal.", "Filtermatte M7 getauscht"),
              ("Lüfter M7 stand, Lager fest. Lüfter getauscht.", "Lüfter M7 ersetzt"),
              ("Filtermatte grau, getauscht. Wöchentliche Prüfung im Schichtbuch ergänzt.", "Filtermatte M7 getauscht")],
    "E-126": [("Ansaugsieb voller Späne, gereinigt, Q14 zurückgesetzt.", "Sieb gereinigt")],
    "E-203": [("B42 verstellt, auf 1,5 mm eingestellt.", "Initiator justiert")],
    "E-330": [("Behälter leer, Fett nachgefüllt, Leitung entlüftet.", "Nachgefüllt")],
    "E-112": [("Leckage am Schnellkupplung Wartungsgerät, Kupplung getauscht.", "Kupplung ersetzt")],
}
with open(out / "Tickets_2025.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["Ticket", "Datum", "Anlage", "Störcode", "Beschreibung", "Maßnahme", "Techniker"])
    for n in range(64):
        code = rnd.choice([*NOTES] * 2 + [c for c, *_ in FAULTS])
        desc, act = rnd.choice(NOTES.get(code, [("Störung behoben nach Anleitung.", "Nach Handbuch")]))
        w.writerow([f"#{2200 + n * 3}", f"2025-{1 + n % 12:02d}-{1 + (n * 7) % 28:02d}", f"Anlage {rnd.choice([1, 2, 3, 3, 4])}",
                    code, desc, act, rnd.choice(["MK", "TS", "AB", "JR"])])
print("demo docs ok", out)
