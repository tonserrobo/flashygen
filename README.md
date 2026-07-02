# FlashyGen

Generate Anki flashcards from Notion pages using AI.

Automatically creates diverse flashcards with proper syntax highlighting for code examples, supporting both local (Ollama) and cloud (Claude) AI providers.

## Features

- AI-powered flashcard generation (Ollama or Claude)
- Multiple question types: recall, conceptual, application, comparison, command, troubleshoot
- Cloze cards over code blocks, generated alongside Q/A cards
- Asset-aware cards: figures from the note are embedded in the deck, code blocks land byte-exact on cards (the model cites `[CODE n]`/`[FIGURE n]` tokens; it never retypes code)
- Explainer section below each answer — context beyond the recalled fact
- Quality gate + LLM validation pass: thin, duplicated, ungrounded, or hallucinated cards are dropped before export
- Coverage manifest next to every deck; `check` and `update` commands diff a deck against the current note and regenerate only what changed
- Resumable generation: per-section checkpoints in `decks/.work/` — interrupted runs don't repeat LLM calls
- Deterministic deck/note IDs — re-importing an updated deck merges in Anki and preserves review history
- Equations rendered via Anki MathJax; tables carried through as markdown
- Works with private Notion pages; clean, styled decks ready to import

## Installation

```bash
git clone https://github.com/yourusername/flashygen.git
cd flashygen
uv sync  # or: pip install -r requirements.txt
```

## Quick Setup

1. **Choose AI Provider**
   - Ollama (free, local): Install from [ollama.ai](https://ollama.ai), run `ollama pull phi3`
   - Claude (paid): Get API key from [console.anthropic.com](https://console.anthropic.com)

2. **Create Notion Integration**
   - Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
   - Create new integration, copy the token

3. **Configure**
   ```bash
   cp .env.example .env
   # Edit .env and add your tokens
   ```

4. **Share Notion Pages**
   - Open your Notion page → "..." menu → "Add connections" → Select your integration

For detailed setup help, run:
```bash
python main.py setup
```

## Usage

**Generate a deck:**
```bash
python main.py generate https://www.notion.so/your-page-url
```
Writes `decks/<title>.apkg` plus `decks/<title>.manifest.json` (card provenance), and prints a coverage summary of any note sections that produced no cards.

**Check a deck against the current note (no LLM calls):**
```bash
python main.py check <url>
```
Reports new sections, changed sections (stale cards), sections with no cards, and figures/code blocks no card cites. Exits 1 when gaps exist, so it can run on a schedule.

**Update a deck incrementally:**
```bash
python main.py update <url>
```
Regenerates cards only for new/changed/uncovered sections, keeps everything else from the manifest, and re-exports. Re-import in Anki: existing cards update in place, review history intact.

**Options (generate/update):**
```bash
--provider, -p               # AI provider: "ollama" (default) or "claude"
--output, -o                 # Output file path (default: decks/<page_title>.apkg)
--cards, -c                  # Cards per concept (default: 3, generate only)
--deck-name, -d              # Custom deck name (default: page title)
--validate / --no-validate   # LLM grounding pass on generated cards (default: on)
--manifest, -m               # Manifest path (check/update; default: decks/<title>.manifest.json)
```

**Examples:**
```bash
# Use Claude instead of Ollama
python main.py generate <url> -p claude

# Faster generation without the validation pass
python main.py generate <url> --no-validate

# All options
python main.py generate <url> -p claude -o deck.apkg -c 4 -d "Python Study"
```

## Troubleshooting

**"Configuration error: ANTHROPIC_API_KEY not found"**
- Create `.env` file and add your API key without quotes

**"Error fetching page: Could not find page"**
- Share the Notion page with your integration (see setup step 4)

**"No flashcards were generated"**
- Page may be empty or have insufficient content

**Generated .apkg file not working**
- Install Anki, then double-click .apkg or import via File → Import

**Duplicate decks after upgrading to 0.2.0**
- Deck IDs became deterministic in 0.2.0; delete decks imported with older versions from Anki once, then re-import — subsequent updates merge cleanly

**A run was interrupted mid-generation**
- Just re-run the same command: sections already generated are resumed from `decks/.work/<page_id>/` checkpoints without new LLM calls

## License

MIT License - see LICENSE file for details
