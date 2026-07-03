"""Generate flashcards using AI (Claude or Ollama)."""

import difflib
import json
import re
from pathlib import Path
from typing import Any

from anthropic import Anthropic
from anthropic.types import TextBlock
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from flashygen.content_parser import chunk_text
from flashygen.llm import OllamaClient, OllamaConfig

console = Console()

_CHUNK_MAX_CHARS = 1200


class Flashcard:
    """Represents a single flashcard."""

    def __init__(
        self,
        front: str,
        back: str,
        tags: list[str] | None = None,
        card_type: str = "recall",
        explainer: str = "",
        code_ref: str = "",
        blanks: list[str] | None = None,
    ):
        self.front = front
        self.back = back
        self.tags = tags if tags is not None else []
        self.card_type = card_type
        self.explainer = explainer
        self.code_ref = code_ref
        self.blanks = blanks if blanks is not None else []

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
        validate: bool = True,
    ):
        self.provider = provider.lower()
        self.model = model
        self.validate = validate

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
        assets: list[dict] | None = None,
        work_dir: str | None = None,
    ) -> list[Flashcard]:
        """Generate flashcards from multiple content sections (chunks).

        Each section is further split into sub-chunks so small Ollama models
        receive a focused, manageable prompt per call rather than one large blast.

        With `work_dir`, each section's cards are checkpointed to disk right
        after generation; a re-run resumes from checkpoints whose section
        content is unchanged instead of calling the model again.
        """
        # lazy import: manifest imports Flashcard from this module
        from flashygen.manifest import card_from_dict, card_to_dict, section_hash

        all_flashcards: list[Flashcard] = []

        console.print(f"[cyan]Processing {len(sections)} section(s)...[/cyan]")

        hierarchy = hierarchy or []
        tag_parts = [part.replace(" ", "-") for part in hierarchy + [title]]
        hierarchy_tag = "::".join(tag_parts)
        console.print(f"[dim]Tag hierarchy: {hierarchy_tag}[/dim]")

        work = Path(work_dir) if work_dir else None
        if work:
            work.mkdir(parents=True, exist_ok=True)

        for i, section in enumerate(sections, 1):
            heading = section.get("heading", f"Section {i}")
            content = section.get("content", "")

            if not content.strip():
                console.print(f"[dim]Skipping empty section: {heading}[/dim]")
                continue

            console.print(f"\n[bold]Section {i}/{len(sections)}:[/bold] {heading}")

            content_hash = section_hash(content)
            checkpoint = work / f"section_{i:02d}.json" if work else None
            if checkpoint and checkpoint.exists():
                data = json.loads(checkpoint.read_text(encoding="utf-8"))
                # an empty checkpoint is a failed attempt, not a result — regenerate
                if data.get("content_hash") == content_hash and data.get("cards"):
                    cards = [card_from_dict(d) for d in data["cards"]]
                    for card in cards:
                        card.tags = [hierarchy_tag, f"type::{card.card_type}"]
                        card.section = heading  # re-stamp: checkpoint may predate a heading rename
                    all_flashcards.extend(cards)
                    console.print(f"[dim]✓ Resumed {len(cards)} cards from checkpoint[/dim]")
                    continue

            try:
                section_flashcards = self.generate_flashcards(
                    content, f"{title} - {heading}", cards_per_concept, assets=assets
                )
                if not section_flashcards:
                    console.print("[dim]  0 cards — retrying section once[/dim]")
                    section_flashcards = self.generate_flashcards(
                        content, f"{title} - {heading}", cards_per_concept, assets=assets
                    )
                for card in section_flashcards:
                    card.tags = [hierarchy_tag, f"type::{card.card_type}"]
                    card.section = heading
                if checkpoint:
                    checkpoint.write_text(json.dumps({
                        "heading": heading,
                        "content_hash": content_hash,
                        "cards": [card_to_dict(c) for c in section_flashcards],
                    }, ensure_ascii=False), encoding="utf-8")
                all_flashcards.extend(section_flashcards)
                console.print(f"[green]✓[/green] Generated {len(section_flashcards)} cards for this section")
            except Exception as e:
                console.print(f"[yellow]⚠[/yellow] Failed to generate cards for this section: {e}")
                console.print("[dim]Continuing with next section...[/dim]")

        # per-section _quality_gate can't see other sections; summary sections
        # restate earlier facts, so dedupe once over the whole deck (issue #22)
        if self.provider != "claude" and len(all_flashcards) > 1:
            before = len(all_flashcards)
            all_flashcards = _dedupe_cards_llm(self.ollama, all_flashcards)
            if len(all_flashcards) < before:
                console.print(
                    f"[yellow]Dropped {before - len(all_flashcards)} cross-section duplicate card(s)[/yellow]"
                )

        return all_flashcards

    def generate_flashcards(
        self,
        content: str,
        title: str,
        cards_per_concept: int = 3,
        assets: list[dict] | None = None,
    ) -> list[Flashcard]:
        """Generate flashcards from content using AI.

        For Ollama: splits content into paragraph-level sub-chunks and calls the
        model once per chunk — keeps prompts small so gemma3-class models can
        handle each piece reliably.
        """
        if self.provider == "claude":
            all_cards = self._generate_claude(content, title, cards_per_concept)
        else:
            chunks = chunk_text(content, max_chars=_CHUNK_MAX_CHARS)
            console.print(f"[dim]Split into {len(chunks)} sub-chunk(s) for iterative generation[/dim]")

            all_cards = []
            for j, chunk in enumerate(chunks, 1):
                console.print(f"[cyan]  Chunk {j}/{len(chunks)} ({len(chunk)} chars)...[/cyan]")
                try:
                    cards = self._generate_ollama_chunk(chunk, title, cards_per_concept)
                    all_cards.extend(cards)
                except Exception as e:
                    console.print(f"[yellow]  Chunk {j} failed: {e}[/yellow]")

            # Deterministic cloze backfill (issue #17): every [CODE n] in this
            # content gets a dedicated focused call instead of relying on the
            # main prompt's single card to also be a cloze.
            if assets:
                covered = {c.code_ref for c in all_cards if c.card_type == "cloze"}
                for token in dict.fromkeys(re.findall(r"\[(CODE \d+)\]", content)):
                    if token in covered:
                        continue
                    asset = next((a for a in assets if a["token"] == token), None)
                    if asset is None:
                        continue
                    if asset.get("language", "").lower() in _DIAGRAM_LANGUAGES:
                        continue  # diagrams are illustrations, not code to memorise (issue #21)
                    cloze = _generate_code_cloze(self.ollama, asset, _asset_context(content, token))
                    if cloze:
                        all_cards.append(cloze)
                        console.print(f"[dim]  + cloze card for [{token}][/dim]")

        kept, dropped = _quality_gate(all_cards, assets=assets)
        if dropped:
            console.print(f"[yellow]Quality gate dropped {dropped} thin/duplicate card(s)[/yellow]")
        return kept

    # ------------------------------------------------------------------ #
    # Ollama path                                                          #
    # ------------------------------------------------------------------ #

    def _generate_ollama_chunk(self, content: str, title: str, cards_per_concept: int = 3) -> list[Flashcard]:
        prompt = _build_ollama_prompt(content, title, cards_per_concept)
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
            p.add_task("Generating...", total=None)
            raw: list[Any] = self.ollama.generate_json_array(prompt)
        cards = _parse_raw_cards(raw, title)
        if self.validate and cards:
            before = len(cards)
            cards = _validate_cards_llm(self.ollama, content, cards)
            if len(cards) < before:
                console.print(f"[yellow]  Validation dropped {before - len(cards)} ungrounded card(s)[/yellow]")
        return cards

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

