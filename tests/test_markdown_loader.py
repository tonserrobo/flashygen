"""Tests for markdown/Obsidian note ingestion (flashygen.markdown_loader)."""
from pathlib import Path

from flashygen.markdown_loader import (
    MarkdownNoteLoader,
    find_markdown_files,
    section_markdown,
)


def _write(tmp_path: Path, rel: str, content: str) -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def test_find_markdown_files_recursive(tmp_path):
    _write(tmp_path, "a.md", "# A")
    _write(tmp_path, "sub/b.md", "# B")
    _write(tmp_path, "sub/deep/c.md", "# C")
    _write(tmp_path, "notes.txt", "not markdown")
    _write(tmp_path, ".hidden/h.md", "# hidden")
    _write(tmp_path, "sub/.hidden2/x.md", "# hidden2")

    files = find_markdown_files(tmp_path)
    rels = [p.relative_to(tmp_path).as_posix() for p in files]
    assert rels == ["a.md", "sub/b.md", "sub/deep/c.md"]


def test_single_file_path(tmp_path):
    f = _write(tmp_path, "only.md", "# Only")
    assert find_markdown_files(f) == [f]


def test_no_markdown_raises(tmp_path):
    _write(tmp_path, "readme.txt", "hi")
    from flashygen.markdown_loader import MarkdownNoteLoader

    try:
        MarkdownNoteLoader().load_directory(tmp_path)
        assert False, "should have raised FileNotFoundError"
    except FileNotFoundError:
        pass


def test_code_blocks_tokenized_as_assets(tmp_path):
    _write(tmp_path, "note.md", "# Note\n\n```python\nx = 1\n```\n\nText.")
    loader = MarkdownNoteLoader()
    content, _ = loader.load_directory(tmp_path)

    assert "[CODE 1]" in content
    assert "```python\nx = 1\n```" in content
    assert loader.assets == [
        {"token": "CODE 1", "kind": "code", "language": "python", "content": "x = 1"}
    ]


def test_images_tokenized_as_figures(tmp_path):
    _write(tmp_path, "note.md", "# Note\n\n![Diagram](fig.png)\n\n![][x]\n\nPlain ![alt](y.png) link.")
    loader = MarkdownNoteLoader()
    content, _ = loader.load_directory(tmp_path)

    assert "[FIGURE 1: Diagram]" in content
    assert "[FIGURE 2: alt]" in content
    assert loader.assets[0]["kind"] == "figure"
    assert loader.assets[0]["url"] == "fig.png"
    assert loader.assets[0]["caption"] == "Diagram"


def test_yaml_frontmatter_stripped(tmp_path):
    _write(tmp_path, "note.md", "---\ntitle: My Note\ntags: [a, b]\n---\n\n# Real Heading\n\nBody")
    loader = MarkdownNoteLoader()
    content, _ = loader.load_directory(tmp_path)
    assert "title: My Note" not in content
    assert "Real Heading" in content


def test_section_markdown_builds_pipeline_triple(tmp_path):
    _write(tmp_path, "note.md", "# Concepts\n\nAlpha is the first.\n\n## Detail\n\nBeta.")
    page_data, parser, sections = section_markdown(tmp_path)

    assert page_data["title"] == tmp_path.name
    assert page_data["id"]
    assert "Concepts" in [s["heading"] for s in sections]
    assert parser.assets == []


def test_assets_flow_into_parser(tmp_path):
    _write(tmp_path, "note.md", "# Code\n\n```cpp\nint x;\n```")
    page_data, parser, sections = section_markdown(tmp_path)
    assert parser.assets[0]["token"] == "CODE 1"


def test_deterministic_page_id(tmp_path):
    _write(tmp_path, "note.md", "# A")
    id1 = section_markdown(tmp_path)[0]["id"]
    id2 = section_markdown(tmp_path)[0]["id"]
    assert id1 == id2
