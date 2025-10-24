"""Notion API client for fetching page content."""

from typing import Dict, List, Any
from notion_client import Client
from rich.console import Console

console = Console()


class NotionPageFetcher:
    """Fetch and process Notion pages."""

    def __init__(self, notion_token: str):
        """Initialize Notion client."""
        self.client = Client(auth=notion_token)

    def extract_page_id(self, url: str) -> str:
        """Extract page ID from Notion URL.

        Supports formats:
        - https://www.notion.so/Page-Title-abc123def456
        - https://www.notion.so/workspace/Page-Title-abc123def456
        - abc123def456 (direct ID)
        """
        if "notion.so" in url:
            # Extract the last part after the last slash
            page_part = url.rstrip('/').split('/')[-1]
            # The ID is either the whole part or after the last hyphen
            if '-' in page_part:
                page_id = page_part.split('-')[-1]
            else:
                page_id = page_part
        else:
            page_id = url

        # Remove any query parameters
        if '?' in page_id:
            page_id = page_id.split('?')[0]

        # Remove hyphens from the ID
        page_id = page_id.replace('-', '')

        return page_id

    def get_page_content(self, page_url: str) -> Dict[str, Any]:
        """Fetch page content including title and blocks."""
        page_id = self.extract_page_id(page_url)

        console.print(f"[cyan]Fetching page: {page_id}[/cyan]")

        try:
            # Get page metadata (includes title)
            page = self.client.pages.retrieve(page_id)

            # Get page blocks (content)
            blocks = self.get_all_blocks(page_id)

            # Extract title
            title = self.extract_title(page)

            return {
                "id": page_id,
                "title": title,
                "blocks": blocks,
            }

        except Exception as e:
            console.print(f"[red]Error fetching page: {e}[/red]")
            console.print("[yellow]Make sure you've shared the page with your integration![/yellow]")
            raise

    def get_all_blocks(self, block_id: str) -> List[Dict[str, Any]]:
        """Recursively fetch all blocks from a page."""
        all_blocks = []

        try:
            # Fetch blocks with pagination
            has_more = True
            start_cursor = None

            while has_more:
                response = self.client.blocks.children.list(
                    block_id=block_id,
                    start_cursor=start_cursor
                )

                blocks = response.get("results", [])
                all_blocks.extend(blocks)

                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")

            # Recursively fetch child blocks
            for block in all_blocks:
                if block.get("has_children"):
                    child_blocks = self.get_all_blocks(block["id"])
                    block["children"] = child_blocks

        except Exception as e:
            console.print(f"[yellow]Warning: Could not fetch blocks for {block_id}: {e}[/yellow]")

        return all_blocks

    def extract_title(self, page: Dict[str, Any]) -> str:
        """Extract title from page metadata."""
        properties = page.get("properties", {})

        # Try common title property names
        for key in ["title", "Title", "Name"]:
            if key in properties:
                title_prop = properties[key]
                if title_prop.get("type") == "title" and title_prop.get("title"):
                    title_parts = title_prop["title"]
                    if title_parts:
                        return "".join([part.get("plain_text", "") for part in title_parts])

        return "Untitled"
