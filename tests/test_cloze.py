"""Tests for cloze cards over registered code blocks (issue #11)."""
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from flashygen.anki_exporter import AnkiExporter, _wrap_cloze_blanks
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


def test_cloze_front_falls_back_to_context_when_no_hint():
    """No hint from the model -> front describes the code from the prose (issue #26)."""
    client = _FakeOllama([{"blanks": ["ReplicatedUsing"]}])
    card = _generate_code_cloze(client, ASSETS[0], context="The code demonstrates a replicated stamina property.")
    assert card.front == "The code demonstrates a replicated stamina property."


def test_cloze_front_keeps_generic_fallback_when_context_short():
    client = _FakeOllama([{"blanks": ["ReplicatedUsing"]}])
    card = _generate_code_cloze(client, ASSETS[0], context="Setup:")
    assert card.front == "Complete the code (CODE 1)"


def test_cloze_front_skips_headings_and_table_rows():
    """A table/heading in the context must not become the card front (issue #26)."""
    ctx = "### Scope & Lifetime\n\n| Scope | Visibility |\n|-------|-----------|\n| Block | Local |\n\nThe code shows a persistent local counter."
    from flashygen.flashcard_generator import _front_from_context
    front = _front_from_context(ctx, "CODE 6")
    assert front == "The code shows a persistent local counter."


def test_cloze_backfill_falls_back_to_recall_when_no_blanks(monkeypatch):
    """A code asset the cloze call can't blank still gets a card (issue #29)."""
    from flashygen import flashcard_generator as fg
    gen = FlashcardGenerator(None, provider="ollama", validate=False)
    gen.ollama = _FakeOllama([])
    monkeypatch.setattr(fg, "_generate_code_cloze", lambda client, asset, context="": None)
    content = "Replication setup:\n[CODE 1]\n```cpp\n" + CODE + "\n```"
    cards = gen.generate_flashcards(content, "T", assets=ASSETS)
    fallback = [c for c in cards if c.code_ref == "CODE 1"]
    assert len(fallback) == 1
    # a code-answer card is reclassified to "command" by the quality gate (issue #27)
    assert fallback[0].card_type == "command"
    assert fallback[0].back == "[CODE 1]"
    assert "Replication setup:" in fallback[0].front


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


def test_wrap_cloze_blanks_no_overlap_for_substring_blanks():
    """A later blank that is a substring of an earlier one must wrap the NEXT
    free occurrence, never nest inside the earlier cloze (issue #33)."""
    code = "void counter() {\n    static int count = 0;\n    ++count;\n}"
    out = _wrap_cloze_blanks(code, ["counter", "count"])
    assert "{{c1::counter}}" in out
    assert "{{c2::count}}" in out
    assert "{{c1::{{" not in out  # no nesting
    assert "}}er}}()" not in out


def test_wrap_cloze_blanks_skips_overlapping_ptr_blank():
    code = "int* ptr = &x;\n\n*ptr = 10;\nstd::cout << *ptr;"
    out = _wrap_cloze_blanks(code, ["*ptr = 10", "*ptr"])
    assert "{{c1::*ptr = 10}}" in out
    assert "{{c2::*ptr}};" in out
    assert "{{c1::{{" not in out


def test_wrap_cloze_blanks_skips_brace_blanks():
    """Braces in a blank are dropped — Anki's parser clips at the first '}}' (issue #34)."""
    code = "int b{};\nint arr[5]{};\nint x = 1;"
    out = _wrap_cloze_blanks(code, ["arr[5]{}", "x", "p{}"])
    assert "{{c1::x}}" in out  # the safe blank is wrapped
    assert "{{c" not in out.replace("{{c1::x}}", "")  # brace blanks never wrapped


def test_generation_filters_brace_and_duplicate_blanks():
    """_generate_code_cloze rejects braces/dupes before building the card (issues #33/#34)."""
    from flashygen.flashcard_generator import _generate_code_cloze
    client = _FakeOllama([{"blanks": ["{x}", "ReplicatedUsing", "ReplicatedUsing"], "hint": "h"}])
    card = _generate_code_cloze(client, ASSETS[0])
    assert card.blanks == ["ReplicatedUsing"]


def test_exported_deck_never_contains_nested_cloze(tmp_path):
    """Overlapping blanks export cleanly — no {{c1::{{c2::...}}}} corruption."""
    from flashygen.flashcard_generator import _parse_raw_cards
    code = "void counter() {\n    static int count = 0;\n    ++count;\n}"
    assets = [{"token": "CODE 1", "kind": "code", "language": "cpp", "content": code}]
    cloze = _parse_raw_cards([{"type": "cloze", "code_ref": "CODE 1", "blanks": ["counter", "count"], "hint": "h"}], "T")[0]
    cloze.tags = ["t"]
    out = AnkiExporter().create_deck([cloze], "Cloze Overlap", str(tmp_path / "c.apkg"), assets=assets)
    with zipfile.ZipFile(out) as z, tempfile.TemporaryDirectory() as td:
        z.extract("collection.anki2", td)
        con = sqlite3.connect(Path(td) / "collection.anki2")
        fields = [r[0] for r in con.execute("SELECT flds FROM notes").fetchall()]
        con.close()
    note = next(f for f in fields if "{{c1::" in f)
    assert "{{c1::counter}}" in note and "{{c2::count}}" in note
    assert "{{c1::{{" not in note and "{{c2::{{" not in note


