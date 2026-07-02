"""Tests for equation/table block handling and drop visibility (issue #4)."""
from flashygen.anki_exporter import AnkiExporter
from flashygen.content_parser import NotionContentParser


def test_equation_block_emitted_as_display_math():
    parser = NotionContentParser()
    text = parser.parse_blocks([{"type": "equation", "equation": {"expression": r"\sqrt{x^2 + y^2 + z^2}"}}])
    assert text == r"$$\sqrt{x^2 + y^2 + z^2}$$"


def test_inline_equation_emitted_as_inline_math():
    parser = NotionContentParser()
    blocks = [{
        "type": "paragraph",
        "paragraph": {"rich_text": [
            {"plain_text": "The magnitude is ", "annotations": {}},
            {"type": "equation", "plain_text": r"|V| = \sqrt{x^2}", "annotations": {}},
        ]},
    }]
    assert parser.parse_blocks(blocks) == r"The magnitude is $|V| = \sqrt{x^2}$"


def test_table_rows_emitted_as_markdown():
    parser = NotionContentParser()
    blocks = [{
        "type": "table",
        "table": {},
        "children": [
            {"type": "table_row", "table_row": {"cells": [
                [{"plain_text": "Specifier", "annotations": {}}],
                [{"plain_text": "Effect", "annotations": {}}],
            ]}},
        ],
    }]
    assert "| Specifier | Effect |" in parser.parse_blocks(blocks)


def test_unhandled_block_types_are_recorded_not_silent():
    parser = NotionContentParser()
    parser.parse_blocks([{"type": "child_database", "child_database": {}}])
    assert parser.skipped_types == {"child_database"}
    parser.parse_blocks([{"type": "paragraph", "paragraph": {"rich_text": []}}])
    assert parser.skipped_types == set()  # reset per page


def test_exporter_converts_math_to_anki_mathjax():
    e = AnkiExporter()
    assert r"\[\sqrt{x^2}\]" in e._format_content(r"$$\sqrt{x^2}$$")
    out = e._format_content(r"magnitude $x_1 * x_2$ here")
    assert r"\(x_1 * x_2\)" in out
    assert "<em>" not in out  # math must be protected from italic/bold mangling


def test_exporter_escapes_html_inside_math():
    out = AnkiExporter()._format_content(r"$a < b$")
    assert r"\(a &lt; b\)" in out
