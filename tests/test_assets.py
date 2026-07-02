"""Tests for the asset registry: verbatim code + figures carried into cards (issue #8)."""
from pathlib import Path

from flashygen.anki_exporter import AnkiExporter
from flashygen.content_parser import NotionContentParser
from flashygen.flashcard_generator import _build_ollama_prompt


def _code_block(code: str, language: str = "cpp") -> dict:
    return {
        "type": "code",
        "code": {
            "rich_text": [{"plain_text": code, "annotations": {}}],
            "language": language,
        },
    }


def _image_block(url: str, caption: str) -> dict:
    return {
        "type": "image",
        "image": {
            "type": "external",
            "external": {"url": url},
            "caption": [{"plain_text": caption, "annotations": {}}],
        },
    }


def test_parser_registers_code_block_and_emits_token():
    parser = NotionContentParser()
    text = parser.parse_blocks([_code_block("int x = 1;")])
    assert "[CODE 1]" in text
    assert "```cpp\nint x = 1;\n```" in text
    assert parser.assets == [
        {"token": "CODE 1", "kind": "code", "language": "cpp", "content": "int x = 1;"}
    ]


def test_parser_registers_image_and_emits_token():
    parser = NotionContentParser()
    text = parser.parse_blocks([_image_block("https://x.test/d.png", "Actor lifecycle")])
    assert "[FIGURE 1: Actor lifecycle]" in text
    assert parser.assets == [
        {"token": "FIGURE 1", "kind": "figure", "url": "https://x.test/d.png", "caption": "Actor lifecycle"}
    ]


def test_registry_resets_between_pages():
    parser = NotionContentParser()
    parser.parse_blocks([_code_block("int x = 1;")])
    parser.parse_blocks([_code_block("int y = 2;")])
    assert len(parser.assets) == 1
    assert parser.assets[0]["content"] == "int y = 2;"


def test_ollama_prompt_mentions_asset_tokens():
    prompt = _build_ollama_prompt("content [CODE 1]", "Title")
    assert "[CODE n]" in prompt and "[FIGURE n]" in prompt


def test_exporter_inlines_verbatim_code_for_token():
    assets = [{"token": "CODE 1", "kind": "code", "language": "cpp", "content": 'int x = 1; // "quoted"'}]
    html, media = AnkiExporter()._substitute_assets("See [CODE 1] here.", assets, Path("."))
    assert '<pre data-language="cpp">' in html
    assert "int x = 1; // &quot;quoted&quot;" in html
    assert "[CODE 1]" not in html
    assert media == []


def test_exporter_downloads_and_embeds_figure(tmp_path, monkeypatch):
    from flashygen import anki_exporter

    class FakeResponse:
        content = b"\x89PNG fake"
        def raise_for_status(self):
            pass

    monkeypatch.setattr(anki_exporter.requests, "get", lambda url, timeout: FakeResponse())
    assets = [{"token": "FIGURE 1", "kind": "figure", "url": "https://x.test/d.png", "caption": "c"}]
    html, media = AnkiExporter()._substitute_assets("Diagram: [FIGURE 1]", assets, tmp_path)
    assert '<img src="fg_1.png">' in html
    assert media == [str(tmp_path / "fg_1.png")]
    assert (tmp_path / "fg_1.png").read_bytes() == b"\x89PNG fake"


def test_exporter_leaves_unknown_tokens_untouched():
    html, media = AnkiExporter()._substitute_assets("See [CODE 9].", [], Path("."))
    assert "[CODE 9]" in html and media == []
