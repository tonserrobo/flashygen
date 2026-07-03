"""Tests for deck-level near-duplicate removal (issue #22).

String similarity cannot separate true duplicates from question-template
overlap ('purpose of #pragma optimize' vs 'purpose of #pragma region'), so
the model judges — but a drop is only honored when word overlap confirms
the pair is actually related.
"""
from flashygen.flashcard_generator import Flashcard, FlashcardGenerator, _dedupe_cards_llm

# the real duplicate pair observed in the UE5_C++_Pragmas deck
DUP_A = Flashcard(
    "What is `#pragma once` and where should it be placed?",
    "It is a directive that tells the compiler to include the file at most once "
    "per translation unit. Placement: at the very top of every header file.",
)
DUP_B = Flashcard(
    "What is the purpose of `#pragma once`?",
    "Include this header at most once per translation unit.",
)
UNRELATED = Flashcard(
    "How do you visually mark an actor's path each frame?",
    "Use DRAW_SPHERE_SingleFrame(GetActorLocation()) inside Tick.",
)


class _FakeOllama:
    def __init__(self, raw):
        self.raw, self.prompts = raw, []

    def generate_json_array(self, prompt, **kwargs):
        if isinstance(self.raw, Exception):
            raise self.raw
        self.prompts.append(prompt)
        return self.raw


def test_llm_flagged_duplicate_dropped():
    client = _FakeOllama([{"keep": 1, "drop": 2}])
    kept = _dedupe_cards_llm(client, [DUP_A, DUP_B, UNRELATED])
    assert kept == [DUP_A, UNRELATED]


def test_drop_of_unrelated_pair_is_ignored():
    """A hallucinated pairing must not delete a card the words don't support."""
    client = _FakeOllama([{"keep": 1, "drop": 3}])  # DUP_A vs UNRELATED: no overlap
    kept = _dedupe_cards_llm(client, [DUP_A, DUP_B, UNRELATED])
    assert kept == [DUP_A, DUP_B, UNRELATED]


def test_invalid_indices_and_llm_failure_leave_cards_untouched():
    cards = [DUP_A, DUP_B]
    assert _dedupe_cards_llm(_FakeOllama([{"keep": 0, "drop": 9}]), cards) == cards
    assert _dedupe_cards_llm(_FakeOllama(RuntimeError("down")), cards) == cards


def test_cloze_cards_are_not_candidates():
    """Clozes are per-asset by construction; only Q/A cards go to the judge."""
    cloze = Flashcard("hint", "[CODE 1]", card_type="cloze", code_ref="CODE 1", blanks=["x"])
    client = _FakeOllama([])
    kept = _dedupe_cards_llm(client, [cloze, DUP_A])
    assert kept == [cloze, DUP_A]
    assert client.prompts == []  # one Q/A card — nothing to compare, no call


def test_sections_pipeline_dedupes_across_sections(monkeypatch):
    """The whole point: per-section _quality_gate can't see other sections."""
    from flashygen import flashcard_generator as fg
    gen = FlashcardGenerator(None, provider="ollama")
    results = [[DUP_A], [DUP_B]]
    gen.generate_flashcards = lambda *a, **k: results.pop(0)
    seen = []

    def fake_dedupe(client, cards):
        seen.extend(cards)
        return [cards[0]]

    monkeypatch.setattr(fg, "_dedupe_cards_llm", fake_dedupe)
    cards = gen.generate_flashcards_from_sections(
        [{"heading": "H1", "content": "x"}, {"heading": "Quick reference", "content": "y"}], "T"
    )
    assert seen == [DUP_A, DUP_B]  # judge saw the cross-section pair
    assert cards == [DUP_A]
