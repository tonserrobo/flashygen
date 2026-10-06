"""Tests for card quality gate and type handling (issue #1)."""
from flashygen.flashcard_generator import (
    Flashcard,
    _build_ollama_prompt,
    _parse_raw_cards,
    _quality_gate,
)


def test_prompt_has_worked_example_and_density_scaling():
    prompt = _build_ollama_prompt("content", "Title")
    assert "EXAMPLE" in prompt  # a worked example of a good card
    assert "only as many as the content" in prompt  # density-scaled count, no forced floor
    assert "3 to 6" not in prompt


def test_prompt_directs_table_row_harvesting():
    """8-row decision tables yielded ~1 card — tables need an explicit nudge (issue #23)."""
    prompt = _build_ollama_prompt("content", "Title")
    assert "|" in prompt and "table row" in prompt.lower()


def test_parse_keeps_card_type():
    cards = _parse_raw_cards([{"front": "Q?", "back": "A" * 50, "type": "command"}], "T")
    assert cards[0].card_type == "command"


def test_parse_defaults_unknown_type_to_recall():
    cards = _parse_raw_cards([{"front": "Q?", "back": "A" * 50}], "T")
    assert cards[0].card_type == "recall"


def test_gate_rejects_command_card_without_code():
    card = Flashcard("How do you log?", "Use the logging macro provided by the engine framework.", card_type="command")
    kept, dropped = _quality_gate([card])
    assert kept == [] and dropped == 1


def test_gate_accepts_command_card_with_code_fence():
    card = Flashcard("How do you log?", 'Use:\n```cpp\nUE_LOG(LogTemp, Warning, TEXT("Hi"));\n```', card_type="command")
    kept, dropped = _quality_gate([card])
    assert len(kept) == 1 and dropped == 0


def test_gate_accepts_command_card_citing_code_asset():
    card = Flashcard("How is Stamina replicated?", "Register it in GetLifetimeReplicatedProps: [CODE 2]", card_type="troubleshoot")
    kept, dropped = _quality_gate([card])
    assert len(kept) == 1 and dropped == 0


def test_gate_rejects_near_empty_back():
    kept, dropped = _quality_gate([Flashcard("What is a class?", "A blueprint.", card_type="recall")])
    assert kept == [] and dropped == 1


def test_gate_keeps_substantial_recall_card():
    back = "A vector is defined by its direction (where it points) and magnitude (its length)."
    kept, dropped = _quality_gate([Flashcard("What defines a vector?", back, card_type="recall")])
    assert len(kept) == 1 and dropped == 0


def test_gate_reclassifies_code_answer_as_command():
    """A recall card whose answer is just a code asset is really a syntax card (issue #27)."""
    card = Flashcard("What does this code show?", "[CODE 11]", card_type="recall", code_ref="CODE 11")
    kept, _ = _quality_gate([card], assets=[{"token": "CODE 11", "kind": "code", "language": "cpp", "content": "const int x = 42;"}])
    assert kept[0].card_type == "command"


def test_gate_keeps_prose_recall_card_as_recall():
    card = Flashcard("What is a variable?", "A named memory location whose value can change.", card_type="recall")
    kept, _ = _quality_gate([card])
    assert kept[0].card_type == "recall"


def test_gate_keeps_template_cards_for_different_assets():
    """Fallback/command cards that differ only by their token are not duplicates (issue #36)."""
    a = Flashcard("What does this code do?\n[CODE 1]", "[CODE 1]", card_type="recall", code_ref="CODE 1")
    b = Flashcard("What does this code do?\n[CODE 2]", "[CODE 2]", card_type="recall", code_ref="CODE 2")
    assets = [
        {"token": "CODE 1", "kind": "code", "language": "cpp", "content": "int a;"},
        {"token": "CODE 2", "kind": "code", "language": "cpp", "content": "int b;"},
    ]
    kept, dropped = _quality_gate([a, b], assets=assets)
    assert len(kept) == 2 and dropped == 0