def _build_ollama_prompt(content: str, title: str, cards_per_concept: int = 3) -> str:
    return f"""You are creating Anki flashcards for a student studying "{title}".

OUTPUT: a JSON array only — no prose, no markdown fences, no explanation.

RULES:
- Aim for about {cards_per_concept} cards (1 to 6), one per distinct fact, command, or
  pitfall — only as many as the content genuinely supports. Never pad with trivia.
- Every distinct command, error, setting, or code snippet must get its own card.
- Lines starting with | are table rows — a dense list of facts. Make one card per
  non-obvious row: the row's decision, value, or purpose is the answer.
- Card types:
    "recall"      — definition or fact ("What is X?")
    "command"     — exact syntax or step ("How do you X?" / back includes full code/command)
    "conceptual"  — reasoning or why ("Why does X happen?")
    "troubleshoot"— problem → solution ("Error: X" → "Fix: Y")
- Backs must be self-contained and specific: state the fact AND the detail that makes it
  useful (a default value, a pitfall, where it lives). One-line trivia backs are rejected.
- For "command" and "troubleshoot" cards the back MUST include the full command or code block.
- The content may contain asset markers like [CODE n] or [FIGURE n: caption]. When a card
  is about that code or figure, put the bare token [CODE n] or [FIGURE n] in the back —
  it is replaced with the real code/image later. Do NOT retype marked code yourself.
- Optionally add "explainer": 1-3 sentences of context BEYOND the answer (why it matters,
  a pitfall, a connection to another concept). Never restate the answer; use "" if you
  have nothing genuine to add.
- Use \\n for newlines inside JSON strings.

EXAMPLE of a good card:
{{"front": "How do you mark a UPROPERTY for replication with a change callback?", "back": "Use ReplicatedUsing and register it in GetLifetimeReplicatedProps:\\n[CODE 2]\\nWithout the DOREPLIFETIME entry the value silently never replicates.", "explainer": "This is a frequent source of silent multiplayer bugs — the engine gives no warning when the DOREPLIFETIME entry is missing.", "type": "command"}}

SCHEMA:
[
  {{"front": "Question?", "back": "Full answer with code if relevant.", "explainer": "Optional deeper context or \\"\\".", "type": "recall|command|conceptual|troubleshoot"}}
]

CONTENT:
{content}

Return ONLY the JSON array."""


