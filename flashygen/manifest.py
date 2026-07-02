"""Card manifest: provenance, coverage, and diffing against a Notion note (issues #5, #9).

The manifest persisted next to each .apkg is the assembled view of what was
generated from which section, so `check` can diff a deck against the current
note and `update` can regenerate only what changed.
"""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from flashygen.flashcard_generator import Flashcard


def section_hash(content: str) -> str:
    return hashlib.sha1(content.encode("utf-8")).hexdigest()[:12]


def card_to_dict(card: Flashcard) -> Dict[str, Any]:
    return {
        "front": card.front,
        "back": card.back,
        "explainer": card.explainer,
        "type": card.card_type,
        "tags": card.tags,
        "section": getattr(card, "section", ""),
        "code_ref": card.code_ref,
        "blanks": card.blanks,
    }


def card_from_dict(data: Dict[str, Any]) -> Flashcard:
    card = Flashcard(
        data["front"],
        data["back"],
        list(data.get("tags", [])),
        card_type=data.get("type", "recall"),
        explainer=data.get("explainer", ""),
        code_ref=data.get("code_ref", ""),
        blanks=list(data.get("blanks", [])),
    )
    card.section = data.get("section", "")
    return card


def build_manifest(
    page_id: str,
    title: str,
    sections: List[Dict[str, str]],
    cards: List[Flashcard],
    assets: List[Dict[str, str]],
) -> Dict[str, Any]:
    by_section: Dict[str, List[Dict[str, Any]]] = {}
    cited = set()
    for card in cards:
        by_section.setdefault(getattr(card, "section", ""), []).append(card_to_dict(card))
        searchable = f"{card.front} {card.back} {card.explainer} {card.code_ref}"
        cited.update(f"{k} {n}" for k, n in re.findall(r"(CODE|FIGURE) (\d+)", searchable))
    return {
        "page_id": page_id,
        "title": title,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sections": [
            {
                "heading": s["heading"],
                "content_hash": section_hash(s.get("content", "")),
                "cards": by_section.get(s["heading"], []),
            }
            for s in sections
        ],
        "uncited_assets": [a["token"] for a in assets if a["token"] not in cited],
    }


def coverage(manifest: Dict[str, Any]) -> Dict[str, Any]:
    sections = manifest["sections"]
    uncovered = [s["heading"] for s in sections if not s["cards"]]
    return {
        "covered": len(sections) - len(uncovered),
        "total": len(sections),
        "uncovered": uncovered,
        "uncited_assets": manifest.get("uncited_assets", []),
    }


def diff_sections(manifest: Dict[str, Any], current_sections: List[Dict[str, str]]) -> Dict[str, Any]:
    """Compare a manifest against the current state of the note's sections."""
    old = {s["heading"]: s for s in manifest["sections"]}
    new = [s["heading"] for s in current_sections if s["heading"] not in old]
    changed = [
        s["heading"]
        for s in current_sections
        if s["heading"] in old and section_hash(s.get("content", "")) != old[s["heading"]]["content_hash"]
    ]
    return {
        "new": new,
        "changed": changed,
        "uncovered": [s["heading"] for s in manifest["sections"] if not s["cards"]],
        "uncited_assets": manifest.get("uncited_assets", []),
    }


def write_manifest(manifest: Dict[str, Any], deck_path: str) -> str:
    path = Path(deck_path).with_suffix(".manifest.json")
    path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    return str(path)


def load_manifest(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
