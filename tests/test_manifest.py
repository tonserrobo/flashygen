"""Tests for the card manifest, coverage, deterministic IDs, and checkpoints (issues #5, #9)."""
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from flashygen.anki_exporter import AnkiExporter
from flashygen.flashcard_generator import Flashcard, FlashcardGenerator
from flashygen.manifest import (
    build_manifest,
    card_from_dict,
    coverage,
    diff_sections,
    section_hash,
)

SECTIONS = [
    {"heading": "Live Coding", "content": "Live Coding injects compiled changes."},
    {"heading": "Build Errors", "content": "Delete Binaries/ and Intermediate/."},
]


def _cards():
    card = Flashcard("What is Live Coding?", "A Patch+Continue system that injects compiled changes.", ["t"])
    card.section = "Live Coding"
    return [card]


def test_build_manifest_maps_cards_to_sections_and_flags_uncited_assets():
    assets = [{"token": "CODE 1", "kind": "code", "language": "cpp", "content": "int x;"}]
    m = build_manifest("page123", "UE5", SECTIONS, _cards(), assets)
    assert m["page_id"] == "page123"
    by_heading = {s["heading"]: s for s in m["sections"]}
    assert len(by_heading["Live Coding"]["cards"]) == 1
    assert by_heading["Build Errors"]["cards"] == []
    assert m["uncited_assets"] == ["CODE 1"]  # no card cites it


def test_coverage_lists_uncovered_sections():
    m = build_manifest("p", "T", SECTIONS, _cards(), [])
    cov = coverage(m)
    assert cov["covered"] == 1 and cov["total"] == 2
    assert cov["uncovered"] == ["Build Errors"]


def test_diff_detects_new_changed_and_uncovered():
    m = build_manifest("p", "T", SECTIONS, _cards(), [])
    current = [
        {"heading": "Live Coding", "content": "Live Coding injects compiled changes. NEW SENTENCE."},
        {"heading": "Build Errors", "content": "Delete Binaries/ and Intermediate/."},
        {"heading": "Pragmas", "content": "Brand new section."},
    ]
    d = diff_sections(m, current)
    assert d["new"] == ["Pragmas"]
    assert d["changed"] == ["Live Coding"]
    assert d["uncovered"] == ["Build Errors"]


def test_card_dict_roundtrip():
    card = _cards()[0]
    clone = card_from_dict(build_manifest("p", "T", SECTIONS, [card], [])["sections"][0]["cards"][0])
    assert (clone.front, clone.back, clone.section, clone.card_type) == (card.front, card.back, "Live Coding", "recall")


def test_deck_and_note_ids_deterministic_across_exports(tmp_path):
    def export(name):
        out = AnkiExporter().create_deck(_cards(), "Det Test", str(tmp_path / name), page_id="page123")
        with zipfile.ZipFile(out) as z, tempfile.TemporaryDirectory() as td:
            z.extract("collection.anki2", td)
            con = sqlite3.connect(Path(td) / "collection.anki2")
            guids = sorted(r[0] for r in con.execute("SELECT guid FROM notes").fetchall())
            decks = con.execute("SELECT decks FROM col").fetchone()[0]
            con.close()
        return guids, decks

    guids1, decks1 = export("a.apkg")
    guids2, decks2 = export("b.apkg")
    assert guids1 == guids2
    assert decks1 == decks2  # same deck id json both times


def test_checkpoint_resume_skips_generated_sections(tmp_path, monkeypatch):
    calls = []

    def fake_generate(self, content, title, cards_per_concept=3, assets=None):
        calls.append(title)
        card = Flashcard("Q?", "An answer long enough to survive any future gating logic.", [])
        return [card]

    monkeypatch.setattr(FlashcardGenerator, "generate_flashcards", fake_generate)
    gen = FlashcardGenerator(None, provider="ollama")

    first = gen.generate_flashcards_from_sections(SECTIONS, "T", work_dir=tmp_path)
    assert len(calls) == 2 and len(first) == 2
    assert len(list(tmp_path.glob("section_*.json"))) == 2

    second = gen.generate_flashcards_from_sections(SECTIONS, "T", work_dir=tmp_path)
    assert len(calls) == 2  # resumed from checkpoints, no new LLM calls
    assert len(second) == 2 and second[0].front == "Q?"


def test_checkpoint_regenerates_when_section_content_changes(tmp_path, monkeypatch):
    calls = []

    def fake_generate(self, content, title, cards_per_concept=3, assets=None):
        calls.append(title)
        return [Flashcard("Q?", "An answer long enough to survive any future gating logic.", [])]

    monkeypatch.setattr(FlashcardGenerator, "generate_flashcards", fake_generate)
    gen = FlashcardGenerator(None, provider="ollama")
    gen.generate_flashcards_from_sections(SECTIONS, "T", work_dir=tmp_path)

    changed = [dict(SECTIONS[0], content="Completely different now."), SECTIONS[1]]
    calls.clear()
    gen.generate_flashcards_from_sections(changed, "T", work_dir=tmp_path)
    assert len(calls) == 1  # only the changed section regenerated
