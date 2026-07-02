"""Parse Notion blocks into structured content for flashcard generation."""

from typing import Dict, List, Any


def chunk_text(content: str, max_chars: int) -> List[str]:
    """Group lines into chunks of ~max_chars without ever splitting a ``` fence.

    A fenced code block is an atomic unit and always joins the current chunk,
    so a block stays with the prose that introduces it — a chunk may overflow
    max_chars to guarantee that. Blank lines are dropped outside fences and
    preserved inside them.
    """
    units: List[tuple] = []  # (text, is_fenced_block)
    fence_buf = None
    for line in content.split("\n"):
        if fence_buf is not None:
            fence_buf.append(line)
            if line.lstrip().startswith("```"):
                units.append(("\n".join(fence_buf), True))
                fence_buf = None
        elif line.lstrip().startswith("```"):
            fence_buf = [line]
        elif line.strip():
            units.append((line, False))
    if fence_buf is not None:  # unterminated fence — keep it whole anyway
        units.append(("\n".join(fence_buf), True))

    chunks: List[str] = []
    current: List[str] = []
    size = 0
    for text, is_fence in units:
        unit_len = len(text) + 1
        if current and size + unit_len > max_chars and not is_fence:
            chunks.append("\n".join(current))
            current, size = [], 0
        current.append(text)
        size += unit_len
    if current:
        chunks.append("\n".join(current))
    return chunks


