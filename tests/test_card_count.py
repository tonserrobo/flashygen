"""Tests for card count constraints."""
import ast
import pathlib

from flashygen.flashcard_generator import _build_claude_prompt, _build_ollama_prompt

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
    prompt = _build_claude_prompt("some content", "Test Page", 3)
    assert "AT MOST 8" in prompt, "Prompt must include hard cap of AT MOST 8 cards per section"
    assert "MAXIMUM GRANULARITY" not in prompt, "Prompt must not instruct maximum granularity"
    assert "More cards is better" not in prompt, "Prompt must not encourage card inflation"

def test_ollama_prompt_generates_json_array():
    """Ollama prompt must demand a JSON-array-only response."""
    prompt = _build_ollama_prompt("some content", "Test Page")
    assert "JSON array" in prompt
    assert "some content" in prompt

def test_ollama_prompt_states_target_card_count():
    """cards_per_concept must reach the prompt, not just the CLI banner (issue #14)."""
    assert "Aim for about 3 cards" in _build_ollama_prompt("c", "T")
    assert "Aim for about 5 cards" in _build_ollama_prompt("c", "T", cards_per_concept=5)