def _build_claude_prompt(content: str, title: str, cards_per_concept: int) -> str:
    return f"""You are an expert at creating high-quality Anki flashcards for spaced repetition.

Content from Notion page "{title}". Generate AT MOST 8 focused cards.
Prioritise the most important concepts — quality over quantity.

Card types: recall, conceptual, application, comparison, command.
Requirements:
- Clear, specific questions
- Answers include code examples where relevant (use \\n for newlines)
- If the content contains [CODE n] or [FIGURE n] markers, cite the bare token in the back
  of any card about that asset instead of reproducing it — it is substituted later
- No redundant or near-duplicate questions
- Lines starting with | are table rows — dense fact lists; card the non-obvious rows

Content:
{content}

Return ONLY a valid JSON array. Each object: "front", "back", "type", and optionally
"explainer" (1-3 sentences of context beyond the answer, or ""). No other text."""


_DIAGRAM_LANGUAGES = {"mermaid", "plantuml", "dot", "graphviz"}

_CLOZE_PROMPT = """From this {language} code, pick 1 to 3 short substrings worth memorising —
a specifier, macro name, function name, or key argument. Copy each EXACTLY as it
appears in the code. Never pick whole lines.

CONTEXT (the notes surrounding this code):
{context}

CODE:
{code}

Prefer blanks that carry the point the CONTEXT makes about the code.
If the CONTEXT presents the code as a mistake, an anti-pattern, or something that
does not compile (watch for "naive", "do NOT", "wrong", a ❌ mark, "won't compile",
or a fix shown right after), do NOT pick blanks. Instead return:
[{{"negative": true, "problem": "what is wrong with the code", "fix": "the correct approach"}}]

Otherwise return ONLY JSON: [{{"blanks": ["exact substring"], "hint": "one line saying what the code does"}}]"""


def _asset_context(content: str, token: str, radius: int = 300) -> str:
    """Prose around [token] with code fences stripped — the teaching point
    lives in the sentences before/after the code, not in the code (issue #20)."""
    prose = re.sub(r"```.*?(```|$)", "", content, flags=re.S)
    idx = prose.find(f"[{token}]")
    if idx == -1:
        return ""
    return prose[max(0, idx - radius): idx + len(token) + 2 + radius].strip()


