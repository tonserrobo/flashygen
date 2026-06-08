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
        - https://app.notion.com/p/Page-Title-abc123def456
        - abc123def456 (direct ID)
        """
        if "notion.so" in url or "notion.com" in url:
            # Strip query string first, then grab the last path segment
            path = url.split('?')[0].rstrip('/')
            page_part = path.split('/')[-1]
            # The slug is Title-HEXID — the ID is the last hyphen-delimited token
            if '-' in page_part:
                page_id = page_part.split('-')[-1]
            else:
                page_id = page_part
        else:
            # Assume bare ID (possibly with hyphens in UUID format)
            page_id = url.split('?')[0]

        # Remove hyphens (UUID format → raw 32-char hex)
        page_id = page_id.replace('-', '')

        return page_id

    def get_page_content(self, page_url: str) -> Dict[str, Any]:
        """Fetch page content including title and blocks."""
        page_id = self.extract_page_id(page_url)

        console.print(f"[cyan]Fetching page ID: {page_id}[/cyan]")

        try:
            # Get page metadata (includes title)
            page = self.client.pages.retrieve(page_id)

            # Get page blocks (content)
            blocks = self.get_all_blocks(page_id)

            # Extract title
            title = self.extract_title(page)

            # Build parent page hierarchy for tag generation
            hierarchy = self.get_page_hierarchy(page_id)
            console.print(f"[dim]Page hierarchy: {' > '.join(hierarchy + [title])}[/dim]")

            return {
                "id": page_id,
                "title": title,
                "blocks": blocks,
                "hierarchy": hierarchy,
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

    def get_page_hierarchy(self, page_id: str) -> List[str]:
        """Walk up the parent page chain to build the hierarchy of page titles.

        Returns a list of titles from top-most ancestor down to (but not including)
        the current page. E.g. for Python > Functions > Type Hinting,
        calling this on "Type Hinting" returns ["Python", "Functions"].
        """
        hierarchy = []
        current_id = page_id

        while True:
            try:
                page = self.client.pages.retrieve(current_id)
            except Exception:
                break

            parent = page.get("parent", {})
            parent_type = parent.get("type")

            if parent_type == "page_id":
                parent_id = parent["page_id"]
                try:
                    parent_page = self.client.pages.retrieve(parent_id)
                    parent_title = self.extract_title(parent_page)
                    hierarchy.append(parent_title)
                    current_id = parent_id
                except Exception:
                    break
            else:
                # Reached workspace or database root — stop
                break

        hierarchy.reverse()
        return hierarchy

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