def test_gate_keeps_figure_image_fronts_for_different_figures():
    a = Flashcard("What does this figure show?\n[FIGURE 1]", "First description.", code_ref="FIGURE 1")
    b = Flashcard("What does this figure show?\n[FIGURE 2]", "Second description.", code_ref="FIGURE 2")
    assets = [
        {"token": "FIGURE 1", "kind": "figure", "url": "", "caption": "x"},
        {"token": "FIGURE 2", "kind": "figure", "url": "", "caption": "y"},
    ]
    kept, dropped = _quality_gate([a, b], assets=assets)
    assert len(kept) == 2 and dropped == 0


def test_gate_still_drops_duplicate_plain_recall_fronts():
    a = Flashcard("What is a class?", "A blueprint defining data and behavior for objects.")
    b = Flashcard("What is a class?", "A user-defined type that bundles data with methods.")
    kept, dropped = _quality_gate([a, b])
    assert len(kept) == 1 and dropped == 1


def test_gate_strips_markers_from_command_front():
    card = Flashcard("See [CODE 1] for the syntax", "[CODE 1]", card_type="command", code_ref="CODE 1")
    assets = [{"token": "CODE 1", "kind": "code", "language": "cpp", "content": "int x;"}]
    kept, _ = _quality_gate([card], assets=assets)
    assert kept and "[CODE" not in kept[0].front


def test_gate_drops_command_card_whose_front_is_only_a_marker():
    card = Flashcard("[CODE 1]", "[CODE 1]", card_type="command", code_ref="CODE 1")
    assets = [{"token": "CODE 1", "kind": "code", "language": "cpp", "content": "int x;"}]
    kept, dropped = _quality_gate([card], assets=assets)
    assert kept == [] and dropped == 1


def test_gate_repairs_missing_code_ref_from_cited_token():
    """A command card citing [CODE n] but omitting code_ref must be repairable (issue #36)."""
    card = Flashcard(
        "How do you define a constructor using an initializer list?",
        "Use the syntax: ClassName() : member1(value1), member2(value2) {} [CODE 94]",
        card_type="command",
    )
    kept, _ = _quality_gate([card])
    assert kept[0].code_ref == "CODE 94"


def test_gate_keeps_fence_command_card_without_code_ref():
    """A fence-only command card has no asset token, so no code_ref is required."""
    card = Flashcard("How do you log?", 'Use:\n```cpp\nUE_LOG(LogTemp, Warning, TEXT("Hi"));\n```', card_type="command")
    kept, _ = _quality_gate([card])
    assert kept[0].card_type == "command" and kept[0].code_ref == ""


def test_gate_moves_embedded_explainer_out_of_back():
    """A model that appends 'Explainer:' to the answer must not leave it there (issue #28)."""
    card = Flashcard(
        "What fixed-width types should be used?",
        "Use the fixed-width types from <cstdint>, such as uint32_t and int64_t, to guarantee a size on every platform.\n\nExplainer: Using these types guarantees a specific number of bits regardless of the platform.",
        card_type="recall",
    )
    kept, _ = _quality_gate([card])
    assert kept[0].explainer == "Using these types guarantees a specific number of bits regardless of the platform."
    assert "Explainer:" not in kept[0].back
    assert kept[0].back == "Use the fixed-width types from <cstdint>, such as uint32_t and int64_t, to guarantee a size on every platform."


def test_gate_strips_embedded_explainer_when_field_already_set():
    card = Flashcard(
        "Q?",
        "A sufficiently detailed answer that fully explains the behavior and passes the gate.\n\nExplainer: redundant block",
        explainer="Real explainer.",
        card_type="recall",
    )
    kept, _ = _quality_gate([card])
    assert kept[0].explainer == "Real explainer."
    assert "Explainer:" not in kept[0].back
