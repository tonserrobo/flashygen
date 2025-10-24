"""Parse Notion blocks into structured content for flashcard generation."""

from typing import Dict, List, Any


class NotionContentParser:
    """Parse Notion blocks into readable text."""

    def parse_blocks(self, blocks: List[Dict[str, Any]], level: int = 0) -> str:
        """Parse blocks into formatted text."""
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
            return f"```{language}\n{code}\n```" if code else ""

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

        elif block_type == "divider":
            return "---"

        # Add more block types as needed
        return ""

    def parse_rich_text(self, rich_text_array: List[Dict[str, Any]]) -> str:
        """Parse rich text array into plain text with basic formatting."""
        if not rich_text_array:
            return ""

        text_parts = []
        for text_obj in rich_text_array:
            plain_text = text_obj.get("plain_text", "")

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

    def extract_content_sections(self, content: str) -> List[Dict[str, str]]:
        """Split content into sections based on headings for better flashcard generation."""
        sections = []
        current_section = {"heading": "", "content": []}

        lines = content.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if it's a heading
            if line.startswith("# ") or line.startswith("## ") or line.startswith("### "):
                # Save previous section if it has content
                if current_section["content"]:
                    sections.append({
                        "heading": current_section["heading"],
                        "content": "\n".join(current_section["content"])
                    })

                # Start new section
                current_section = {
                    "heading": line.lstrip("#").strip(),
                    "content": []
                }
            else:
                current_section["content"].append(line)

        # Add the last section
        if current_section["content"]:
            sections.append({
                "heading": current_section["heading"],
                "content": "\n".join(current_section["content"])
            })

        return sections if sections else [{"heading": "Content", "content": content}]
