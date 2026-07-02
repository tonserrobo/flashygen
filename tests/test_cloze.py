"""Tests for cloze cards over registered code blocks (issue #11)."""
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from flashygen.anki_exporter import AnkiExporter
from flashygen.flashcard_generator import (
    Flashcard,
    _build_ollama_prompt,
    _parse_raw_cards,
    _quality_gate,
)

CODE = "UPROPERTY(ReplicatedUsing=OnRep_Stamina)\nfloat Stamina = 100.f;"
ASSETS = [{"token": "CODE 1", "kind": "code", "language": "cpp", "content": CODE}]


def _cloze_raw(blanks, ref="CODE 1"):
    return {"type": "cloze", "code_ref": ref, "blanks": blanks, "hint": "Replication macro"}


def test_parse_builds_cloze_card():
    cards = _parse_raw_cards([_cloze_raw(["ReplicatedUsing"])], "T")
    assert len(cards) == 1
    card = cards[0]
    assert card.card_type == "cloze"
    assert card.code_ref == "CODE 1" and card.blanks == ["ReplicatedUsing"]


def test_gate_keeps_valid_cloze_and_drops_hallucinated_blanks():
    valid = _parse_raw_cards([_cloze_raw(["ReplicatedUsing", "100.f"])], "T")
    bad_blank = _parse_raw_cards([_cloze_raw(["DOREPLIFETIME"])], "T")  # not in CODE 1
    bad_ref = _parse_raw_cards([_cloze_raw(["ReplicatedUsing"], ref="CODE 9")], "T")
    kept, dropped = _quality_gate(valid + bad_blank + bad_ref, assets=ASSETS)
    assert len(kept) == 1 and kept[0].blanks == ["ReplicatedUsing", "100.f"] and dropped == 2


def test_prompt_requests_cloze_cards():
    prompt = _build_ollama_prompt("content", "T")
    assert '"cloze"' in prompt and '"blanks"' in prompt


def test_exporter_emits_cloze_note_alongside_qa(tmp_path):
    qa = Flashcard("Q?", "A real answer with enough substance to pass the gate.", ["t"])
    cloze = _parse_raw_cards([_cloze_raw(["ReplicatedUsing"])], "T")[0]
    cloze.tags = ["t"]
    out = AnkiExporter().create_deck([qa, cloze], "Cloze Test", str(tmp_path / "c.apkg"), assets=ASSETS)
    with zipfile.ZipFile(out) as z, tempfile.TemporaryDirectory() as td:
        z.extract("collection.anki2", td)
        con = sqlite3.connect(Path(td) / "collection.anki2")
        rows = [r[0] for r in con.execute("SELECT flds FROM notes").fetchall()]
        con.close()
    assert len(rows) == 2
    cloze_fields = next(r for r in rows if "{{c1::" in r)
    assert "{{c1::ReplicatedUsing}}" in cloze_fields
    assert "float Stamina = 100.f;" in cloze_fields  # rest of code verbatim
    assert "Replication macro" in cloze_fields  # hint shown as context