def _generate_code_cloze(client: Any, asset: dict, context: str = "") -> Flashcard | None:
    """One focused model call per code asset → one cloze card (issue #17).

    The asset registry has the exact code, so blanks are validated as substrings
    here instead of hoping the main generation call gets the JSON right.
    Code the surrounding notes present as a mistake becomes a troubleshoot card
    instead of a memorisation cloze (issue #20).
    """
    try:
        raw = client.generate_json_array(_CLOZE_PROMPT.format(
            language=asset.get("language", "code"),
            code=asset["content"],
            context=context or "(none)",
        ))
    except Exception as e:
        console.print(f"[yellow]  cloze generation failed for [{asset['token']}]: {e}[/yellow]")
        return None
    for item in raw:
        if not isinstance(item, dict):
            continue
        if item.get("negative"):
            problem = str(item.get("problem", "")).strip()
            fix = str(item.get("fix", "")).strip()
            if not problem:
                return None
            token = asset["token"]
            return Flashcard(
                f"What is wrong with this code?\n[{token}]",
                f"[{token}]\n{problem}" + (f"\n\nFix: {fix}" if fix else ""),
                [],
                card_type="troubleshoot",
            )
        blanks = [str(b) for b in item.get("blanks", []) if str(b) and str(b) in asset["content"]]
        if blanks:
            hint = str(item.get("hint", "")).strip()
            return Flashcard(
                hint or f"Complete the code ({asset['token']})",
                f"[{asset['token']}]",
                [],
                card_type="cloze",
                code_ref=asset["token"],
                blanks=blanks[:3],
            )
    return None


_CARD_TYPES = {"recall", "command", "conceptual", "troubleshoot", "application", "comparison"}


def _parse_raw_cards(raw: list[Any], title: str) -> list[Flashcard]:
    cards: list[Flashcard] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        card_type = str(item.get("type", "")).strip().lower()

        if card_type == "cloze":
            code_ref = str(item.get("code_ref", "")).strip()
            blanks = [str(b).strip() for b in item.get("blanks", []) if str(b).strip()]
            hint = str(item.get("hint", "")).strip()
            if code_ref and blanks:
                cards.append(Flashcard(
                    hint or f"Complete the code ({code_ref})",
                    f"[{code_ref}]",
                    [],
                    card_type="cloze",
                    code_ref=code_ref,
                    blanks=blanks,
                ))
            continue

        front = str(item.get("front", "")).strip()
        back = str(item.get("back", "")).strip()
        if card_type not in _CARD_TYPES:
            card_type = "recall"
        explainer = str(item.get("explainer", "")).strip()
        if front and back:
            cards.append(Flashcard(front, back, [], card_type=card_type, explainer=explainer))
    return cards


_MIN_BACK_CHARS = 40
_CODE_REQUIRED_TYPES = {"command", "troubleshoot"}
_LEAK_MARKERS = ('"front"', '"back"', "JSON array", "recall|command")


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


_STOPWORDS = frozenset(
    "a an the is are was be to of in on for and or it this that what how "
    "which where when you your with as by at not no do does".split()
)


def _word_jaccard(a: str, b: str) -> float:
    wa = {w for w in _normalize(a).split() if w not in _STOPWORDS}
    wb = {w for w in _normalize(b).split() if w not in _STOPWORDS}
    return len(wa & wb) / len(wa | wb) if wa | wb else 0.0


_DEDUPE_PROMPT = """These flashcards all come from one deck. A summary or quick-reference
section often restates a fact that already has a card — find such duplicates.

CARDS:
{cards}

Return ONLY JSON: a (possibly empty) array of {{"keep": <n>, "drop": <m>}} pairs where
card m asks the same fact as card n. Distinct facts about the same topic are NOT duplicates."""


def _dedupe_cards_llm(client: Any, cards: list[Flashcard]) -> list[Flashcard]:
    """Deck-level near-duplicate removal (issue #22).

    String similarity can't do this: the observed real duplicate pair scores
    *lower* on front similarity than legitimate template-sharing pairs
    ('purpose of #pragma optimize' vs 'purpose of #pragma region'). So the
    model judges, and a drop is only honored when word overlap confirms the
    pair is actually related — a small model can't nuke unrelated cards.
    """
    qa = [(i, c) for i, c in enumerate(cards) if c.card_type != "cloze"]
    if len(qa) < 2:
        return cards
    listing = "\n".join(f"{n}. {c.front} — {c.back[:80]}" for n, (_, c) in enumerate(qa, 1))
    try:
        raw = client.generate_json_array(_DEDUPE_PROMPT.format(cards=listing))
    except Exception as e:
        console.print(f"[yellow]Dedupe pass failed, keeping all cards: {e}[/yellow]")
        return cards
    drop: set[int] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        k, d = item.get("keep"), item.get("drop")
        if not (isinstance(k, int) and isinstance(d, int)):
            continue
        if not (1 <= k <= len(qa) and 1 <= d <= len(qa)) or k == d:
            continue
        keep_card, drop_card = qa[k - 1][1], qa[d - 1][1]
        # ponytail: 0.15 calibrated on the 2026-07-03 decks — true dup 0.24, unrelated ≤0.09
        if _word_jaccard(keep_card.front + " " + keep_card.back,
                         drop_card.front + " " + drop_card.back) >= 0.15:
            drop.add(qa[d - 1][0])
    return [c for i, c in enumerate(cards) if i not in drop]


