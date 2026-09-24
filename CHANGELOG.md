# Changelog

All notable changes to FlashyGen are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com); versions follow semver.

## [0.2.6] - 2026-09-24

Card-presentation fixes driven by reviewing the C++ decks
(issues [#31](https://github.com/tonserrobo/flashygen/issues/31),
[#32](https://github.com/tonserrobo/flashygen/issues/32)).

### Fixed
- **Code identifiers no longer italicised** (#32): `_format_content`'s bold/italic
  regexes matched any `*...*`/`_..._` pair, so C++ written without backticks
  (`std::out_of_range`, `char* argv`, `THIRD_PARTY_INCLUDES_START`, `*ptr`,
  `std::to_string(value)`) was wrapped in `<em>`/`<strong>` — the "only some text
  coloured or italics" symptom on cards. Emphasis is now CommonMark-flanking-aware:
  a `*` or `_` inside a word is literal, so identifiers survive while genuine
  `*italic*`/`**bold**` still convert.

### Changed
- **Formatted code-block cards generated alongside cloze** (#31): every code asset
  that gets a cloze card now also gets a `command` card whose answer is the full
  registered code block (via `[CODE n]`), unless a Q/A card already presents it.
  The main generation prompt also steers command cards for code-snippet teaching
  points. Code shown as a mistake still becomes a troubleshoot card instead.

## [0.2.5] - 2026-09-24

Cloze-safety and markdown-cleanliness fixes found while reviewing the
Pointers & References, Controlling Program Flow, and Variables & Constants decks
(issues [#33](https://github.com/tonserrobo/flashygen/issues/33),
[#34](https://github.com/tonserrobo/flashygen/issues/34),
[#35](https://github.com/tonserrobo/flashygen/issues/35)).

### Fixed
- **Overlapping cloze blanks no longer nest** (#33): `_build_cloze_note` wrapped
  blanks with sequential `str.replace(..., 1)`, so a blank that was a substring
  of an earlier one (`counter`/`count`, `*ptr = 10`/`*ptr`) re-wrapped *inside*
  the existing cloze — producing invalid `{{c1::{{c2::count}}er}}` notes that
  Anki rendered as broken deletions. The exporter now computes each blank's
  first occurrence that does not overlap an already-chosen span and applies
  wraps right-to-left, so overlapping blanks land on distinct free occurrences.
- **Braces in cloze blanks rejected** (#34): a blank like `arr[5]{}` was wrapped
  as `{{c2::arr[5]{}}}` and clipped to `arr[5]{` by Anki's non-greedy parser.
  Braces are now filtered at generation time (`_clean_blanks`), at the quality
  gate, and in the exporter, so no cloze can be built over a brace-containing
  blank.
- **Notion colour markup stripped from markdown notes** (#35): `~={red}...=~`
  spans survive copy-as-markdown exports and leaked into section headings and
  manifest keys (`~={red}Control types =~ (part 1)`). `markdown_loader` now
  removes them before sectioning, matching the Notion API path which already
  drops colour annotations.

## [0.2.4] - 2026-09-12

CLI and markdown-loader robustness (issues [#19](https://github.com/tonserrobo/flashygen/issues/19),
[#24](https://github.com/tonserrobo/flashygen/issues/24),
[#25](https://github.com/tonserrobo/flashygen/issues/25),
[#27](https://github.com/tonserrobo/flashygen/issues/27)).

### Fixed
- **UTF-8 forced on stdio at startup** (#19): `python main.py ... > log` on Windows
  crashed with `UnicodeEncodeError` because redirected stdout falls back to
  cp1252, which can't encode rich's ✓/⚠ glyphs. `main()` now reconfigures
  stdout/stderr to UTF-8.
- **Command cards no longer all under recall** (#27): a card whose answer IS code
  (a bare `[CODE n]` citation or a fenced block) is reclassified as `command` by
  the quality gate, so exact-syntax facts surface as command cards rather than
  being lumped under recall.

### Notes
- Mermaid/diagram fences routed to the figure registry (#24) and nested in-note
  H1s releveled to H2 (#25) were already implemented and tested; this release
  just closes them.

## [0.2.3] - 2026-09-12

Card-content fixes driven by reviewing the Variables & Constants deck
(issues [#26](https://github.com/tonserrobo/flashygen/issues/26),
[#28](https://github.com/tonserrobo/flashygen/issues/28),
[#29](https://github.com/tonserrobo/flashygen/issues/29)).

### Fixed
- **Explainer no longer leaks into the answer** (#28): a model that appends an
  `Explainer:` block to the back now has that text lifted into the explainer
  field (or stripped, if the field is already set) instead of rendering an
  orphaned "Explainer:" prefix as part of the answer.
- **Cloze fronts derived from the surrounding prose** (#26): when the cloze call
  returns no hint, the front is the first descriptive sentence of the code's
  context rather than the generic "Complete the code (CODE n)". Headings, code
  fences, table rows, and sentence fragments are skipped; the generic fallback
  is used only when nothing usable remains.
- **Every code asset yields a card** (#29): if the per-asset cloze call finds no
  valid blanks, a recall card citing the asset is generated instead of silently
  dropping the content. The deck-level dedupe also refuses to drop the last card
  of a section, so a redundant note can never surface as an uncovered section.

## [0.2.2] - 2026-07-03

Card-content fixes driven by comparing the four UE5 decks against their source Notion pages
(issues [#20](https://github.com/tonserrobo/flashygen/issues/20)–[#23](https://github.com/tonserrobo/flashygen/issues/23)).

### Fixed
- **Cloze backfill sees the surrounding prose** (#20): the per-asset cloze call now receives
  the sentences around the code block (fences stripped), so blanks carry the teaching point
  instead of defaulting to API names. Code the notes present as a mistake ("does not
  compile", naive anti-pattern) becomes a troubleshoot card ("What is wrong with this
  code?") instead of a memorisation cloze.
- **Diagram blocks no longer get cloze cards** (#21): mermaid/plantuml/dot/graphviz assets
  are illustrations, not code to memorise — skipped by the backfill.
- **Cross-section duplicate cards removed** (#22): summary/quick-reference sections restate
  facts already carded; the per-section quality gate can't see that. A deck-level LLM pass
  now judges duplicates, and a drop is only honored when word overlap confirms the pair is
  related (string similarity alone can't separate real duplicates from question-template
  overlap — measured on the 2026-07-03 decks).

### Changed
- **Tables called out in generation prompts** (#23): markdown table rows are dense fact
  lists (an 8-row decision table yielded one card); both prompts now direct one card per
  non-obvious row.

## [0.2.1] - 2026-07-03

Coverage fixes driven by a log review of the four UE5 deck runs
(issues [#13](https://github.com/tonserrobo/flashygen/issues/13)–[#18](https://github.com/tonserrobo/flashygen/issues/18)).

### Fixed
- **Empty checkpoints no longer freeze sections** (#13): a section that produced 0 cards is
  regenerated on the next run instead of being "resumed" empty forever. Resumed cards also
  get re-stamped with the current section heading, so coverage attribution survives renames.
- **Zero-card sections retried once** (#14, partial): a section whose cards were all dropped
  gets one more generation attempt before going uncovered. `cards_per_concept` now reaches
  the Ollama prompt ("Aim for about N cards") instead of stopping at the CLI banner.
- **Tiny tail chunks merged** (#15): a sub-`max/3` remainder after chunking folds into the
  previous chunk instead of becoming its own section that only ever yields dropped thin cards.
- **Column content warning** (#16): `column`/`column_list`/`synced_block` are treated as the
  structural containers they are — their children were always parsed; the false
  "Unhandled block types dropped" warning is gone.
- **Preamble sections named** (#18): content before the first heading is sectioned as
  "Introduction" instead of an empty string that leaked into prompts, tags, and manifest keys.

### Changed
- **Deterministic cloze generation** (#17): instead of asking the main generation call to also
  emit cloze JSON (which gemma-class models almost never did), every `[CODE n]` in a section
  now gets a dedicated focused call that picks blanks from the exact registered code, validated
  as substrings before the card is built. The cloze schema is dropped from the main prompt.
  Note: backfill runs at generation time, so checkpoint-resumed sections keep their existing
  cards — delete `decks/.work/<page_id>/` (or edit the note) to regenerate with cloze coverage.

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
