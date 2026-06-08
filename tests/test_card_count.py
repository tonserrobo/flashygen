"""Tests for card count constraints."""
import ast
import pathlib
import pytest

from flashygen.flashcard_generator import FlashcardGenerator

def test_max_sections_is_ten():
    """main.py must cap sections at 10 to keep total cards ≤150."""
    source = (pathlib.Path(__file__).parent.parent / "main.py").read_text()
    tree = ast.parse(source)
    max_sections_values = []
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "max_sections":
            if isinstance(node.value, ast.Constant):
                max_sections_values.append(node.value.value)
    assert max_sections_values, "No max_sections keyword argument found in main.py"
    assert all(v <= 10 for v in max_sections_values), (
        f"max_sections must be ≤10 to keep total cards ≤150. Found: {max_sections_values}"
    )

def test_claude_prompt_has_card_cap():
    """Claude prompt must contain the AT MOST 8 cards cap."""
    gen = FlashcardGenerator(api_key="dummy", model="claude-haiku-4-5-20251001", provider="claude")
    prompt = gen._build_claude_prompt("some content", "Test Page", 3)
    assert "AT MOST 8" in prompt, "Prompt must include hard cap of AT MOST 8 cards per section"
    assert "MAXIMUM GRANULARITY" not in prompt, "Prompt must not instruct maximum granularity"
    assert "More cards is better" not in prompt, "Prompt must not encourage card inflation"

def test_ollama_prompt_unaffected():
    """Ollama prompt is separate and should not be changed."""
    pytest.importorskip("ollama", minversion=None)
    gen = FlashcardGenerator(api_key=None, model="phi3", provider="ollama")
    prompt = gen._build_ollama_prompt("some content", "Test Page")
    assert prompt.startswith("Generate Anki flashcards")