def _quality_gate(
    cards: list[Flashcard],
    assets: list[dict] | None = None,
) -> tuple[list[Flashcard], int]:
    """Drop cards too thin, leaked, duplicated, or citing unknown assets.

    Deterministic tier-1 checks; LLM grounding is _validate_cards_llm.
    Returns (kept, dropped_count).
    """
    known_tokens = {a["token"] for a in assets} if assets is not None else None
    kept: list[Flashcard] = []
    kept_fronts: list[str] = []
    for card in cards:
        if card.card_type == "cloze":
            # cloze cards live or die by their registry reference, nothing else
            if assets is not None:
                asset = next((a for a in assets if a["token"] == card.code_ref), None)
                if asset is None or any(b not in asset["content"] for b in card.blanks):
                    continue  # hallucinated ref or blank
            kept.append(card)
            continue

        front, back = card.front, card.back
        has_code = "```" in back or "[CODE" in back or "`" in back
        if card.card_type in _CODE_REQUIRED_TYPES and not has_code:
            continue
        # short backs are fine when they cite code — the token expands at export
        if len(back) < _MIN_BACK_CHARS and not has_code:
            continue
        if any(m in front or m in back for m in _LEAK_MARKERS):
            continue
        norm_front = _normalize(front)
        if norm_front == _normalize(back):
            continue
        if known_tokens is not None:
            cited = {f"{k} {n}" for k, n in re.findall(r"\[(CODE|FIGURE) (\d+)", front + back)}
            if cited - known_tokens:
                continue  # hallucinated asset reference
        # ponytail: O(n²) pairwise dedup — fine for a few hundred cards per deck
        if any(difflib.SequenceMatcher(None, norm_front, f).ratio() >= 0.85 for f in kept_fronts):
            continue
        # explainer must add context beyond the answer, not restate it
        if card.explainer and difflib.SequenceMatcher(
            None, _normalize(card.explainer), _normalize(back)
        ).ratio() >= 0.85:
            card.explainer = ""
        kept_fronts.append(norm_front)
        kept.append(card)
    return kept, len(cards) - len(kept)


_VALIDATION_PROMPT = """You are verifying flashcards against the source material they were generated from.

SOURCE:
{source}

CARDS:
{cards}

For EACH card return one object:
{{"card": <number>, "supported": true/false, "correct": true/false, "fixed_back": ""}}
- "supported": the answer is fully backed by the SOURCE.
- "correct": the answer is factually right as general knowledge.
- If the answer is flawed but fixable from the SOURCE, put the corrected answer in
  "fixed_back" (otherwise leave it "").

Return ONLY a JSON array with one object per card."""


def _validate_cards_llm(client: Any, source: str, cards: list[Flashcard]) -> list[Flashcard]:
    """Second-pass grounding check against the source chunk (issue #6, tier 2).

    Fails open: an unreachable model or unverifiable verdict keeps the card —
    validation must never destroy a deck.
    """
    if not cards:
        return cards
    listing = "\n".join(f"{i}. Q: {c.front}\n   A: {c.back}" for i, c in enumerate(cards, 1))
    try:
        raw = client.generate_json_array(_VALIDATION_PROMPT.format(source=source, cards=listing))
    except Exception as e:
        console.print(f"[yellow]  Validation call failed ({e}) — keeping cards unvalidated[/yellow]")
        return cards

    verdicts: dict[int, dict] = {}
    for v in raw:
        if isinstance(v, dict):
            try:
                verdicts[int(v.get("card"))] = v
            except (TypeError, ValueError):
                continue

    kept: list[Flashcard] = []
    for i, card in enumerate(cards, 1):
        v = verdicts.get(i)
        if v is None:
            kept.append(card)
            continue
        if v.get("correct") is False:
            continue
        fixed = str(v.get("fixed_back") or "").strip()
        if v.get("supported") is False:
            if fixed:
                card.back = fixed
                kept.append(card)
            continue
        if fixed:
            card.back = fixed
        kept.append(card)
    return kept
