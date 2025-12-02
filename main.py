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

app = typer.Typer(help="Generate Anki flashcards from Notion pages using AI")
console = Console()


@app.command()
def generate(
    page_url: str = typer.Argument(..., help="Notion page URL or page ID"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path (default: page_title.apkg)"),
    cards_per_concept: int = typer.Option(3, "--cards", "-c", help="Number of cards per concept"),
    deck_name: str = typer.Option(None, "--deck-name", "-d", help="Custom deck name (default: page title)"),
    provider: str = typer.Option("ollama", "--provider", "-p", help="AI provider: 'ollama' (default) or 'claude'"),
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
        # Step 1: Fetch Notion page
        console.print("\n[bold]Step 1:[/bold] Fetching Notion page content...")
        notion_fetcher = NotionPageFetcher(config.notion_token)
        page_data = notion_fetcher.get_page_content(page_url)

        console.print(f"[green]✓[/green] Page retrieved: [bold]{page_data['title']}[/bold]")
        console.print(f"[dim]Found {len(page_data['blocks'])} blocks[/dim]")

        # Step 2: Parse content
        console.print("\n[bold]Step 2:[/bold] Parsing page content...")
        parser = NotionContentParser()
        content = parser.parse_blocks(page_data['blocks'])

        if not content.strip():
            console.print("[red]Error: No content found in the page![/red]")
            raise typer.Exit(1)

        console.print(f"[green]✓[/green] Parsed {len(content)} characters of content")

        # Extract sections for chunked processing
        # Start with H1 only to avoid over-fragmentation
        sections = parser.extract_content_sections(content, max_heading_level=1)
        console.print(f"[dim]Detected {len(sections)} raw section(s) (H1 level)[/dim]")

        # If too few sections (regardless of content size), try H1+H2 for better granularity
        if len(sections) < 3:
            console.print("[dim]Too few sections, trying H1+H2 split for better coverage...[/dim]")
            sections_h2 = parser.extract_content_sections(content, max_heading_level=2)
            # Only use H2 split if it gives us more sections
            if len(sections_h2) > len(sections):
                sections = sections_h2
                console.print(f"[dim]Detected {len(sections)} raw section(s) (H1+H2 level)[/dim]")
            else:
                console.print(f"[dim]No improvement with H2 split, keeping {len(sections)} section(s)[/dim]")

        # Merge small sections to avoid over-fragmentation
        if len(sections) > 20:
            console.print(f"[yellow]Warning: {len(sections)} sections is too many. Merging sections...[/yellow]")
            sections = parser.merge_small_sections(sections, min_content_size=800, max_sections=20)
            console.print(f"[dim]Merged down to {len(sections)} section(s)[/dim]")

        # For Claude Haiku, split large sections to avoid token limit truncation
        if config.provider == "claude" and "haiku" in config.model.lower():
            console.print("[dim]Using Haiku - splitting large sections to avoid truncation...[/dim]")
            sections_before = len(sections)
            sections = parser.split_large_sections(sections, max_section_size=2500)
            if len(sections) > sections_before:
                console.print(f"[dim]Split into {len(sections)} smaller section(s) for better coverage[/dim]")

        # Step 3: Generate flashcards with AI
        provider_display = "Claude" if config.provider == "claude" else "Ollama"
        console.print(f"\n[bold]Step 3:[/bold] Generating flashcards with {provider_display} (target: {cards_per_concept} per concept)...")
        generator = FlashcardGenerator(
            config.anthropic_api_key,
            config.model,
            provider=config.provider,
            ollama_base_url=config.ollama_base_url
        )

        # Use chunked processing for better coverage of large notes
        flashcards = generator.generate_flashcards_from_sections(
            sections,
            page_data['title'],
            cards_per_concept
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
            card_type = card.tags[-1] if len(card.tags) > 1 else "unknown"
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
            output
        )

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
