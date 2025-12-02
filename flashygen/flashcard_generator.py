"""Generate flashcards using AI (Claude or Ollama)."""

import json
from typing import List, Dict
from anthropic import Anthropic
from anthropic.types import TextBlock
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

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
    """Generate flashcards from content using AI (Claude or Ollama)."""

    def __init__(self, api_key: str | None, model: str = "claude-3-5-sonnet-20241022",
                 provider: str = "ollama", ollama_base_url: str = "http://localhost:11434"):
        """Initialize AI client.

        Args:
            api_key: Anthropic API key (only required for Claude provider)
            model: Model name to use
            provider: Either "ollama" or "claude"
            ollama_base_url: Base URL for Ollama server (default: http://localhost:11434)
        """
        self.provider = provider.lower()
        self.model = model
        self.ollama_base_url = ollama_base_url

        if self.provider == "claude":
            if not api_key:
                raise ValueError("API key required for Claude provider")
            self.client = Anthropic(api_key=api_key)
        else:  # ollama
            if not OLLAMA_AVAILABLE:
                raise ImportError("ollama package not installed. Install with: pip install ollama")
            self.client = None  # Ollama uses module-level functions

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
        """Generate flashcards from content using AI."""

        prompt = self._build_prompt(content, title, cards_per_concept)

        provider_name = "Claude" if self.provider == "claude" else "Ollama"
        console.print(f"[cyan]Generating flashcards with {provider_name}...[/cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Thinking...", total=None)

            try:
                if self.provider == "claude":
                    # Use Anthropic Claude
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
                else:
                    # Use Ollama with optimized settings for different models
                    # Configure context window and other options based on model
                    options = {
                        "temperature": 0.7,
                        "num_ctx": 8192,  # Larger context window for complex prompts
                    }

                    # DeepSeek models may need different settings
                    if "deepseek" in self.model.lower():
                        options["num_ctx"] = 16384  # DeepSeek supports larger context
                        console.print(f"[dim]Using extended context window (16K) for DeepSeek model[/dim]")

                    try:
                        response = ollama.chat(
                            model=self.model,
                            messages=[
                                {"role": "user", "content": prompt}
                            ],
                            options=options,
                            format="json"  # Force JSON output only
                        )
                        response_text = response['message']['content']
                    except Exception as ollama_error:
                        console.print(f"[red]Ollama error: {str(ollama_error)}[/red]")
                        console.print(f"[yellow]Model: {self.model}[/yellow]")
                        console.print(f"[yellow]Prompt length: {len(prompt)} chars[/yellow]")
                        raise

                flashcards = self._parse_response(response_text, title)

                console.print(f"[green]Generated {len(flashcards)} flashcards![/green]")
                return flashcards

            except Exception as e:
                console.print(f"[red]Error generating flashcards: {e}[/red]")
                raise

    def _build_prompt(self, content: str, title: str, cards_per_concept: int) -> str:
        """Build the prompt for AI to generate flashcards."""

        # Use different prompts for Claude vs Ollama
        # Ollama models need direct, imperative instructions without conversation
        if self.provider == "ollama":
            return self._build_ollama_prompt(content, title)
        else:
            return self._build_claude_prompt(content, title, cards_per_concept)

    def _build_ollama_prompt(self, content: str, title: str) -> str:
        """Build a direct, imperative prompt optimized for Ollama models."""
        return f"""Generate Anki flashcards from the content below.

CRITICAL INSTRUCTIONS:
1. Return ONLY a JSON array - no explanations, no chat, no extra text
2. Create individual flashcards for EVERY code example - do not skip any
3. Each code snippet gets its own separate flashcard
4. Use the ACTUAL content provided below, NOT the examples in these instructions

JSON FORMAT (use \\n for newlines):
[
  {{
    "front": "Question about the code/concept",
    "back": "Answer with code example using \\n for newlines",
    "type": "command"
  }}
]

Example of correct output for C++ code:
[
  {{
    "front": "What is the syntax for auto type deduction with integers in C++?",
    "back": "```cpp\\nauto x = 42; // compiler deduces int\\n```",
    "type": "command"
  }},
  {{
    "front": "How does auto deduce double types in C++?",
    "back": "```cpp\\nauto y = 3.14; // compiler deduces double\\n```",
    "type": "command"
  }}
]

CONTENT TO PROCESS (from "{title}"):
{content}

RETURN ONLY THE JSON ARRAY - START WITH [ AND END WITH ]"""

    def _build_claude_prompt(self, content: str, title: str, cards_per_concept: int) -> str:
        """Build detailed conversational prompt for Claude."""
        return f"""You are an expert at creating high-quality flashcards for spaced repetition learning (like Anki).

I have content from a Notion page titled "{title}" that I want to convert into flashcards.

Your task is to create a COMPREHENSIVE set of flashcards with MAXIMUM COVERAGE of the material:

1. Treat EVERY code example, command, syntax, function, method, or technique as a SEPARATE learnable item
2. Create flashcards for EACH individual item - don't group multiple items together
3. Your goal is MAXIMUM GRANULARITY - create many small, focused cards rather than few large cards
4. For code-heavy content, you should generate 1-3 cards per code example/command
Card types to use:
   - **Recall**: Direct factual recall ("What is X?", "Define Y")
   - **Conceptual**: Understanding and explanation ("Why does X work?", "Explain how Y relates to Z")
   - **Application**: Practical usage ("When would you use X?", "How would you apply Y?")
   - **Comparison**: Relationships and differences ("How does X differ from Y?", "Compare A and B")
   - **Command**: Practical how-to with exact commands/syntax ("How do you do X?", "What's the syntax for Y?")

CRITICAL Requirements for MAXIMUM COVERAGE:
- **GRANULARITY IS KEY**: Create many small, focused cards rather than few large cards
- **EVERY code example gets AT LEAST one card** - no exceptions!
- **EVERY command/syntax gets its own card** - don't combine multiple items
- Make questions clear, specific, and unambiguous
- Answers MUST include working code examples with proper syntax
- For each code snippet in the content, ask yourself: "What's the syntax?", "What does it do?", "When would you use it?"
- Vary the question types to reinforce learning from different angles

**QUANTITY EXPECTATION:**
- A note with 10 code examples should produce AT LEAST 10-30 flashcards
- A note with 30 code examples should produce AT LEAST 30-100 flashcards
- More cards is better than fewer cards - prioritize comprehensive coverage

**CRITICAL FOR CODE/COMMAND CONTENT:**
When you encounter code snippets or command lists, you MUST create SEPARATE, INDIVIDUAL flashcards for EACH command or code example. DO NOT group multiple commands into a single card.

**EXAMPLES OF PROPER GRANULARITY:**

Example 1 - Git commands (4 commands = 4 cards minimum):
```
git log                       # Full log
git log --oneline            # Compact view
git log --graph --all        # Visual branch graph
git log -n 5                 # Last 5 commits
```
Creates:
- "How do you view the full git commit log?" → "git log"
- "How do you view the git log in compact view?" → "git log --oneline"
- "How do you view a visual branch graph in git?" → "git log --graph --all"
- "How do you view the last 5 commits in git?" → "git log -n 5"

Example 2 - C++ code (3 examples = 3-6 cards):
```cpp
auto x = 42;              // int
auto y = 3.14;            // double
auto str = "hello"s;      // std::string
```
Creates:
- Front: "What is the syntax for auto type deduction with integers in C++?" / Back: "```cpp\nauto x = 42; // compiler deduces int\n```" / Type: "command"
- Front: "How does auto deduce double types in C++?" / Back: "```cpp\nauto y = 3.14; // compiler deduces double\n```" / Type: "command"
- Front: "How do you use auto with std::string literals in C++?" / Back: "```cpp\nauto str = \"hello\"s; // 's' suffix creates std::string\n```" / Type: "command"

DO NOT create a single card that combines all examples. Each distinct example needs its own card!
IMPORTANT: Generate flashcards about the ACTUAL CONTENT provided, not about the examples in this prompt!

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
        """Parse AI response into Flashcard objects."""
        try:
            # Save raw response for debugging
            try:
                with open("debug_response.json", "w", encoding="utf-8") as f:
                    f.write(response)
                console.print(f"[dim]Debug: Saved raw response to debug_response.json ({len(response)} chars)[/dim]")
            except Exception as e:
                console.print(f"[dim]Warning: Could not save debug file: {e}[/dim]")

            # Find JSON in the response
            response = response.strip()

            # Show preview of response for debugging
            preview = response[:200].replace('\n', ' ')
            console.print(f"[dim]Response preview: {preview}...[/dim]")

            # Remove any leading text before the JSON array
            # Sometimes AI adds explanatory text like "Here is the JSON array..."
            if not response.startswith('['):
                # Find the first '[' character
                json_start = response.find('[')
                if json_start != -1:
                    console.print(f"[dim]Found JSON starting at position {json_start}[/dim]")
                    response = response[json_start:]
                else:
                    console.print(f"[yellow]No '[' found in response. First 500 chars:[/yellow]")
                    console.print(f"[yellow]{response[:500]}[/yellow]")
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
