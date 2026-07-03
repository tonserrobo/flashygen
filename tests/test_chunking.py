"""Tests for fence-aware chunking (issue #2)."""
from flashygen.content_parser import NotionContentParser, chunk_text


def _fences_balanced(chunk: str) -> bool:
    return sum(1 for l in chunk.split("\n") if l.lstrip().startswith("```")) % 2 == 0


CODE_BLOCK = "```cpp\n" + "\n".join(f"void Function{i}(int Arg{i});  // line {i}" for i in range(12)) + "\n```"


def test_code_block_never_split():
    """A fenced block spanning the size boundary must stay whole in one chunk."""
    prose = "\n".join(f"Paragraph line {i} " + "x" * 80 for i in range(6))
    chunks = chunk_text(prose + "\n" + CODE_BLOCK + "\n" + prose, max_chars=400)
    assert len(chunks) > 1  # still actually chunking
    assert all(_fences_balanced(c) for c in chunks)
    assert sum(1 for c in chunks if CODE_BLOCK in c) == 1  # block intact and contiguous


def test_fence_joins_preceding_context_even_when_overflowing():
    """The explanation line before a code block must land in the same chunk as the block."""
    intro = "The macro is defined as follows:"
    chunks = chunk_text(intro + "\n" + CODE_BLOCK, max_chars=200)
    assert len(chunks) == 1
    assert intro in chunks[0] and CODE_BLOCK in chunks[0]


def test_blank_lines_preserved_inside_fence():
    block = "```cpp\nint a;\n\nint b;\n```"
    chunks = chunk_text("Intro line.\n\n" + block, max_chars=500)
    assert len(chunks) == 1
    assert block in chunks[0]
    assert "Intro line.\n" in chunks[0]  # blank prose lines dropped, prose kept


def test_plain_text_still_splits():
    lines = "\n".join(f"line {i} " + "y" * 60 for i in range(20))
    chunks = chunk_text(lines, max_chars=300)
    assert len(chunks) > 3
    assert all(len(c) <= 300 for c in chunks)
    assert "".join(chunks).replace("\n", "") == lines.replace("\n", "")  # nothing lost


def test_tiny_tail_chunk_merged_into_previous():
    """A sub-min remainder must not become its own chunk — it only yields thin cards (issue #15)."""
    content = "a" * 900 + "\n" + "b" * 900 + "\n" + "c" * 100
    chunks = chunk_text(content, max_chars=1000)
    assert len(chunks) == 2
    assert chunks[-1] == "b" * 900 + "\n" + "c" * 100  # tail folded in, nothing lost


def test_preamble_before_first_h1_gets_named_section():
    """Content before the first H1 must not produce an empty heading (issue #18)."""
    parser = NotionContentParser()
    sections = parser.extract_content_sections("Intro line.\n# Setup\nBody.", max_heading_level=1)
    assert [s["heading"] for s in sections] == ["Introduction", "Setup"]
    assert sections[0]["content"] == "Intro line."


def test_split_large_sections_preserves_fences():
    parser = NotionContentParser()
    prose = "\n".join(f"Explanatory sentence number {i}. " + "z" * 70 for i in range(8))
    sections = [{"heading": "Macros", "content": prose + "\n" + CODE_BLOCK + "\n" + prose}]
    result = parser.split_large_sections(sections, max_section_size=400)
    assert len(result) > 1
    assert all(_fences_balanced(s["content"]) for s in result)
    assert sum(1 for s in result if CODE_BLOCK in s["content"]) == 1
