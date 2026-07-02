"""Tests for Anki export formatting and output paths."""
from pathlib import Path

from flashygen.anki_exporter import AnkiExporter
from flashygen.flashcard_generator import Flashcard


def test_cpp_fence_language_preserved():
    """A ```c++ fence must keep its full language tag and not leak '++' into the code."""
    out = AnkiExporter()._format_content('Example:\n```c++\n#include "X.h"\nvoid F();\n```')
    assert 'data-language="c++"' in out
    assert "++<br>" not in out  # stray '++' must not be injected as the first code line
    assert "#include &quot;X.h&quot;" in out


def test_fence_without_language_still_renders():
    out = AnkiExporter()._format_content("```\nint x = 1;\n```")
    assert 'data-language="code"' in out
    assert "int x = 1;" in out


def test_default_output_goes_to_decks_dir(tmp_path, monkeypatch):
    """With no --output, decks land in decks/, not the working-directory root."""
    monkeypatch.chdir(tmp_path)
    result = AnkiExporter().create_deck([Flashcard("Q?", "A.")], "Test Deck")
    assert Path(result) == Path("decks") / "Test_Deck.apkg"
    assert (tmp_path / "decks" / "Test_Deck.apkg").exists()
