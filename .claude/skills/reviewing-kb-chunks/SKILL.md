---
name: reviewing-kb-chunks
description: Read-only critic pass for knowledge-base chunks - grounding against the cited sources, AI slop and redundancy, and embedding suitability (self-containment, one topic, length, frontmatter). Use after writing-kb-chunks produces or edits a chunk, when auditing chunks for drift, and before a chunk set is accepted. Not for general docs (reviewing-documentation) or authoring (writing-kb-chunks).
---

# Reviewing knowledge-base chunks

Read-only. Report findings with evidence; never edit. Fixes go back to `documentation-curator` using `writing-kb-chunks`. The reviewer is never the author.

## Passes (in order)

| Pass | Check | Blocking when |
|------|-------|---------------|
| 1 Grounding | Extract every factual claim; open each file in `sources` and verify it. Score grounded / partial / ungrounded / stale. "Not shown" must not be restated as "not implemented" | Any ungrounded or stale claim |
| 2 Citation existence | Every `sources` path and every `links` chunk_id exists; ids unique | A dangling reference |
| 3 Style and slop | Hedging, meta-commentary, restated title, summary sentence, marketing, a fact stated twice, terminology drift from sibling chunks, conversion noise | Noise or invented content; slop alone is minor |
| 4 Shape | Self-contained (no outward-pointing pronouns), one topic, 40-350 words (the lint limit; aim for 80 to 300; outside that is a target miss only), flat formatting, frontmatter complete (`chunk_id`, `title`, `topics`, `links`, `sources`; optional `example`) | Missing frontmatter, two topics |
| 5 Cross-chunk | A fact belonging to another topic is linked, not re-explained; run a `business-kb` search for near-duplicates | Duplicated mechanism |

## Output

```json
{
  "chunk_id": "BC-003",
  "claims_reviewed": 8,
  "findings": [
    {"claim": "string", "pass": "grounding|citation|style|shape|cross-chunk",
     "status": "ungrounded|stale|dangling-link|slop|redundant|not-self-contained|too-long|too-short|two-topics|noise",
     "evidence": "file:line, tool result, or 'not found'",
     "severity": "blocking|minor"}
  ]
}
```

## Rules

- Evidence is a file:line or tool result, never a bare verdict.
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
