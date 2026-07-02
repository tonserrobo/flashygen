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
