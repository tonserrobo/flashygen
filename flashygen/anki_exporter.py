"""Export flashcards to Anki deck format."""

import random
from pathlib import Path
from typing import List
import genanki
from rich.console import Console

from .flashcard_generator import Flashcard

console = Console()


class AnkiExporter:
    """Export flashcards to Anki .apkg format."""

    def __init__(self):
        """Initialize the Anki exporter."""
        # Create a custom model for our flashcards with styling
        self.model = genanki.Model(
            model_id=random.randrange(1 << 30, 1 << 31),
            name='FlashyGen Basic',
            fields=[
                {'name': 'Question'},
                {'name': 'Answer'},
            ],
            templates=[
                {
                    'name': 'Card 1',
                    'qfmt': '''
                        <div class="card">
                            <div class="question">{{Question}}</div>
                        </div>
                    ''',
                    'afmt': '''
                        <div class="card">
                            <div class="question">{{Question}}</div>
                            <hr>
                            <div class="answer">{{Answer}}</div>
                        </div>
                    ''',
                },
            ],
            css='''
                /* Main card container */
                .card {
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                    font-size: 18px;
                    text-align: center;
                    color: #1a1a1a;
                    background: linear-gradient(135deg, #f5f7fa 0%, #f0f2f5 100%);
                    padding: 30px;
                    line-height: 1.7;
                    max-width: 100%;
                }

                /* Question styling */
                .question {
                    font-size: 22px;
                    font-weight: 600;
                    margin-bottom: 20px;
                    color: #1e3a8a;
                    padding: 20px;
                    background-color: #ffffff;
                    border-radius: 12px;
                    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
                    border-left: 5px solid #3b82f6;
                }

                /* Answer container */
                .answer {
                    font-size: 18px;
                    text-align: left;
                    margin-top: 25px;
                    padding: 25px;
                    background-color: #ffffff;
                    border-radius: 12px;
                    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
                    border-left: 5px solid #10b981;
                }

                /* Divider line */
                hr {
                    border: none;
                    border-top: 2px solid #e5e7eb;
                    margin: 25px 0;
                    opacity: 0.6;
                }

                /* Inline code */
                code {
                    background-color: #f1f5f9;
                    color: #dc2626;
                    padding: 3px 8px;
                    border-radius: 4px;
                    font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Code', 'Consolas', monospace;
                    font-size: 15px;
                    font-weight: 500;
                    border: 1px solid #e2e8f0;
                }

                /* Code block container */
                pre {
                    background-color: #1e293b;
                    color: #e2e8f0;
                    padding: 20px;
                    border-radius: 8px;
                    text-align: left;
                    overflow-x: auto;
                    margin: 15px 0;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2);
                    border: 1px solid #334155;
                    position: relative;
                }

                /* Code block with language badge */
                pre::before {
                    content: attr(data-language);
                    position: absolute;
                    top: 8px;
                    right: 12px;
                    font-size: 11px;
                    color: #94a3b8;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    font-weight: 600;
                }

                pre code {
                    background-color: transparent;
                    color: inherit;
                    padding: 0;
                    border: none;
                    font-size: 14px;
                    line-height: 1.6;
                    display: block;
                }

                /* Syntax highlighting - Comments */
                .comment {
                    color: #6b7280;
                    font-style: italic;
                }

                /* Syntax highlighting - Keywords */
                .keyword {
                    color: #c678dd;
                    font-weight: 600;
                }

                /* Syntax highlighting - Strings */
                .string {
                    color: #98c379;
                }

                /* Syntax highlighting - Numbers */
                .number {
                    color: #d19a66;
                }

                /* Syntax highlighting - Functions */
                .function {
                    color: #61afef;
                }

                /* Syntax highlighting - Operators */
                .operator {
                    color: #56b6c2;
                }

                /* Syntax highlighting - Variables */
                .variable {
                    color: #e06c75;
                }

                /* Strong/Bold text */
                strong, b {
                    color: #1e40af;
                    font-weight: 700;
                }

                /* Italic/Emphasis text */
                em, i {
                    color: #7c3aed;
                    font-style: italic;
                }

                /* Lists */
                ul, ol {
                    text-align: left;
                    padding-left: 25px;
                    margin: 10px 0;
                }

                li {
                    margin: 8px 0;
                    line-height: 1.6;
                }

                /* Blockquotes */
                blockquote {
                    border-left: 4px solid #fbbf24;
                    padding-left: 20px;
                    margin: 15px 0;
                    color: #4b5563;
                    font-style: italic;
                    background-color: #fffbeb;
                    padding: 15px 20px;
                    border-radius: 4px;
                }

                /* Headings in answers */
                h1, h2, h3, h4 {
                    color: #1f2937;
                    margin-top: 20px;
                    margin-bottom: 10px;
                    font-weight: 700;
                }

                h1 { font-size: 24px; }
                h2 { font-size: 21px; }
                h3 { font-size: 18px; }
                h4 { font-size: 16px; }

                /* Links */
                a {
                    color: #2563eb;
                    text-decoration: none;
                    border-bottom: 1px dotted #2563eb;
                }

                a:hover {
                    color: #1d4ed8;
                    border-bottom: 1px solid #1d4ed8;
                }

                /* Mobile responsiveness */
                @media (max-width: 600px) {
                    .card {
                        padding: 20px;
                        font-size: 16px;
                    }

                    .question {
                        font-size: 19px;
                        padding: 15px;
                    }

                    .answer {
                        font-size: 16px;
                        padding: 18px;
                    }

                    pre {
                        padding: 15px;
                        font-size: 13px;
                    }
                }
            '''
        )

    def create_deck(
        self,
        flashcards: List[Flashcard],
        deck_name: str,
        output_path: str = None
    ) -> str:
        """Create an Anki deck from flashcards and save to file."""

        if not flashcards:
            console.print("[yellow]No flashcards to export![/yellow]")
            return None

        # Create deck
        deck_id = random.randrange(1 << 30, 1 << 31)
        deck = genanki.Deck(deck_id, deck_name)

        # Add notes (flashcards) to deck
        for flashcard in flashcards:
            # Convert markdown-like formatting to HTML
            front_html = self._format_content(flashcard.front)
            back_html = self._format_content(flashcard.back)

            # Sanitize tags: replace spaces with hyphens (Anki doesn't allow spaces in tags)
            sanitized_tags = [tag.replace(' ', '-') for tag in flashcard.tags]

            note = genanki.Note(
                model=self.model,
                fields=[front_html, back_html],
                tags=sanitized_tags
            )
            deck.add_note(note)

        # Determine output path (default: decks/ so artifacts stay out of the repo root)
        if output_path is None:
            Path("decks").mkdir(exist_ok=True)
            output_path = str(Path("decks") / f"{deck_name.replace(' ', '_')}.apkg")

        # Ensure the path has .apkg extension
        if not output_path.endswith('.apkg'):
            output_path = f"{output_path}.apkg"

        # Create package and save
        package = genanki.Package(deck)
        package.write_to_file(output_path)

        console.print(f"[green]Successfully created Anki deck: {output_path}[/green]")
        console.print(f"[cyan]Total cards: {len(flashcards)}[/cyan]")

        return output_path

    def _format_content(self, text: str) -> str:
        """Convert markdown-like formatting to HTML for Anki."""
        import re
        import html

        # Store code blocks to protect them from other processing
        code_blocks = []
        # Use HTML comment style placeholder to avoid being mangled by markdown
        # formatting (triple underscores were consumed by bold/italic processing)
        code_block_placeholder = "<!--CODEBLOCK{}-->"

        # Extract and store code blocks
        def store_code_block(match):
            language = match.group(1) or 'code'
            code = match.group(2).strip()

            # Apply syntax highlighting (which includes HTML escaping)
            highlighted_code = self._highlight_code(code, language)

            # Build the pre tag with language attribute for CSS
            html_code = f'<pre data-language="{language}"><code>{highlighted_code}</code></pre>'

            index = len(code_blocks)
            code_blocks.append(html_code)
            return code_block_placeholder.format(index)

        # Extract code blocks first (flexible regex - newline after language is
        # optional). Language class must cover c++, c#, objective-c++ etc. —
        # \w+ alone truncated "c++" to "c" and leaked "++" into the code body.
        text = re.sub(
            r'```([\w+#.-]*)[ \t]*\n?(.*?)\s*```',
            store_code_block,
            text,
            flags=re.DOTALL
        )

        # Convert inline code (`code`) - escape HTML inside
        def format_inline_code(match):
            code_content = html.escape(match.group(1))
            return f'<code>{code_content}</code>'

        text = re.sub(r'`([^`]+)`', format_inline_code, text)

        # Convert bold (**text** or __text__)
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)

        # Convert italic (*text* or _text_) - but not in URLs or after backslashes
        text = re.sub(r'(?<!\\)\*([^*]+?)\*', r'<em>\1</em>', text)
        text = re.sub(r'(?<!\\)_([^_]+?)_', r'<em>\1</em>', text)

        # Convert remaining line breaks to <br> (but not in code blocks)
        text = text.replace('\n', '<br>')

        # Restore code blocks
        for i, code_block in enumerate(code_blocks):
            text = text.replace(code_block_placeholder.format(i), code_block)

        return text

    def _highlight_code(self, code: str, language: str) -> str:
        """Escape code content for safe HTML rendering inside a <pre><code> block."""
        import html

        # Just escape HTML — no regex-based syntax highlighting, which corrupts
        # the output by matching inside its own injected span tags.
        code = html.escape(code)
        code = code.replace('\n', '<br>')
        return code
