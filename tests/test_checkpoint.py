"""Tests for per-section checkpoint resume and zero-card retry (issues #13, #14)."""
import json

from flashygen.flashcard_generator import Flashcard, FlashcardGenerator
from flashygen.manifest import section_hash

SECTION = {"heading": "Setup", "content": "Install the engine from the Epic launcher."}


def _good_card():
    return Flashcard("Q?", "A sufficiently long and substantial answer for the gate.")


def _generator(results):
    """Generator whose per-section generation pops canned results and records calls."""
    gen = FlashcardGenerator(None, provider="ollama")
    calls = []

    def fake(content, title, cards_per_concept=3, assets=None):
        calls.append(content)
        return results.pop(0)

    gen.generate_flashcards = fake
    return gen, calls


def _write_checkpoint(work, cards):
    (work / "section_01.json").write_text(json.dumps({
        "heading": SECTION["heading"],
        "content_hash": section_hash(SECTION["content"]),
        "cards": cards,
    }), encoding="utf-8")


def test_empty_checkpoint_is_regenerated_not_resumed(tmp_path):
    """A 0-card checkpoint must not freeze the section — re-runs retry it (issue #13)."""
    _write_checkpoint(tmp_path, [])
    gen, calls = _generator([[_good_card()]])
    cards = gen.generate_flashcards_from_sections([SECTION], "T", work_dir=str(tmp_path))
    assert len(calls) == 1  # model called despite the (empty) checkpoint
    assert len(cards) == 1


def test_nonempty_checkpoint_resumed_without_model_call(tmp_path):
    _write_checkpoint(tmp_path, [{"front": "Q?", "back": "A" * 50, "type": "recall"}])
    gen, calls = _generator([])
    cards = gen.generate_flashcards_from_sections([SECTION], "T", work_dir=str(tmp_path))
    assert calls == []  # resumed, no model call
    assert len(cards) == 1


def test_resumed_cards_get_current_section_heading(tmp_path):
    """Resume must re-stamp section attribution, or coverage counts the card
    under the checkpoint-era heading (seen live after the issue #18 rename)."""
    _write_checkpoint(tmp_path, [{"front": "Q?", "back": "A" * 50, "type": "recall", "section": ""}])
    gen, _ = _generator([])
    cards = gen.generate_flashcards_from_sections([SECTION], "T", work_dir=str(tmp_path))
    assert cards[0].section == SECTION["heading"]


def test_zero_card_section_retried_once():
    """A section that nets 0 cards gets one more attempt before going uncovered (issue #14)."""
    gen, calls = _generator([[], [_good_card()]])
    cards = gen.generate_flashcards_from_sections([SECTION], "T")
    assert len(calls) == 2
    assert len(cards) == 1


def test_zero_card_section_not_retried_forever():
    gen, calls = _generator([[], []])
    cards = gen.generate_flashcards_from_sections([SECTION], "T")
    assert len(calls) == 2  # exactly one retry, then move on
    assert cards == []