class NotionContentParser:
    """Parse Notion blocks into readable text.

    While parsing, code blocks and images are recorded in `self.assets` and
    referenced in the text by [CODE n] / [FIGURE n] tokens, so downstream
    stages can cite assets instead of reproducing them (issue #8).
    """

    def __init__(self):
        self.assets: List[Dict[str, str]] = []
        self.skipped_types: set = set()

    def parse_blocks(self, blocks: List[Dict[str, Any]], level: int = 0) -> str:
        """Parse blocks into formatted text."""
        if level == 0:
            self.assets = []
            self.skipped_types = set()
        content_parts = []

        for block in blocks:
            block_type = block.get("type")
            block_content = self.parse_block(block, block_type, level)

            if block_content:
                content_parts.append(block_content)

            # Parse children if they exist
            if "children" in block and block["children"]:
                child_content = self.parse_blocks(block["children"], level + 1)
                if child_content:
                    content_parts.append(child_content)

        return "\n\n".join(content_parts)

    def parse_block(self, block: Dict[str, Any], block_type: str, level: int) -> str:
        """Parse a single block based on its type."""
        if block_type == "paragraph":
            return self.parse_rich_text(block["paragraph"].get("rich_text", []))

        elif block_type == "heading_1":
            text = self.parse_rich_text(block["heading_1"].get("rich_text", []))
            return f"# {text}" if text else ""

        elif block_type == "heading_2":
            text = self.parse_rich_text(block["heading_2"].get("rich_text", []))
            return f"## {text}" if text else ""

        elif block_type == "heading_3":
            text = self.parse_rich_text(block["heading_3"].get("rich_text", []))
            return f"### {text}" if text else ""

        elif block_type == "bulleted_list_item":
            text = self.parse_rich_text(block["bulleted_list_item"].get("rich_text", []))
            indent = "  " * level
            return f"{indent}- {text}" if text else ""

        elif block_type == "numbered_list_item":
            text = self.parse_rich_text(block["numbered_list_item"].get("rich_text", []))
            indent = "  " * level
            return f"{indent}1. {text}" if text else ""

        elif block_type == "to_do":
            text = self.parse_rich_text(block["to_do"].get("rich_text", []))
            checked = block["to_do"].get("checked", False)
            checkbox = "[x]" if checked else "[ ]"
            return f"{checkbox} {text}" if text else ""

        elif block_type == "toggle":
            text = self.parse_rich_text(block["toggle"].get("rich_text", []))
            return f"▸ {text}" if text else ""

        elif block_type == "code":
            rich_text = block["code"].get("rich_text", [])
            language = block["code"].get("language", "")
            code = self.parse_rich_text(rich_text)
            if not code:
                return ""
            n = sum(1 for a in self.assets if a["kind"] == "code") + 1
            self.assets.append(
                {"token": f"CODE {n}", "kind": "code", "language": language or "code", "content": code}
            )
            return f"[CODE {n}]\n```{language}\n{code}\n```"

        elif block_type == "image":
            image = block["image"]
            url = image.get(image.get("type", ""), {}).get("url", "")
            if not url:
                return ""
            caption = self.parse_rich_text(image.get("caption", []))
            n = sum(1 for a in self.assets if a["kind"] == "figure") + 1
            self.assets.append(
                {"token": f"FIGURE {n}", "kind": "figure", "url": url, "caption": caption}
            )
            return f"[FIGURE {n}: {caption}]" if caption else f"[FIGURE {n}]"

        elif block_type == "quote":
            text = self.parse_rich_text(block["quote"].get("rich_text", []))
            return f"> {text}" if text else ""

        elif block_type == "callout":
            text = self.parse_rich_text(block["callout"].get("rich_text", []))
            icon = block["callout"].get("icon", {})
            emoji = ""
            if icon.get("type") == "emoji":
                emoji = icon.get("emoji", "") + " "
            return f"{emoji}{text}" if text else ""

        elif block_type == "equation":
            expression = block["equation"].get("expression", "")
            return f"$${expression}$$" if expression else ""

        elif block_type == "table":
            return ""  # rows arrive as table_row children and are parsed there

        elif block_type == "table_row":
            cells = block["table_row"].get("cells", [])
            return "| " + " | ".join(self.parse_rich_text(cell) for cell in cells) + " |"

        elif block_type == "divider":
            return "---"

        # Unhandled type — record it so coverage gaps are visible, not silent
        self.skipped_types.add(block_type)
        return ""

    def parse_rich_text(self, rich_text_array: List[Dict[str, Any]]) -> str:
        """Parse rich text array into plain text with basic formatting."""
        if not rich_text_array:
            return ""

        text_parts = []
        for text_obj in rich_text_array:
            plain_text = text_obj.get("plain_text", "")

            # Inline equations: plain_text holds the LaTeX expression
            if text_obj.get("type") == "equation" and plain_text:
                text_parts.append(f"${plain_text}$")
                continue

            # Apply basic formatting
            annotations = text_obj.get("annotations", {})
            if annotations.get("bold"):
                plain_text = f"**{plain_text}**"
            if annotations.get("italic"):
                plain_text = f"*{plain_text}*"
            if annotations.get("code"):
                plain_text = f"`{plain_text}`"

            text_parts.append(plain_text)

        return "".join(text_parts)

    def extract_content_sections(self, content: str, max_heading_level: int = 2) -> List[Dict[str, str]]:
        """Split content into sections based on heading level.

        Args:
            content: The markdown content to split
            max_heading_level: Maximum heading level to split on (1=H1 only, 2=H1+H2)

        This creates manageable chunks without over-fragmenting the content.
        Deeper headings are kept within their parent section for context.
        """
        sections = []
        current_section = {"heading": "", "content": []}

        lines = content.split("\n")

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Check heading level
            is_h1 = line_stripped.startswith("# ") and not line_stripped.startswith("## ")
            is_h2 = line_stripped.startswith("## ") and not line_stripped.startswith("### ")

            # Decide if we should split on this heading
            should_split = False
            if max_heading_level >= 1 and is_h1:
                should_split = True
            elif max_heading_level >= 2 and is_h2:
                should_split = True

            if should_split:
                # Save previous section if it has content
                if current_section["content"]:
                    sections.append({
                        "heading": current_section["heading"],
                        "content": "\n".join(current_section["content"])
                    })

                # Start new section
                current_section = {
                    "heading": line_stripped.lstrip("#").strip(),
                    "content": []
                }
                continue

            # Add line to current section (including H3+ headings)
            current_section["content"].append(line_stripped)

        # Add the last section
        if current_section["content"]:
            sections.append({
                "heading": current_section["heading"],
                "content": "\n".join(current_section["content"])
            })

        return sections if sections else [{"heading": "Content", "content": content}]

    def merge_small_sections(self, sections: List[Dict[str, str]], min_content_size: int = 500, max_sections: int = 50) -> List[Dict[str, str]]:
        """Merge small sections together to avoid over-fragmentation.

        Args:
            sections: List of sections to potentially merge
            min_content_size: Minimum content size before merging with next section
            max_sections: Maximum number of sections to return (merge if over this)

        Returns:
            Merged sections list
        """
        if len(sections) <= max_sections:
            # Check if we need to merge based on size
            needs_merging = any(len(s.get('content', '')) < min_content_size for s in sections)
            if not needs_merging:
                return sections

        # Calculate target sections per merge to reach max_sections
        merge_ratio = max(1, len(sections) // max_sections)

        merged = []
        current_merged = None
        items_in_current = 0

        for i, section in enumerate(sections):
            content = section.get('content', '')
            heading = section.get('heading', f'Section {i+1}')

            if current_merged is None:
                # Start new merged section
                current_merged = {
                    'heading': heading,
                    'content': content
                }
                items_in_current = 1
            else:
                # Check if we should merge or start new section
                current_size = len(current_merged['content'])
                should_merge = (
                    current_size < min_content_size or  # Current section too small
                    items_in_current < merge_ratio  # Haven't merged enough yet
                )

                if should_merge:
                    # Merge with current section
                    current_merged['content'] += f"\n\n### {heading}\n\n{content}"
                    items_in_current += 1
                else:
                    # Save current and start new
                    merged.append({
                        'heading': current_merged['heading'],
                        'content': current_merged['content']
                    })
                    current_merged = {
                        'heading': heading,
                        'content': content
                    }
                    items_in_current = 1

        # Add the last merged section
        if current_merged:
            merged.append({
                'heading': current_merged['heading'],
                'content': current_merged['content']
            })

        return merged

    def split_large_sections(self, sections: List[Dict[str, str]], max_section_size: int = 2500) -> List[Dict[str, str]]:
        """Split large sections into smaller chunks to avoid token limit issues.

        Args:
            sections: List of sections to potentially split
            max_section_size: Maximum character count per section (roughly 600-800 tokens)

        Returns:
            Sections with large ones split into smaller chunks
        """
        result = []

        for section in sections:
            heading = section.get('heading', 'Section')
            content = section.get('content', '')

            # If section is small enough, keep as-is
            if len(content) <= max_section_size:
                result.append(section)
                continue

            # Split large section into fence-safe chunks
            parts = chunk_text(content, max_section_size)
            for i, part in enumerate(parts, 1):
                result.append({
                    'heading': f"{heading} (part {i})" if len(parts) > 1 else heading,
                    'content': part
                })

        return result
