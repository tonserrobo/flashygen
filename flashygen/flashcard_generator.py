"""Generate flashcards using Claude AI."""

import json
from typing import List, Dict
from anthropic import Anthropic
from anthropic.types import TextBlock
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


class Flashcard:
    """Represents a single flashcard."""

    def __init__(self, front: str, back: str, tags: List[str] | None = None):
        self.front = front
        self.back = back
        self.tags = tags if tags is not None else []

    def __repr__(self):
        return f"Flashcard(front='{self.front[:50]}...', back='{self.back[:50]}...')"


class FlashcardGenerator:
    """Generate flashcards from content using Claude."""

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        """Initialize Claude client."""
        self.client = Anthropic(api_key=api_key)
        self.model = model

        # Set max_tokens based on model
        if "haiku" in model.lower():
            self.max_tokens = 4096
        else:
            self.max_tokens = 8192

    def generate_flashcards_from_sections(
        self,
        sections: List[Dict[str, str]],
        title: str,
        cards_per_concept: int = 3
    ) -> List[Flashcard]:
        """Generate flashcards from multiple content sections (chunks).

        Args:
            sections: List of dicts with 'heading' and 'content' keys
            title: Overall title for the content
            cards_per_concept: Number of cards to generate per concept

        Returns:
            Combined list of flashcards from all sections
        """
        all_flashcards = []

        console.print(f"[cyan]Processing {len(sections)} section(s)...[/cyan]")

        for i, section in enumerate(sections, 1):
            heading = section.get('heading', f'Section {i}')
            content = section.get('content', '')

            if not content.strip():
                console.print(f"[dim]Skipping empty section: {heading}[/dim]")
                continue

            console.print(f"\n[bold]Section {i}/{len(sections)}:[/bold] {heading}")

            # Generate flashcards for this section
            try:
                section_flashcards = self.generate_flashcards(
                    content,
                    f"{title} - {heading}",
                    cards_per_concept
                )

                # Add section-specific tag
                for card in section_flashcards:
                    if heading:
                        card.tags.append(heading.replace(' ', '-'))

                all_flashcards.extend(section_flashcards)
                console.print(f"[green]✓[/green] Generated {len(section_flashcards)} cards for this section")
            except Exception as e:
                console.print(f"[yellow]⚠[/yellow] Failed to generate cards for this section: {e}")
                console.print("[dim]Continuing with next section...[/dim]")
                continue

        return all_flashcards

    def generate_flashcards(
        self,
        content: str,
        title: str,
        cards_per_concept: int = 3
    ) -> List[Flashcard]:
        """Generate flashcards from content using Claude."""

        prompt = self._build_prompt(content, title, cards_per_concept)

        console.print("[cyan]Generating flashcards with Claude...[/cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Thinking...", total=None)

            try:
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )

                # Extract text from the first content block
                first_block = message.content[0]
                if isinstance(first_block, TextBlock):
                    response_text = first_block.text
                else:
                    raise ValueError(f"Unexpected content block type: {type(first_block)}")

                flashcards = self._parse_response(response_text, title)

                console.print(f"[green]Generated {len(flashcards)} flashcards![/green]")
                return flashcards

            except Exception as e:
                console.print(f"[red]Error generating flashcards: {e}[/red]")
                raise

    def _build_prompt(self, content: str, title: str, cards_per_concept: int) -> str:
        """Build the prompt for Claude to generate flashcards."""
        return f"""You are an expert at creating high-quality flashcards for spaced repetition learning (like Anki).

I have content from a Notion page titled "{title}" that I want to convert into flashcards.

Your task:
1. Identify the key concepts, facts, and ideas in the content
2. For each important concept, create {cards_per_concept} flashcards with DIFFERENT approaches:
   - **Recall**: Direct factual recall ("What is X?", "Define Y")
   - **Conceptual**: Understanding and explanation ("Why does X work?", "Explain how Y relates to Z")
   - **Application**: Practical usage ("When would you use X?", "How would you apply Y?")
   - **Comparison**: Relationships and differences ("How does X differ from Y?", "Compare A and B")
   - **Command**: Practical how-to with exact commands/syntax ("How do you do X?", "What's the command to Y?")

CRITICAL Requirements:
- Make questions clear, specific, and unambiguous
- Answers MUST be detailed and complete - include examples whenever possible
- **ALWAYS include code examples in answers when the content contains code**
- **ALWAYS include concrete examples to illustrate concepts**
- **For technical/tool content: CREATE "command" type cards with exact syntax and usage examples**
- Vary the question types to reinforce learning from different angles
- Focus on understanding, not just memorization
- Avoid redundant questions
- For code-related content: Include syntax examples, show usage patterns, demonstrate with actual code snippets
- For command-type cards: Show the exact command/syntax, explain what it does, and include practical examples
- For conceptual content: Provide real-world examples, analogies, or practical scenarios

Content to process:
{content}

Return your response as a VALID JSON array. Each object should have:
- "front": The question/prompt (plain string)
- "back": The answer WITH EXAMPLES (use \\n for newlines, include code blocks)
- "type": One of "recall", "conceptual", "application", "comparison", "command"

CRITICAL JSON FORMATTING RULES:
- Use \\n (backslash-n) for ALL newlines in the JSON strings
- Use \\t (backslash-t) for indentation in code
- Code blocks should use ```language at the start and ``` at the end
- All special characters must be properly escaped for JSON

Example format with properly formatted CODE (notice the \\n for newlines):
[
  {{
    "front": "How do you define a function in Python?",
    "back": "Use the def keyword followed by function name and parameters:\\n\\n```python\\ndef greet(name):\\n    return f'Hello, {{name}}'\\n\\nresult = greet('Alice')  # Returns 'Hello, Alice!'\\n```",
    "type": "recall"
  }},
  {{
    "front": "What's the difference between append() and extend() in Python lists?",
    "back": "append() adds a single element, extend() adds multiple elements from an iterable:\\n\\n```python\\n# append() - adds whole list as one element\\nlist1 = [1, 2]\\nlist1.append([3, 4])\\nprint(list1)  # [1, 2, [3, 4]]\\n\\n# extend() - adds each element individually\\nlist2 = [1, 2]\\nlist2.extend([3, 4])\\nprint(list2)  # [1, 2, 3, 4]\\n```",
    "type": "comparison"
  }},
  {{
    "front": "When should you use a list comprehension?",
    "back": "Use list comprehensions when creating a new list from an existing iterable - they're more concise and often faster:\\n\\n```python\\n# Traditional loop\\nsquares = []\\nfor x in range(5):\\n    squares.append(x**2)\\n\\n# List comprehension (better)\\nsquares = [x**2 for x in range(5)]\\nprint(squares)  # [0, 1, 4, 9, 16]\\n```\\n\\nAvoid for complex logic that hurts readability.",
    "type": "application"
  }},
  {{
    "front": "How do you set the default branch name in Git during initialization?",
    "back": "Use the git config command to set the default branch name:\\n\\n```bash\\ngit config --global init.defaultBranch main\\n```\\n\\nThis sets 'main' as the default branch name for all new repositories. You can verify with:\\n\\n```bash\\ngit config --global init.defaultBranch\\n```",
    "type": "command"
  }}
]

CRITICAL:
- ALWAYS include code examples in properly formatted code blocks
- Use \\n for newlines (not actual newlines in the JSON)
- Show concrete examples with actual syntax
- Demonstrate output/results when helpful

Return ONLY valid JSON with escaped newlines, no other text."""

    def _parse_response(self, response: str, title: str) -> List[Flashcard]:
        """Parse Claude's response into Flashcard objects."""
        try:
            # Find JSON in the response
            response = response.strip()

            # Remove any leading text before the JSON array
            # Sometimes Claude adds explanatory text like "Here is the JSON array..."
            if not response.startswith('['):
                # Find the first '[' character
                json_start = response.find('[')
                if json_start != -1:
                    response = response[json_start:]
                else:
                    raise ValueError("No JSON array found in response")

            # Remove markdown code blocks if present
            if response.startswith("```"):
                lines = response.split("\n")
                # Remove first and last lines (```)
                response = "\n".join(lines[1:-1])
                # Remove 'json' if it's the language identifier
                if response.startswith("json"):
                    response = response[4:].strip()

            # Check if response looks truncated (doesn't end with ])
            if not response.rstrip().endswith(']'):
                console.print("[yellow]Warning: Response appears truncated, attempting to parse partial JSON...[/yellow]")
                # Try to close the JSON array
                # Find the last complete object
                last_complete = response.rfind('}')
                if last_complete != -1:
                    response = response[:last_complete+1] + '\n]'
                else:
                    raise ValueError("Response is too truncated to parse")

            # Parse JSON with strict=False to allow control characters
            flashcard_data = json.loads(response, strict=False)

            flashcards = []
            for item in flashcard_data:
                front = item.get("front", "").strip()
                back = item.get("back", "").strip()
                card_type = item.get("type", "recall")

                if front and back:
                    tags = [title, card_type]
                    flashcards.append(Flashcard(front, back, tags))

            return flashcards

        except json.JSONDecodeError as e:
            console.print(f"[red]Error parsing JSON response: {e}[/red]")
            console.print(f"[yellow]Response was: {response[:500]}...[/yellow]")

            # Try to save the full response for debugging
            try:
                with open("debug_response.json", "w", encoding="utf-8") as f:
                    f.write(response)
                console.print(f"[yellow]Full response saved to debug_response.json[/yellow]")
            except:
                pass

            raise
        except Exception as e:
            console.print(f"[red]Error parsing flashcards: {e}[/red]")
            raise
