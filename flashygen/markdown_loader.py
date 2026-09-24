"""Load and section Obsidian / markdown notes from a directory into the
FlashyGen pipeline.

The Notion path goes through the block API; markdown notes are already text.
This module adapts markdown so it plugs into the same downstream stages
(generation, manifest, check/update):

- Scans a directory recursively for every ``.md`` file.
- Each file becomes its own content blob; sections are split from its headings.
- Fenced code blocks and image links are pulled out into the shared asset
  registry and replaced with ``[CODE n]`` / ``[FIGURE n]`` tokens, so the
  existing cloze-over-code and figure-embed logic works unchanged.
- One deck per directory: every file's sections are combined, and the folder
  name is the deck title.

Markdown files with YAML frontmatter have it stripped before sectioning.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

from flashygen.content_parser import NotionContentParser

_FENCE_RE = re.compile(r"```([\w+#.-]*)")
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
_H1_RE = re.compile(r"^#\s+(.+)$")
# Notion's text-colour markup (`~={red}...=~`) survives copy-as-markdown exports
# and would otherwise leak into headings, section names, and card text (issue #35).
_NOTION_COLOR_RE = re.compile(r"~=\{[^{}]*\}(.*?)=~", re.DOTALL)
# Diagram fence languages are illustrations, not code to memorise. They are
# registered as figures (not code) so they never become cloze targets and never
# consume CODE n slots (mirrors flashcard_generator._DIAGRAM_LANGUAGES).
_DIAGRAM_LANGUAGES = {"mermaid", "plantuml", "dot", "graphviz"}


def find_markdown_files(path: str | Path) -> List[Path]:
    """Return every ``.md`` file under ``path`` (recursive), sorted.

    ``path`` may be a single markdown file or a directory. Hidden files and
    directories (dot-prefixed) are skipped, matching Obsidian's default of not
    indexing them.
    """
    root = Path(path)
    if root.is_file():
        return [root] if root.suffix.lower() == ".md" else []

    files: List[Path] = []
    for candidate in sorted(root.rglob("*.md"), key=lambda p: str(p).lower()):
        if any(part.startswith(".") for part in candidate.relative_to(root).parts):
            continue
        files.append(candidate)
    return files


class MarkdownNoteLoader:
    """Turn a directory of markdown notes into sections and an asset registry."""

    def __init__(self):
        self.parser = NotionContentParser()
        self.assets: List[Dict[str, str]] = []
        self.files: List[Path] = []

    def _next_token(self, kind: str) -> str:
        n = sum(1 for a in self.assets if a["kind"] == kind) + 1
        return f"{kind.upper()} {n}"

    def _extract_assets(self, text: str) -> str:
        """Replace fenced code blocks and images with asset tokens.

        Returns the markdown with assets tokenized; ``self.assets`` holds the
        registry. Fences are consumed line-by-line so an unterminated fence
        never swallows the rest of the file.
        """
        lines = text.split("\n")
        out: List[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            m = _FENCE_RE.match(line.strip())
            if m and line.strip().startswith("```"):
                lang = m.group(1) or "code"
                body: List[str] = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    body.append(lines[i])
                    i += 1
                if i < len(lines):  # closing fence
                    i += 1
                code = "\n".join(body)
                if lang.strip().lower() in _DIAGRAM_LANGUAGES:
                    token = self._next_token("figure")
                    self.assets.append(
                        {"token": token, "kind": "figure", "url": "", "caption": lang,
                         "content": code}
                    )
                    out.append(f"[{token}: {lang}]")
                    continue
                token = self._next_token("code")
                self.assets.append(
                    {"token": token, "kind": "code", "language": lang, "content": code}
                )
                out.append(f"[{token}]\n```{lang}\n{code}\n```")
                continue

            out.append(line)
            i += 1

        content = "\n".join(out)

        def repl(match: re.Match) -> str:
            caption, url = match.group(1), match.group(2)
            token = self._next_token("figure")
            self.assets.append(
                {"token": token, "kind": "figure", "url": url, "caption": caption}
            )
            return f"[{token}: {caption}]" if caption else f"[{token}]"

        return _IMAGE_RE.sub(repl, content)

    def load_directory(self, path: str | Path) -> Tuple[str, List[Path]]:
        """Scan ``path`` and return combined tokenized content + file list.

        Files are prefixed with their own H1 (derived from the file name) so
        each note is addressable as a section, and the folder name becomes the
        deck title.
        """
        self.assets = []
        self.files = find_markdown_files(path)
        if not self.files:
            raise FileNotFoundError(
                f"No .md files found under {path} — point at a directory of "
                "markdown notes or a single .md file."
            )

        parts: List[str] = []
        for file in self.files:
            raw = file.read_text(encoding="utf-8")
            raw = _FRONTMATTER_RE.sub("", raw)
            raw = self._strip_notion_markup(raw)
            raw = self._relevel_internal_h1(raw)
            content = self._extract_assets(raw).strip()
            title = self._note_title(file)
            parts.append(f"# {title}\n\n{content}")
        return "\n\n".join(parts), self.files

    @staticmethod
    def _strip_notion_markup(text: str) -> str:
        """Remove Notion colour spans (`~={red}text=~`) from markdown content.

        Colour annotations are dropped on the Notion API path, but the markdown
        path would otherwise carry the raw markup into headings and section
        names (issue #35).
        """
        return _NOTION_COLOR_RE.sub(lambda m: m.group(1).strip(), text)

    @staticmethod
    def _relevel_internal_h1(text: str) -> str:
        """Demote any in-note H1 (``# ...``) to H2.

        Each file is prefixed with its own H1 derived from the file stem, so a
        note that already contains a top-level heading would otherwise split
        itself into its own top-level section (issue #25). Fenced code blocks
        are skipped so ``#include``-style lines and diagram source are untouched.
        """
        lines = text.split("\n")
        out: List[str] = []
        in_fence = False
        for line in lines:
            if line.strip().startswith("```"):
                in_fence = not in_fence
                out.append(line)
                continue
            if not in_fence and _H1_RE.match(line):
                out.append("## " + _H1_RE.match(line).group(1))
                continue
            out.append(line)
        return "\n".join(out)

    @staticmethod
    def _note_title(file: Path) -> str:
        """Derive a section heading from the file path (relative to its folder)."""
        return file.stem


def directory_title(path: str | Path) -> str:
    """Deck title for a directory of notes — its folder name."""
    root = Path(path)
    if root.is_file():
        return root.stem
    return root.name or root.resolve().name


def section_markdown(path: str | Path) -> Tuple[Dict, NotionContentParser, List[Dict[str, str]]]:
    """Build the ``(page_data, parser, sections)`` triple used by the CLI.

    Mirrors ``main._fetch_and_section`` so markdown notes drop straight into
    the existing generate/check/update commands. ``page_data`` carries the
    fields those commands read: ``title``, ``id`` (a stable hash of the path),
    ``hierarchy``, and the asset registry is exposed via ``parser.assets``.
    """
    loader = MarkdownNoteLoader()
    content, files = loader.load_directory(path)
    parser = loader.parser
    parser.assets = loader.assets

    sections = parser.extract_content_sections(content, max_heading_level=1)
    if len(sections) < 3:
        sections_h2 = parser.extract_content_sections(content, max_heading_level=2)
        if len(sections_h2) > len(sections):
            sections = sections_h2
    if len(sections) > 20:
        sections = parser.merge_small_sections(sections, min_content_size=800, max_sections=10)
    sections = parser.split_large_sections(sections, max_section_size=1200)

    import hashlib

    title = directory_title(path)
    page_data = {
        "id": hashlib.sha1(str(Path(path).resolve()).encode("utf-8")).hexdigest()[:16],
        "title": title,
        "hierarchy": [str(Path(path).resolve().name)],
    }
    return page_data, parser, sections
