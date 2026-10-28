from mira.rag import DONT_KNOW


def write_codes(tmp_path):
    path = tmp_path / "stoercodes.csv"
    path.write_text(
        "Code;Beschreibung;Massnahme\n"
        "E-417;Übertemperatur Spindel;Lüfter prüfen, Filter tauschen\n"
        "E-102;Druckluft zu niedrig;Kompressor und Leitungen prüfen\n",
        encoding="utf-8",
    )
    return path


def test_answer_cites_the_matching_row(mira, models, tmp_path):
    assert mira.ingest_file(write_codes(tmp_path)) == 2
    answer = mira.ask("Was bedeutet E-417 Übertemperatur?")
    assert answer.grounded
    assert answer.sources[0].doc_name == "stoercodes.csv"
    assert answer.sources[0].location == "Zeile 2"
    assert "E-417" in models.chats[0][1]["content"]


def test_no_match_says_dont_know_without_calling_the_llm(mira, models, tmp_path):
    mira.ingest_file(write_codes(tmp_path))
    answer = mira.ask("Wie backe ich Brot?")
    assert answer.answer == DONT_KNOW
    assert not answer.grounded
    assert models.chats == []


def test_llm_dont_know_is_passed_through(mira, models, tmp_path):
    mira.ingest_file(write_codes(tmp_path))
    models.reply = "Weiß ich nicht."
    answer = mira.ask("E-417 Spindel Ersatzteilnummer?")
    assert answer.answer == DONT_KNOW
    assert not answer.grounded


def test_reingest_replaces_old_version(mira, store, tmp_path):
    path = write_codes(tmp_path)
    mira.ingest_file(path)
    path.write_text("Code;Beschreibung\nE-417;neu\n", encoding="utf-8")
    mira.ingest_file(path)
    assert store.documents() == [{"doc_id": store.documents()[0]["doc_id"], "name": "stoercodes.csv", "chunks": 1}]
