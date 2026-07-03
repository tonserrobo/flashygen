"""Tests for cloze cards over registered code blocks (issue #11)."""
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from flashygen.anki_exporter import AnkiExporter
from flashygen.flashcard_generator import (
    Flashcard,
    FlashcardGenerator,
    _build_ollama_prompt,
    _generate_code_cloze,
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


def test_prompt_no_longer_requests_cloze_cards():
    """Cloze cards are generated deterministically per code asset (issue #17) —
    the main prompt must not distract a small model with a second output schema."""
    prompt = _build_ollama_prompt("content", "T")
    assert '"cloze"' not in prompt and '"blanks"' not in prompt


class _FakeOllama:
    def __init__(self, raw):
        self.raw, self.prompts = raw, []

    def generate_json_array(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return self.raw


def test_dedicated_cloze_call_builds_card_from_asset():
    client = _FakeOllama([{"blanks": ["ReplicatedUsing"], "hint": "Replication macro"}])
    card = _generate_code_cloze(client, ASSETS[0])
    assert card.card_type == "cloze"
    assert card.code_ref == "CODE 1" and card.blanks == ["ReplicatedUsing"]
    assert CODE in client.prompts[0]  # model sees the exact registered code


def test_dedicated_cloze_keeps_only_exact_substrings():
    client = _FakeOllama([{"blanks": ["DOREPLIFETIME", "Stamina"], "hint": "h"}])
    card = _generate_code_cloze(client, ASSETS[0])
    assert card.blanks == ["Stamina"]  # hallucinated blank filtered out


def test_dedicated_cloze_returns_none_when_nothing_valid():
    assert _generate_code_cloze(_FakeOllama([{"blanks": ["DOREPLIFETIME"], "hint": "h"}]), ASSETS[0]) is None
    assert _generate_code_cloze(_FakeOllama([]), ASSETS[0]) is None


def test_generate_backfills_cloze_for_uncited_code(monkeypatch):
    """Every [CODE n] in a section gets a cloze card even when the main call cites none."""
    from flashygen import flashcard_generator as fg
    gen = FlashcardGenerator(None, provider="ollama", validate=False)
    gen.ollama = _FakeOllama([{
        "front": "Q?", "back": "A sufficiently long answer about stamina replication.", "type": "recall",
    }])
    monkeypatch.setattr(fg, "_generate_code_cloze", lambda client, asset, context="": Flashcard(
        "hint", f"[{asset['token']}]", [], card_type="cloze", code_ref=asset["token"], blanks=["Stamina"],
    ))
    content = "Replication setup:\n[CODE 1]\n```cpp\n" + CODE + "\n```"
    cards = gen.generate_flashcards(content, "T", assets=ASSETS)
    assert sum(1 for c in cards if c.card_type == "cloze") == 1


def test_cloze_prompt_receives_surrounding_prose():
    """Blanks should carry the teaching point, which lives in the prose (issue #20)."""
    client = _FakeOllama([{"blanks": ["ReplicatedUsing"], "hint": "h"}])
    _generate_code_cloze(client, ASSETS[0], context="Replication needs a change callback.")
    assert "Replication needs a change callback." in client.prompts[0]


def test_negative_example_flips_to_troubleshoot_card():
    """Code shown as a mistake must not become a memorisation card (issue #20)."""
    client = _FakeOllama([{
        "negative": True,
        "problem": "Moves 1 unit per frame, so speed depends on framerate.",
        "fix": "Scale the offset by DeltaTime.",
    }])
    card = _generate_code_cloze(client, ASSETS[0], context="A naive Tick — do NOT do this:")
    assert card.card_type == "troubleshoot"
    assert "[CODE 1]" in card.front and "[CODE 1]" in card.back
    assert "DeltaTime" in card.back


def test_negative_without_problem_text_yields_no_card():
    card = _generate_code_cloze(_FakeOllama([{"negative": True}]), ASSETS[0], context="Broken:")
    assert card is None


def test_asset_context_is_prose_with_fences_stripped():
    from flashygen.flashcard_generator import _asset_context
    content = "The naive version:\n[CODE 1]\n```cpp\n" + CODE + "\n```\nThis breaks at high FPS."
    ctx = _asset_context(content, "CODE 1")
    assert "The naive version:" in ctx
    assert "This breaks at high FPS." in ctx  # prose AFTER the fence survives
    assert "UPROPERTY" not in ctx  # the code itself does not


def test_backfill_passes_prose_context(monkeypatch):
    from flashygen import flashcard_generator as fg
    gen = FlashcardGenerator(None, provider="ollama", validate=False)
    gen.ollama = _FakeOllama([])
    seen = {}

    def fake(client, asset, context=""):
        seen["ctx"] = context
        return None

    monkeypatch.setattr(fg, "_generate_code_cloze", fake)
    content = "Replication setup:\n[CODE 1]\n```cpp\n" + CODE + "\n```"
    gen.generate_flashcards(content, "T", assets=ASSETS)
    assert "Replication setup:" in seen["ctx"]


def test_backfill_skips_diagram_assets(monkeypatch):
    """Mermaid/diagram blocks are illustrations, not code to memorise (issue #21)."""
    from flashygen import flashcard_generator as fg
    gen = FlashcardGenerator(None, provider="ollama", validate=False)
    gen.ollama = _FakeOllama([{
        "front": "Q?", "back": "A sufficiently long answer about the class hierarchy.", "type": "recall",
    }])
    called = []
    monkeypatch.setattr(fg, "_generate_code_cloze", lambda client, asset: called.append(asset["token"]))
    assets = [{"token": "CODE 1", "kind": "code", "language": "mermaid",
               "content": "graph LR\n  UObject --> AActor"}]
    gen.generate_flashcards("Hierarchy:\n[CODE 1]", "T", assets=assets)
    assert called == []


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
