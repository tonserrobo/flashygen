#!/usr/bin/env python3
"""FlashyGen CLI - Generate flashcards from Notion pages."""

import typer
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from flashygen.config import get_config
from flashygen.notion_client import NotionPageFetcher
from flashygen.content_parser import NotionContentParser
from flashygen.flashcard_generator import FlashcardGenerator
from flashygen.anki_exporter import AnkiExporter
from flashygen import manifest as mf

app = typer.Typer(help="Generate Anki flashcards from Notion pages using AI")
console = Console()


def _fetch_and_section(notion_token: str, page_url: str):
    """Fetch a Notion page and run the parse + sectioning pipeline."""
    console.print("\n[bold]Step 1:[/bold] Fetching Notion page content...")
    notion_fetcher = NotionPageFetcher(notion_token)
    page_data = notion_fetcher.get_page_content(page_url)

    console.print(f"[green]✓[/green] Page retrieved: [bold]{page_data['title']}[/bold]")
    console.print(f"[dim]Found {len(page_data['blocks'])} blocks[/dim]")

    console.print("\n[bold]Step 2:[/bold] Parsing page content...")
    parser = NotionContentParser()
    content = parser.parse_blocks(page_data['blocks'])

    if not content.strip():
        console.print("[red]Error: No content found in the page![/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Parsed {len(content)} characters of content")
    if parser.skipped_types:
        console.print(f"[yellow]⚠ Unhandled block types dropped: {', '.join(sorted(parser.skipped_types))}[/yellow]")

    # Start with H1 only to avoid over-fragmentation
    sections = parser.extract_content_sections(content, max_heading_level=1)
    console.print(f"[dim]Detected {len(sections)} raw section(s) (H1 level)[/dim]")

    if len(sections) < 3:
        sections_h2 = parser.extract_content_sections(content, max_heading_level=2)
        if len(sections_h2) > len(sections):
            sections = sections_h2
            console.print(f"[dim]Using H1+H2 split: {len(sections)} section(s)[/dim]")

    if len(sections) > 20:
        console.print(f"[yellow]Warning: {len(sections)} sections is too many. Merging sections...[/yellow]")
        sections = parser.merge_small_sections(sections, min_content_size=800, max_sections=10)
        console.print(f"[dim]Merged down to {len(sections)} section(s)[/dim]")

    # Split large sections so each fits comfortably in a small model's context
    sections = parser.split_large_sections(sections, max_section_size=1200)
    console.print(f"[dim]After size-capping: {len(sections)} section(s)[/dim]")

    return page_data, parser, sections


def _default_manifest_path(title: str) -> str:
    return str(Path("decks") / f"{title.replace(' ', '_')}.manifest.json")


def _print_coverage(cov: dict):
    console.print(f"\n[bold]Coverage:[/bold] {cov['covered']}/{cov['total']} sections have cards")
    for heading in cov["uncovered"]:
        console.print(f"  [yellow]uncovered section:[/yellow] {heading}")
    for token in cov["uncited_assets"]:
        console.print(f"  [yellow]uncited asset:[/yellow] [{token}]")


