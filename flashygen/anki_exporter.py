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

            note = genanki.Note(
                model=self.model,
                fields=[front_html, back_html],
                tags=flashcard.tags
            )
            deck.add_note(note)

        # Determine output path
        if output_path is None:
            output_path = f"{deck_name.replace(' ', '_')}.apkg"

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

        # First, protect code blocks from line break conversion
        # Convert code blocks (```language\ncode\n``` or just ```\ncode\n```)
        def format_code_block(match):
            language = match.group(1) or 'code'
            code = match.group(2).strip()

            # Apply syntax highlighting
            highlighted_code = self._highlight_code(code, language)

            # Build the pre tag with language attribute for CSS
            return f'<pre data-language="{language}"><code>{highlighted_code}</code></pre>'

        text = re.sub(
            r'```(\w+)?\s*\n(.*?)```',
            format_code_block,
            text,
            flags=re.DOTALL
        )

        # Convert inline code (`code`)
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

        # Convert bold (**text** or __text__)
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)

        # Convert italic (*text* or _text_) - but not in URLs or after backslashes
        text = re.sub(r'(?<!\\)\*([^*]+?)\*', r'<em>\1</em>', text)
        text = re.sub(r'(?<!\\)_([^_]+?)_', r'<em>\1</em>', text)

        # Convert remaining line breaks to <br>
        text = text.replace('\n', '<br>')

        return text

    def _highlight_code(self, code: str, language: str) -> str:
        """Apply syntax highlighting to code blocks for multiple languages."""
        import re
        import html

        # Escape HTML first
        code = html.escape(code)

        # Define common keywords for various languages
        keywords_map = {
            'python': r'\b(def|class|import|from|as|if|elif|else|for|while|in|return|try|except|finally|with|lambda|yield|async|await|pass|break|continue|raise|assert|global|nonlocal|and|or|not|is|True|False|None)\b',
            'javascript': r'\b(function|const|let|var|if|else|for|while|return|class|extends|import|export|from|as|async|await|try|catch|finally|throw|new|this|super|static|yield|break|continue|switch|case|default|typeof|instanceof|in|of|delete|void|true|false|null|undefined)\b',
            'typescript': r'\b(function|const|let|var|if|else|for|while|return|class|extends|implements|import|export|from|as|async|await|try|catch|finally|throw|new|this|super|static|yield|break|continue|switch|case|default|typeof|instanceof|in|of|delete|void|true|false|null|undefined|interface|type|enum|namespace|abstract|readonly|public|private|protected)\b',
            'java': r'\b(public|private|protected|class|interface|extends|implements|new|return|if|else|for|while|do|switch|case|default|break|continue|try|catch|finally|throw|throws|import|package|static|final|abstract|synchronized|volatile|transient|native|strictfp|void|boolean|byte|char|short|int|long|float|double|true|false|null|this|super)\b',
            'c': r'\b(int|char|float|double|void|struct|union|enum|typedef|sizeof|if|else|for|while|do|switch|case|default|break|continue|return|goto|auto|register|static|extern|const|volatile|signed|unsigned|short|long)\b',
            'cpp': r'\b(int|char|float|double|void|bool|struct|class|union|enum|typedef|namespace|using|template|typename|public|private|protected|virtual|override|final|static|const|volatile|mutable|if|else|for|while|do|switch|case|default|break|continue|return|try|catch|throw|new|delete|this|nullptr|true|false)\b',
            'go': r'\b(package|import|func|var|const|type|struct|interface|map|chan|if|else|for|range|switch|case|default|break|continue|return|defer|go|select|fallthrough|goto|true|false|nil|make|new|len|cap|append|copy|delete|panic|recover)\b',
            'rust': r'\b(fn|let|mut|const|static|struct|enum|impl|trait|type|mod|use|pub|crate|super|self|if|else|match|loop|while|for|in|break|continue|return|move|ref|as|unsafe|async|await|dyn|true|false|Some|None|Ok|Err)\b',
            'ruby': r'\b(def|class|module|if|elsif|else|unless|case|when|for|while|until|loop|break|next|return|yield|begin|rescue|ensure|end|do|then|and|or|not|true|false|nil|self|super|include|extend|require|attr_accessor|attr_reader|attr_writer)\b',
            'php': r'\b(function|class|interface|trait|extends|implements|new|return|if|else|elseif|for|foreach|while|do|switch|case|default|break|continue|try|catch|finally|throw|public|private|protected|static|final|abstract|const|var|echo|print|require|include|namespace|use|as|true|false|null|this|self|parent)\b',
            'sql': r'\b(SELECT|FROM|WHERE|JOIN|INNER|LEFT|RIGHT|OUTER|ON|GROUP|BY|ORDER|ASC|DESC|HAVING|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|TABLE|DATABASE|INDEX|ALTER|DROP|TRUNCATE|UNION|ALL|DISTINCT|AS|AND|OR|NOT|IN|BETWEEN|LIKE|IS|NULL|TRUE|FALSE)\b',
            'shell': r'\b(if|then|else|elif|fi|case|esac|for|while|until|do|done|function|return|exit|break|continue|echo|printf|read|cd|ls|mkdir|rm|cp|mv|grep|sed|awk|sudo|chmod|chown|export|source|alias)\b',
            'bash': r'\b(if|then|else|elif|fi|case|esac|for|while|until|do|done|function|return|exit|break|continue|echo|printf|read|cd|ls|mkdir|rm|cp|mv|grep|sed|awk|sudo|chmod|chown|export|source|alias)\b',
        }

        # Get keyword pattern for this language (default to python if unknown)
        keyword_pattern = keywords_map.get(language.lower(), keywords_map.get('python', ''))

        # Highlight comments (various styles)
        # Single-line comments: //, #, --
        code = re.sub(r'(//[^\n]*)', r'<span class="comment">\1</span>', code)
        code = re.sub(r'(#[^\n]*)', r'<span class="comment">\1</span>', code)
        code = re.sub(r'(--[^\n]*)', r'<span class="comment">\1</span>', code)

        # Multi-line comments: /* */, """ """, ''' '''
        code = re.sub(r'(/\*.*?\*/)', r'<span class="comment">\1</span>', code, flags=re.DOTALL)
        code = re.sub(r'(""".*?""")', r'<span class="comment">\1</span>', code, flags=re.DOTALL)
        code = re.sub(r"('''.*?''')", r'<span class="comment">\1</span>', code, flags=re.DOTALL)

        # Highlight strings (before keywords to avoid highlighting keywords in strings)
        # Double quotes
        code = re.sub(r'(?<!class=)("(?:[^"\\]|\\.)*")', r'<span class="string">\1</span>', code)
        # Single quotes
        code = re.sub(r"(?<!class=)('(?:[^'\\]|\\.)*')", r'<span class="string">\1</span>', code)
        # Backticks (for template literals)
        code = re.sub(r'(`(?:[^`\\]|\\.)*`)', r'<span class="string">\1</span>', code)

        # Highlight keywords
        if keyword_pattern:
            code = re.sub(keyword_pattern, r'<span class="keyword">\1</span>', code)

        # Highlight numbers
        code = re.sub(r'\b(\d+\.?\d*)\b', r'<span class="number">\1</span>', code)

        # Highlight function calls (word followed by parenthesis)
        code = re.sub(r'\b([a-zA-Z_]\w*)\s*(?=\()', r'<span class="function">\1</span>', code)

        # Highlight operators (be careful not to double-wrap already highlighted code)
        # Skip this step if it causes issues with nested spans
        # The simpler highlighting above is sufficient for most use cases

        # Convert line breaks to <br>
        code = code.replace('\n', '<br>')

        return code