def test_backfill_adds_full_code_command_card(monkeypatch):
    """A cloze asset also gets a formatted code-block command card (issue #31)."""
    from flashygen import flashcard_generator as fg
    gen = FlashcardGenerator(None, provider="ollama", validate=False)
    gen.ollama = _FakeOllama([{
        "front": "Q?", "back": "A sufficiently long answer about stamina replication.", "type": "recall",
    }])
    monkeypatch.setattr(fg, "_generate_code_cloze", lambda client, asset, context="": Flashcard(
        "The code shows a persistent local counter.", f"[{asset['token']}]", [],
        card_type="cloze", code_ref=asset["token"], blanks=["Stamina"],
    ))
    content = ("Replication setup:\nThe macro is required for replication to work correctly.\n"
               "[CODE 1]\n```cpp\n" + CODE + "\n```")
    cards = gen.generate_flashcards(content, "T", assets=ASSETS)
    types = {c.card_type for c in cards}
    assert "cloze" in types and "command" in types
    cmd = next(c for c in cards if c.card_type == "command")
    assert cmd.back == "[CODE 1]" and cmd.code_ref == "CODE 1"
    assert cmd.front.startswith("Recall the")


def test_no_extra_command_card_when_qa_already_cites_asset(monkeypatch):
    """The formatted code-block card is skipped if a Q/A card already cites it (issue #31)."""
    from flashygen import flashcard_generator as fg
    gen = FlashcardGenerator(None, provider="ollama", validate=False)
    gen.ollama = _FakeOllama([{
        "front": "How do you mark it?", "back": "Use [CODE 1]. A long enough answer.", "type": "command",
    }])
    monkeypatch.setattr(fg, "_generate_code_cloze", lambda client, asset, context="": Flashcard(
        "hint", f"[{asset['token']}]", [], card_type="cloze", code_ref=asset["token"], blanks=["Stamina"],
    ))
    content = "Replication setup:\n[CODE 1]\n```cpp\n" + CODE + "\n```"
    cards = gen.generate_flashcards(content, "T", assets=ASSETS)
    commands = [c for c in cards if c.card_type == "command"]
    assert len(commands) == 1  # the main-gen command card, not an extra one
    assert commands[0].back == "Use [CODE 1]. A long enough answer."


def test_troubleshoot_asset_gets_no_command_card(monkeypatch):
    """Code presented as a mistake gets the troubleshoot card, not a code-block card (issue #31)."""
    from flashygen import flashcard_generator as fg
    gen = FlashcardGenerator(None, provider="ollama", validate=False)
    gen.ollama = _FakeOllama([{
        "front": "Q?", "back": "A sufficiently long answer about the naive code.", "type": "recall",
    }])
    monkeypatch.setattr(fg, "_generate_code_cloze", lambda client, asset, context="": Flashcard(
        "What is wrong with this code?\n[CODE 1]", "[CODE 1]\nIt does not compile.",
        [], card_type="troubleshoot",
    ))
    content = "Replication setup:\n[CODE 1]\n```cpp\n" + CODE + "\n```"
    cards = gen.generate_flashcards(content, "T", assets=ASSETS)
    assert any(c.card_type == "troubleshoot" for c in cards)
    assert not any(c.card_type == "command" for c in cards)


def test_code_command_card_phrasing():
    from flashygen.flashcard_generator import _code_command_card
    asset = ASSETS[0]
    cmd = _code_command_card(asset, "The code demonstrates a replicated stamina property.")
    assert cmd.front == "Recall the code that demonstrates a replicated stamina property."
    assert cmd.back == "[CODE 1]" and cmd.card_type == "command"
    cmd2 = _code_command_card(asset, "Setup:")
    assert cmd2.front == "Recall the exact code in CODE 1:"


def test_code_command_card_falls_back_on_unrelated_prose():
    """Random explanatory prose must not become a "Recall the code shown:" front (issue #36)."""
    from flashygen.flashcard_generator import _code_command_card
    asset = ASSETS[0]
    cmd = _code_command_card(
        asset,
        "Not using it correctly can lead to unintended behavior, such as assigning a "
        "parameter value back to itself.",
    )
    assert cmd.front == "Recall the exact code in CODE 1:"


def test_code_command_card_rejects_description_with_token_or_newline():
    from flashygen.flashcard_generator import _code_command_card
    asset = ASSETS[0]
    cmd = _code_command_card(asset, "The code shows how to do it:\n[CODE 2]\nand more")
    assert cmd.front == "Recall the exact code in CODE 1:"


def test_prompt_steers_formatted_code_cards():
    prompt = _build_ollama_prompt("content", "T")
    assert "formatted code block is the answer" in prompt
    assert "cloze" in prompt
