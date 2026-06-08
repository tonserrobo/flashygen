"""Generate flashcards using AI (Claude or Ollama)."""

import json
from typing import Any

from anthropic import Anthropic
from anthropic.types import TextBlock
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from flashygen.llm import OllamaClient, OllamaConfig

console = Console()

_CHUNK_MAX_CHARS = 800


class Flashcard:
    """Represents a single flashcard."""

    def __init__(self, front: str, back: str, tags: list[str] | None = None):
        self.front = front
        self.back = back
        self.tags = tags if tags is not None else []

    def __repr__(self):
        return f"Flashcard(front='{self.front[:50]}...', back='{self.back[:50]}...')"


class FlashcardGenerator:
    """Generate flashcards from content using AI (Claude or Ollama)."""

    def __init__(
        self,
        api_key: str | None,
        model: str = "gemma3:4b",
        provider: str = "ollama",
        ollama_base_url: str = "http://localhost:11434",
    ):
        self.provider = provider.lower()
        self.model = model

        if self.provider == "claude":
            if not api_key:
                raise ValueError("API key required for Claude provider")
            self.client = Anthropic(api_key=api_key)
            self.max_tokens = 8192
        else:
            config = OllamaConfig.from_env()
            config.model = model
            config.base_url = ollama_base_url
            self.ollama = OllamaClient(config)

    def generate_flashcards_from_sections(
        self,
        sections: list[dict[str, str]],
        title: str,
        cards_per_concept: int = 3,
        hierarchy: list[str] | None = None,
    ) -> list[Flashcard]:
        """Generate flashcards from multiple content sections (chunks).

        Each section is further split into sub-chunks so small Ollama models
        receive a focused, manageable prompt per call rather than one large blast.
        """
        all_flashcards: list[Flashcard] = []

        console.print(f"[cyan]Processing {len(sections)} section(s)...[/cyan]")

        hierarchy = hierarchy or []
        tag_parts = [part.replace(" ", "-") for part in hierarchy + [title]]
        hierarchy_tag = "::".join(tag_parts)
        console.print(f"[dim]Tag hierarchy: {hierarchy_tag}[/dim]")

        for i, section in enumerate(sections, 1):
            heading = section.get("heading", f"Section {i}")
            content = section.get("content", "")

            if not content.strip():
                console.print(f"[dim]Skipping empty section: {heading}[/dim]")
                continue

            console.print(f"\n[bold]Section {i}/{len(sections)}:[/bold] {heading}")

            try:
                section_flashcards = self.generate_flashcards(
                    content, f"{title} - {heading}", cards_per_concept
                )
                for card in section_flashcards:
                    card.tags = [hierarchy_tag]
                all_flashcards.extend(section_flashcards)
                console.print(f"[green]✓[/green] Generated {len(section_flashcards)} cards for this section")
            except Exception as e:
                console.print(f"[yellow]⚠[/yellow] Failed to generate cards for this section: {e}")
                console.print("[dim]Continuing with next section...[/dim]")

        return all_flashcards

    def generate_flashcards(
        self, content: str, title: str, cards_per_concept: int = 3
    ) -> list[Flashcard]:
        """Generate flashcards from content using AI.

        For Ollama: splits content into paragraph-level sub-chunks and calls the
        model once per chunk — keeps prompts small so gemma3-class models can
        handle each piece reliably.
        """
        if self.provider == "claude":
            return self._generate_claude(content, title, cards_per_concept)

        chunks = _split_into_chunks(content, max_chars=_CHUNK_MAX_CHARS)
        console.print(f"[dim]Split into {len(chunks)} sub-chunk(s) for iterative generation[/dim]")

        all_cards: list[Flashcard] = []
        for j, chunk in enumerate(chunks, 1):
            console.print(f"[cyan]  Chunk {j}/{len(chunks)} ({len(chunk)} chars)...[/cyan]")
            try:
                cards = self._generate_ollama_chunk(chunk, title)
                all_cards.extend(cards)
            except Exception as e:
                console.print(f"[yellow]  Chunk {j} failed: {e}[/yellow]")
        return all_cards

    # ------------------------------------------------------------------ #
    # Ollama path                                                          #
    # ------------------------------------------------------------------ #

    def _generate_ollama_chunk(self, content: str, title: str) -> list[Flashcard]:
        prompt = _build_ollama_prompt(content, title)
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
            p.add_task("Generating...", total=None)
            raw: list[Any] = self.ollama.generate_json_array(prompt)
        return _parse_raw_cards(raw, title)

    # ------------------------------------------------------------------ #
    # Claude path                                                          #
    # ------------------------------------------------------------------ #

    def _generate_claude(self, content: str, title: str, cards_per_concept: int) -> list[Flashcard]:
        prompt = _build_claude_prompt(content, title, cards_per_concept)
        console.print("[cyan]Generating flashcards with Claude...[/cyan]")
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
            p.add_task("Thinking...", total=None)
            message = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        first_block = message.content[0]
        if not isinstance(first_block, TextBlock):
            raise ValueError(f"Unexpected content block type: {type(first_block)}")
        response_text = first_block.text

        # Claude returns a JSON array as text — parse it
        response_text = response_text.strip()
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1]).lstrip("json").strip().rstrip("`").strip()
        if not response_text.startswith("["):
            start = response_text.find("[")
            if start == -1:
                raise ValueError("No JSON array found in Claude response")
            response_text = response_text[start:]

        raw: list[Any] = json.loads(response_text, strict=False)
        cards = _parse_raw_cards(raw, title)
        console.print(f"[green]Generated {len(cards)} flashcards![/green]")
        return cards