@app.command()
def generate(
    page_url: str = typer.Argument(..., help="Notion page URL or page ID"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path (default: page_title.apkg)"),
    cards_per_concept: int = typer.Option(3, "--cards", "-c", help="Number of cards per concept"),
    deck_name: str = typer.Option(None, "--deck-name", "-d", help="Custom deck name (default: page title)"),
    provider: str = typer.Option("ollama", "--provider", "-p", help="AI provider: 'ollama' (default) or 'claude'"),
    validate: bool = typer.Option(True, "--validate/--no-validate", help="LLM validation pass on generated cards (Ollama only)"),
):
    """Generate flashcards from a Notion page."""

    console.print(Panel.fit(
        "[bold cyan]FlashyGen[/bold cyan] - Notion to Anki Flashcard Generator",
        border_style="cyan"
    ))

    # Load configuration
    config = get_config(provider)
    valid, message = config.validate()

    if not valid:
        console.print(f"[red]Configuration error: {message}[/red]")
        console.print("[yellow]Please check your .env file. See .env.example for reference.[/yellow]")
        raise typer.Exit(1)

    # Show which provider is being used
    provider_name = "Claude" if config.provider == "claude" else f"Ollama ({config.model})"
    console.print(f"[dim]Using AI provider: {provider_name}[/dim]")

    try:
        page_data, parser, sections = _fetch_and_section(config.notion_token, page_url)

        # Step 3: Generate flashcards with AI
        provider_display = "Claude" if config.provider == "claude" else "Ollama"
        console.print(f"\n[bold]Step 3:[/bold] Generating flashcards with {provider_display} (target: {cards_per_concept} per concept)...")
        generator = FlashcardGenerator(
            config.anthropic_api_key,
            config.model,
            provider=config.provider,
            ollama_base_url=config.ollama_base_url,
            validate=validate
        )

        # Chunked processing with per-section disk checkpoints (resumable runs)
        flashcards = generator.generate_flashcards_from_sections(
            sections,
            page_data['title'],
            cards_per_concept,
            hierarchy=page_data.get('hierarchy', []),
            assets=parser.assets,
            work_dir=str(Path("decks") / ".work" / page_data['id'])
        )

        if not flashcards:
            console.print("[red]Error: No flashcards were generated![/red]")
            raise typer.Exit(1)

        console.print(f"[green]✓[/green] Generated {len(flashcards)} flashcards")

        # Show flashcard preview
        console.print("\n[bold]Flashcard Preview:[/bold]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Type", style="cyan")
        table.add_column("Front", style="white")
        table.add_column("Back", style="green")

        # Show first 3 flashcards
        for card in flashcards[:3]:
            card_type = card.card_type
            front_preview = card.front[:50] + "..." if len(card.front) > 50 else card.front
            back_preview = card.back[:50] + "..." if len(card.back) > 50 else card.back
            table.add_row(card_type, front_preview, back_preview)

        if len(flashcards) > 3:
            table.add_row("...", "...", "...")

        console.print(table)

        # Step 4: Export to Anki
        console.print(f"\n[bold]Step 4:[/bold] Creating Anki deck...")
        exporter = AnkiExporter()

        # Use custom deck name or page title
        final_deck_name = deck_name or page_data['title']

        output_file = exporter.create_deck(
            flashcards,
            final_deck_name,
            output,
            assets=parser.assets,
            page_id=page_data['id']
        )

        # Write the card manifest next to the deck and report coverage
        deck_manifest = mf.build_manifest(
            page_data['id'], page_data['title'], sections, flashcards, parser.assets
        )
        manifest_file = mf.write_manifest(deck_manifest, output_file)
        console.print(f"[dim]Manifest: {manifest_file}[/dim]")
        _print_coverage(mf.coverage(deck_manifest))

        # Final success message
        console.print(Panel.fit(
            f"[bold green]Success![/bold green]\n\n"
            f"Created: [cyan]{output_file}[/cyan]\n"
            f"Cards: [yellow]{len(flashcards)}[/yellow]\n"
            f"Deck: [magenta]{final_deck_name}[/magenta]\n\n"
            f"Import this file into Anki to start learning!",
            border_style="green",
            title="✓ Flashcards Generated"
        ))

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def check(
    page_url: str = typer.Argument(..., help="Notion page URL or page ID"),
    manifest_path: str = typer.Option(None, "--manifest", "-m", help="Deck manifest (default: decks/<title>.manifest.json)"),
):
    """Compare an existing deck's manifest against the current Notion note.

    Reports new sections, changed sections (stale cards), sections with no
    cards, and registered assets no card cites. No LLM calls.
    """
    config = get_config("ollama")
    if not config.notion_token:
        console.print("[red]NOTION_TOKEN not found in .env file[/red]")
        raise typer.Exit(1)

    page_data, parser, sections = _fetch_and_section(config.notion_token, page_url)
    manifest_path = manifest_path or _default_manifest_path(page_data['title'])
    if not Path(manifest_path).exists():
        console.print(f"[red]No manifest at {manifest_path} — generate the deck first.[/red]")
        raise typer.Exit(1)

    diff = mf.diff_sections(mf.load_manifest(manifest_path), sections)

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Status", style="cyan")
    table.add_column("Section", style="white")
    for heading in diff["new"]:
        table.add_row("new", heading)
    for heading in diff["changed"]:
        table.add_row("changed", heading)
    for heading in diff["uncovered"]:
        table.add_row("no cards", heading)
    for token in diff["uncited_assets"]:
        table.add_row("uncited asset", f"[{token}]")
    console.print(table)

    gaps = len(diff["new"]) + len(diff["changed"]) + len(diff["uncovered"])
    if gaps:
        console.print(f"[yellow]{gaps} section(s) need attention — run: python main.py update {page_url}[/yellow]")
        raise typer.Exit(1)
    console.print("[green]Deck is up to date with the note.[/green]")


@app.command()
def update(
    page_url: str = typer.Argument(..., help="Notion page URL or page ID"),
    manifest_path: str = typer.Option(None, "--manifest", "-m", help="Deck manifest (default: decks/<title>.manifest.json)"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
    deck_name: str = typer.Option(None, "--deck-name", "-d", help="Custom deck name (default: page title)"),
    provider: str = typer.Option("ollama", "--provider", "-p", help="AI provider: 'ollama' (default) or 'claude'"),
    validate: bool = typer.Option(True, "--validate/--no-validate", help="LLM validation pass on generated cards (Ollama only)"),
):
    """Regenerate cards only for new/changed/uncovered sections, keep the rest.

    Deterministic note ids mean re-importing the deck updates existing cards
    in Anki (review history preserved) and adds only the new ones.
    """
    config = get_config(provider)
    valid, message = config.validate()
    if not valid:
        console.print(f"[red]Configuration error: {message}[/red]")
        raise typer.Exit(1)

    try:
        page_data, parser, sections = _fetch_and_section(config.notion_token, page_url)
        manifest_path = manifest_path or _default_manifest_path(page_data['title'])
        if not Path(manifest_path).exists():
            console.print(f"[red]No manifest at {manifest_path} — generate the deck first.[/red]")
            raise typer.Exit(1)
        old_manifest = mf.load_manifest(manifest_path)

        diff = mf.diff_sections(old_manifest, sections)
        targets = set(diff["new"] + diff["changed"] + diff["uncovered"])
        if not targets:
            console.print("[green]Deck is already up to date with the note.[/green]")
            return

        console.print(f"[cyan]Regenerating {len(targets)} section(s): {', '.join(sorted(targets))}[/cyan]")
        generator = FlashcardGenerator(
            config.anthropic_api_key,
            config.model,
            provider=config.provider,
            ollama_base_url=config.ollama_base_url,
            validate=validate
        )
        new_cards = generator.generate_flashcards_from_sections(
            [s for s in sections if s["heading"] in targets],
            page_data['title'],
            hierarchy=page_data.get('hierarchy', []),
            assets=parser.assets
        )

        kept_cards = [
            mf.card_from_dict(c)
            for s in old_manifest["sections"] if s["heading"] not in targets
            for c in s["cards"]
        ]
        flashcards = kept_cards + new_cards
        console.print(f"[green]✓[/green] {len(kept_cards)} kept + {len(new_cards)} regenerated")

        output_file = AnkiExporter().create_deck(
            flashcards,
            deck_name or page_data['title'],
            output,
            assets=parser.assets,
            page_id=page_data['id']
        )
        new_manifest = mf.build_manifest(
            page_data['id'], page_data['title'], sections, flashcards, parser.assets
        )
        mf.write_manifest(new_manifest, output_file)
        _print_coverage(mf.coverage(new_manifest))
        console.print("[green]Re-import the deck in Anki — existing cards update in place.[/green]")

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def setup():
    """Show setup instructions for API keys and Notion integration."""

    console.print(Panel.fit(
        "[bold cyan]FlashyGen Setup Guide[/bold cyan]",
        border_style="cyan"
    ))

    console.print("\n[bold]1. Get your Anthropic API Key[/bold]")
    console.print("   • Visit: https://console.anthropic.com")
    console.print("   • Sign up or log in")
    console.print("   • Create an API key")
    console.print("   • Add billing information (pay-as-you-go)")

    console.print("\n[bold]2. Create a Notion Integration[/bold]")
    console.print("   • Visit: https://www.notion.so/my-integrations")
    console.print("   • Click 'New integration'")
    console.print("   • Give it a name (e.g., 'FlashyGen')")
    console.print("   • Copy the 'Internal Integration Token'")

    console.print("\n[bold]3. Share pages with your integration[/bold]")
    console.print("   • Open a Notion page you want to use")
    console.print("   • Click '...' menu -> 'Add connections'")
    console.print("   • Select your integration")
    console.print("   • Repeat for each page you want to access")

    console.print("\n[bold]4. Configure FlashyGen[/bold]")

    env_path = Path(".env")
    if env_path.exists():
        console.print(f"   • [green]Found .env file[/green]")
        console.print(f"   • Edit: {env_path.absolute()}")
    else:
        console.print(f"   • [yellow]Create a .env file[/yellow]")
        console.print(f"   • Copy from: .env.example")

    console.print("\n[bold]5. Test your setup[/bold]")
    console.print("   • Run: [cyan]python main.py generate <notion-page-url>[/cyan]")

    console.print("\n[dim]Need help? Check the README.md file[/dim]")


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
