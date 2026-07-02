# Changelog

All notable changes to FlashyGen are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com); versions follow semver.

## [0.2.0] - 2026-07-02

Card-quality and incremental-update overhaul, driven by a review of the UE5 C++ decks
(issues [#1](https://github.com/tonserrobo/flashygen/issues/1)–[#12](https://github.com/tonserrobo/flashygen/issues/12)).

### Added
- **Asset registry** (#8): parser records code blocks and images; content carries
  `[CODE n]`/`[FIGURE n]` tokens the model cites instead of retyping. Exporter substitutes
  byte-exact `<pre>` blocks and downloads figures (Notion URLs expire ~1h) into the `.apkg`
  as bundled media.
- **Cloze cards** (#11): generated in addition to Q/A cards for registered code blocks —
  the model selects blank substrings, the exporter wraps `{{c1::…}}` on verbatim code.
- **Explainer field** (#10): third note field rendered below the answer with context beyond
  the recalled fact; blanked automatically if it restates the answer.
- **Quality gate** (#1, #6): drops command/troubleshoot cards without code, near-empty backs,
  prompt leakage, backs restating fronts, near-duplicate fronts, and cards citing
  non-existent assets.
- **LLM validation pass** (#6): per-chunk grounding check against the source
  (`--validate/--no-validate`, default on); incorrect cards dropped, fixable ones corrected.
  Fails open — validation can never destroy a deck.
- **Coverage manifest** (#5): `<deck>.manifest.json` written next to every deck with per-card
  provenance (section, content hash) and uncited assets; coverage summary printed after runs.
- **`check` command** (#9): diff a deck's manifest against the current Notion note — new,
  changed, and uncovered sections plus uncited assets; exit 1 on gaps (cron-able, no LLM calls).
- **`update` command** (#9): regenerate only new/changed/uncovered sections, keep the rest
  from the manifest, re-export.
- **Resumable generation** (#9): per-section checkpoints in `decks/.work/<page_id>/` written
  immediately after each section; re-runs skip unchanged sections without repeat LLM calls.
- **Equation & table support** (#4): Notion equation blocks/inline equations emitted as LaTeX
  and rendered via Anki MathJax; tables carried through as markdown rows; unhandled block
  types now produce a visible warning instead of vanishing.
- Card `type` exported as a `type::<x>` Anki tag; Ollama prompt rewritten with a worked
  example and density-scaled card counts (#1).
- Test suite: 56 tests (pytest added as dev dependency).

### Changed
- **Deterministic IDs** (#9): fixed model id, deck id from the Notion page id, note guids
  from (page, section, front) — re-imports merge in Anki and preserve review history.
  *One-time migration: delete decks imported with 0.1.x from Anki before re-importing.*
- Chunking is code-fence-aware (#2): fenced blocks are atomic and stay with the prose that
  introduces them; both the section splitter and the sub-chunker share one implementation.
- Decks (and manifests, media, work dirs) now default to `decks/` instead of the repo root (#12).

### Fixed
- ` ```c++ ` code fences no longer break the exporter — language tag preserved, no stray
  `++` injected into card text (#3; also affected `c#`, `objective-c++`).
- LaTeX in cards no longer mangled by the markdown formatter (math spans are
  placeholder-protected and HTML-escaped) (#4).
- `debug_response.json` restored to valid JSON (committed merge conflict markers removed) (#7).
- Stale tests repaired; `typer.Exit` no longer swallowed by the generic error handler.

## [0.1.0]

Initial version: Notion page → parsed sections → Ollama/Claude generation → styled `.apkg` export.
