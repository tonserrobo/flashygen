"""Tests for deterministic figure coverage (issue #36).

Figures are registered as [FIGURE n] markers but the model rarely cites them,
so each figure with nearby prose or a caption gets its own card and the
exporter swaps the token for the downloaded image.
"""
from flashygen.flashcard_generator import (
    FlashcardGenerator,
    _figure_card,
)


class _FakeOllama:
    def __init__(self, raw):
        self.raw = raw

    def generate_json_array(self, prompt, **kwargs):
        return self.raw


def _figure(token="FIGURE 1", caption="Actor lifecycle"):
    return {"token": token, "kind": "figure", "url": "https://x.test/y.png", "caption": caption}


def test_figure_card_uses_image_front_and_prose_back():
    card = _figure_card(_figure("FIGURE 2", "Hierarchy"), "The diagram shows the class hierarchy.")
    assert card.front == "What does this figure show?\n[FIGURE 2]"
    assert card.back == "The diagram shows the class hierarchy."
    assert card.code_ref == "FIGURE 2" and card.card_type == "recall"


def test_figure_card_falls_back_to_caption():
    card = _figure_card(_figure("FIGURE 3", "Actor lifecycle"), "")
    assert card.front == "What does this figure show?\n[FIGURE 3]"
    assert card.back == "Actor lifecycle"


def test_figure_card_skips_uncaptioned_figure_without_prose():
    assert _figure_card(_figure("FIGURE 4", ""), "") is None


def test_figure_card_ignores_diagram_language_placeholder_caption():
    asset = {"token": "FIGURE 6", "kind": "figure", "url": "", "caption": "mermaid"}
    assert _figure_card(asset, "") is None
    card = _figure_card(asset, "The flow below shows the retry loop.")
    assert card.back == "The flow below shows the retry loop."


def test_figure_card_rejects_prose_with_embedded_tokens():
    card = _figure_card(_figure("FIGURE 5", "X"), "The code uses [CODE 1] here.")
    # the marker is scrubbed, so the clean sentence is usable as the answer
    assert "[CODE" not in card.back


def test_figure_card_uses_permissive_context_for_bulleted_prose():
    """A truncated/bulleted context still yields a description (issue #38)."""
    asset = {"token": "FIGURE 8", "kind": "figure", "url": "", "caption": "mermaid"}
    card = _figure_card(asset, "and dependencies, using notation.\n- **Transitive inheritance**: A class inherits through a chain.")
    assert card is not None
    assert "Transitive inheritance" in card.back


def test_asset_context_finds_captioned_figure_token():
    from flashygen.flashcard_generator import _asset_context
    content = "Intro. [FIGURE 7: Actor lifecycle] Outro."
    assert _asset_context(content, "FIGURE 7") == content


def test_generate_backfills_figure_card(monkeypatch):
    from flashygen import flashcard_generator as fg
    gen = FlashcardGenerator(None, provider="ollama", validate=False)
    gen.ollama = _FakeOllama([
        {"front": "Q?", "back": "A long enough answer about the actor diagram.", "type": "recall"},
    ])
    assets = [_figure("FIGURE 1", "Actor lifecycle")]
    content = (
        "The diagram below shows the Actor lifecycle.\n\n"
        "[FIGURE 1: Actor lifecycle]\n\n"
        "The actor is the base object type."
    )
    cards = gen.generate_flashcards(content, "T", assets=assets)
    figures = [c for c in cards if c.code_ref == "FIGURE 1"]
    assert len(figures) == 1
    assert figures[0].front == "What does this figure show?\n[FIGURE 1]"
    assert figures[0].back == "The diagram below shows the Actor lifecycle."


def test_generate_does_not_duplicate_already_cited_figure(monkeypatch):
    from flashygen import flashcard_generator as fg
    gen = FlashcardGenerator(None, provider="ollama", validate=False)
    gen.ollama = _FakeOllama([
        {"front": "Which diagram shows the lifecycle?", "back": "See [FIGURE 1].", "type": "recall"},
    ])
    assets = [_figure("FIGURE 1", "Actor lifecycle")]
    content = "The diagram below shows the Actor lifecycle.\n\n[FIGURE 1: Actor lifecycle]"
    cards = gen.generate_flashcards(content, "T", assets=assets)
    figures = [c for c in cards if c.code_ref == "FIGURE 1"]
    assert len(figures) == 1  # only the model's card, no backfill duplicate
