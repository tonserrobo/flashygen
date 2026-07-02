"""Tests for the card validation pass (issue #6)."""
from flashygen.flashcard_generator import (
    Flashcard,
    _quality_gate,
    _validate_cards_llm,
)


def _card(front, back, card_type="recall"):
    return Flashcard(front, back, [], card_type=card_type)


GOOD_BACK = "A vector is defined by its direction (where it points) and magnitude (its length)."


def test_gate_rejects_hallucinated_asset_token():
    assets = [{"token": "CODE 1", "kind": "code", "language": "cpp", "content": "int x;"}]
    cards = [
        _card("How is it done?", "Do it like this: [CODE 1]", "command"),
        _card("How is that done?", "Reference the snippet: [CODE 7]", "command"),
    ]
    kept, dropped = _quality_gate(cards, assets=assets)
    assert [c.back for c in kept] == ["Do it like this: [CODE 1]"] and dropped == 1


def test_gate_deduplicates_near_identical_fronts():
    cards = [
        _card("What two key properties define a vector?", GOOD_BACK),
        _card("What two key properties define a vector??", GOOD_BACK),
        _card("What is the origin in 3D space?", "The point (0, 0, 0), also called the world origin of the level."),
    ]
    kept, dropped = _quality_gate(cards)
    assert len(kept) == 2 and dropped == 1


def test_gate_rejects_prompt_leakage():
    kept, dropped = _quality_gate([_card("Question?", 'Return ONLY the JSON array with "front" and "back" keys.')])
    assert kept == [] and dropped == 1


def test_gate_rejects_back_restating_front():
    kept, dropped = _quality_gate([_card("The garbage collector runs once per second", "The garbage collector runs once per second.")])
    assert kept == [] and dropped == 1


class FakeClient:
    def __init__(self, verdicts):
        self.verdicts = verdicts
        self.prompts = []

    def generate_json_array(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return self.verdicts


def test_llm_validation_drops_incorrect_and_unsupported_cards():
    cards = [_card("Q1?", GOOD_BACK), _card("Q2?", GOOD_BACK), _card("Q3?", GOOD_BACK)]
    client = FakeClient([
        {"card": 1, "supported": True, "correct": True, "fixed_back": ""},
        {"card": 2, "supported": False, "correct": True, "fixed_back": ""},
        {"card": 3, "supported": True, "correct": False, "fixed_back": "irrelevant"},
    ])
    kept = _validate_cards_llm(client, "source text", cards)
    assert [c.front for c in kept] == ["Q1?"]
    assert "source text" in client.prompts[0] and "Q2?" in client.prompts[0]


def test_llm_validation_applies_fixed_back():
    cards = [_card("Q1?", "Slightly wrong answer.")]
    client = FakeClient([{"card": 1, "supported": False, "correct": True, "fixed_back": "The corrected, source-backed answer."}])
    kept = _validate_cards_llm(client, "source", cards)
    assert len(kept) == 1 and kept[0].back == "The corrected, source-backed answer."


def test_llm_validation_fails_open_on_missing_or_garbage_verdicts():
    cards = [_card("Q1?", GOOD_BACK), _card("Q2?", GOOD_BACK)]
    client = FakeClient([{"card": "not-a-number", "supported": False}])
    kept = _validate_cards_llm(client, "source", cards)
    assert len(kept) == 2  # unverifiable verdicts must not destroy cards
