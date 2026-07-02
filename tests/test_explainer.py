"""Tests for the explainer section on cards (issue #10)."""
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

BACK = "Use ReplicatedUsing and register the property in GetLifetimeReplicatedProps."


def test_parse_keeps_explainer():
    cards = _parse_raw_cards(
        [{"front": "Q?", "back": BACK, "type": "recall", "explainer": "Common multiplayer bug: no warning is emitted."}],
        "T",
    )
    assert cards[0].explainer == "Common multiplayer bug: no warning is emitted."


def test_parse_defaults_explainer_empty():
    cards = _parse_raw_cards([{"front": "Q?", "back": BACK}], "T")
    assert cards[0].explainer == ""


def test_prompt_requests_explainer():
    prompt = _build_ollama_prompt("content", "Title")
    assert '"explainer"' in prompt


def test_gate_blanks_explainer_that_restates_back():
    card = Flashcard("Q?", BACK, [], card_type="recall")
    card.explainer = BACK + " "
    kept, _ = _quality_gate([card])
    assert kept[0].explainer == ""


def test_model_has_conditional_explainer_field():
    model = AnkiExporter().model
    assert [f["name"] for f in model.fields] == ["Question", "Answer", "Explainer"]
    assert "{{#Explainer}}" in model.templates[0]["afmt"]


def test_exported_note_carries_explainer(tmp_path):
    card = Flashcard("Q?", BACK, [], card_type="recall")
    card.explainer = "This is one of UE5's most common multiplayer bugs."
    out = AnkiExporter().create_deck([card], "Exp Test", str(tmp_path / "e.apkg"))
    with zipfile.ZipFile(out) as z, tempfile.TemporaryDirectory() as td:
        z.extract("collection.anki2", td)
        con = sqlite3.connect(Path(td) / "collection.anki2")
        flds = con.execute("SELECT flds FROM notes").fetchone()[0]
        con.close()
    fields = flds.split("\x1f")
    assert len(fields) == 3
    assert "most common multiplayer bugs" in fields[2]
