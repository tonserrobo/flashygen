# FlashyGen Quick Start Guide

## Setup (5 minutes)

### 1. Create `.env` file with your API keys:

```bash
cp .env.example .env
```

Then edit `.env` and add:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
NOTION_TOKEN=secret_your-notion-token-here
```

**Get API Keys:**

- Anthropic: https://console.anthropic.com
- Notion: https://www.notion.so/my-integrations

### 2. Share your Notion page with the integration:

1. Open your Notion page
2. Click "..." menu (top right)
3. Click "Add connections"
4. Select your integration
5. Click "Confirm"

## Usage

### Generate flashcards from a Notion page:

```bash
uv run python main.py generate https://www.notion.so/your-page-url
```

### With custom options:

```bash
# Custom output file and more cards
uv run python main.py generate <url> -o my-deck.apkg -c 5

# Custom deck name
uv run python main.py generate <url> -d "My Study Deck"
```

### Import into Anki:

1. Open Anki
2. File → Import
3. Select the generated `.apkg` file
4. Start studying!

## Tips

- Start with pages that have clear concepts and definitions
- The default 3 cards per concept works well for most content
- Use meaningful page titles in Notion - they become your deck names
- Code blocks and formatting are preserved in the flashcards

## Troubleshooting

**"Configuration error"**: Check your `.env` file has both API keys

**"Could not find page"**: Make sure you shared the page with your integration

**Run setup guide**: `uv run python main.py setup`

## Need Help?

See the full [README.md](README.md) for detailed documentation.