# ------------------------------------------------------------------ #
# Helpers (module-level, no state)                                    #
# ------------------------------------------------------------------ #

def _split_into_chunks(content: str, max_chars: int = 800) -> list[str]:
    """Split content at paragraph boundaries, grouping up to max_chars per chunk."""
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    if not paragraphs:
        return [content] if content.strip() else []

    chunks: list[str] = []
    current: list[str] = []
    current_size = 0

    for para in paragraphs:
        if current_size + len(para) > max_chars and current:
            chunks.append("\n\n".join(current))
            current = [para]
            current_size = len(para)
        else:
            current.append(para)
            current_size += len(para)

    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _build_ollama_prompt(content: str, title: str) -> str:
    return f"""Generate Anki flashcards from the content below.

INSTRUCTIONS:
1. Return ONLY a JSON array — no explanations, no chat, no extra text.
2. Create one flashcard per distinct concept, command, or code example.
3. Keep answers concise (1-3 lines). Use \\n for newlines inside strings.

FORMAT:
[
  {{"front": "Question?", "back": "Answer", "type": "recall|command|conceptual"}}
]

CONTENT (from "{title}"):
{content}

RETURN ONLY THE JSON ARRAY — START WITH [ AND END WITH ]"""


def _build_claude_prompt(content: str, title: str, cards_per_concept: int) -> str:
    return f"""You are an expert at creating high-quality Anki flashcards for spaced repetition.

Content from Notion page "{title}". Generate AT MOST 8 focused cards.
Prioritise the most important concepts — quality over quantity.

Card types: recall, conceptual, application, comparison, command.
Requirements:
- Clear, specific questions
- Answers include code examples where relevant (use \\n for newlines)
- No redundant or near-duplicate questions

Content:
{content}

Return ONLY a valid JSON array. Each object: "front", "back", "type". No other text."""


def _parse_raw_cards(raw: list[Any], title: str) -> list[Flashcard]:
    cards: list[Flashcard] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        front = str(item.get("front", "")).strip()
        back = str(item.get("back", "")).strip()
        if front and back:
            cards.append(Flashcard(front, back, []))
    return cards
