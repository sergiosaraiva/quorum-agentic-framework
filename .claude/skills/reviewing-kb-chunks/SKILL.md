---
name: reviewing-kb-chunks
description: Read-only critic pass for knowledge-base chunks - grounding against the cited sources, AI slop and redundancy, and embedding suitability (self-containment, one topic, length, frontmatter). Use after writing-kb-chunks produces or edits a chunk, when auditing chunks for drift, and before a chunk set is accepted. Not for general docs (reviewing-documentation) or authoring (writing-kb-chunks).
---

# Reviewing knowledge-base chunks

Read-only. Report findings with evidence; never edit. Fixes go back to `documentation-curator` using `writing-kb-chunks`. The reviewer is never the author.

## Passes (in order)

| Pass | Check | Status when it fails |
|------|-------|----------------------|
| 1 Grounding | Extract every factual claim; open each file in `sources` and verify it. Score grounded / partial / ungrounded / stale. "Not shown" must not be restated as "not implemented" | `ungrounded` or `stale` |
| 2 Citation existence | Every `sources` path and every `links` chunk_id exists; ids unique. `check_chunks.py` only checks that `sources` is non-empty, so verify repo-path sources yourself; a source that is a brief name, a record id or the placeholder `example: invented` is not a `gate-failure` (see Known Non-Issues, `example: true`) | `gate-failure` (a chunk-rule violation, reported even if `check_chunks.py` missed it) |
| 3 Style and slop | Hedging, meta-commentary, restated title, summary sentence, marketing, a fact stated twice, terminology drift from sibling chunks, conversion noise | invented content or noise: `ungrounded`; slop alone: `slop` (does not block) |
| 4 Shape | Self-contained (no outward-pointing pronouns), one topic, 40-350 words (the lint limit; aim for 80 to 300; outside that is a target miss only), flat formatting, frontmatter complete (`chunk_id`, `title`, `topics`, `links`, `sources`; optional `example`) | missing frontmatter or two topics: `gate-failure`; other shape issues: `not-self-contained`, `too-long`, `too-short` (do not block) |
| 5 Cross-chunk | A fact belonging to another topic is linked, not re-explained; run a `business-kb` search for near-duplicates | duplicated mechanism: `conflict`; other redundancy: `redundant` (does not block) |

Blocking is decided only by `_SHARED-PATTERNS.md`, "What blocks": `ungrounded`, `fabricated-citation`, `stale`, `conflict` and `gate-failure`, reported at confidence >= 0.8. `slop`, `not-self-contained`, `too-long`, `too-short` and `redundant` do not block. A claim at confidence 0.50-0.79 goes in `unverified` (`_SHARED-PATTERNS.md`, Finding form) and never blocks.

## Output

Finding form: `_SHARED-PATTERNS.md` (canonical field names; `status` replaces `severity`).

```json
{
  "chunk_id": "BC-003",
  "claims_reviewed": 8,
  "findings": [
    {"id": "KC-1", "claim": "string", "category": "grounding|citation|style|shape|cross-chunk", "file": "kb/chunks/BC-003-x.md", "anchor": "heading or quoted literal",
     "status": "ungrounded|fabricated-citation|stale|conflict|gate-failure|slop|redundant|not-self-contained|too-long|too-short",
     "scenario": "evidence: file:anchor, tool result, or 'not found'", "fix": "string",
     "confidence": 0.85}
  ],
  "unverified": ["optional: unverified (would-be <status>): what and why"]
}
```

## Rules

- Evidence is a file + anchor or tool result, never a bare verdict.
- Re-check load-bearing claims against the live source, not a cached summary.
- Zero findings is valid; state what you checked.
- If a source is silent on something the chunk asserts, return a BQ in `questions_to_record` (`recording-decisions`) rather than a rewrite.
- Run `python3 scripts/kb/check_chunks.py` first and report its output verbatim. Report "pass" or findings; never edit the chunk.

## Checklist

- [ ] Every claim traced to a source
- [ ] Links and sources exist
- [ ] Slop and redundancy pass done
- [ ] Self-containment, one topic, length checked
- [ ] No edits made
