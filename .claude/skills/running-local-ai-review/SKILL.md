---
name: running-local-ai-review
description: Runs scripts/ai_review_local.py, the required local AI review of the current branch before pushing, with a capped number of rounds and no API key. It runs the quality-guardian and regression-detective prompts only; together with the in-session reviewer pair it is the review gate. Use before the first push of a branch and after fixing review findings. Not for reviewing an open PR on GitHub (pr-review) or running the test suite.
---

# Running the local AI review

The script reviews your branch diff with the `claude` CLI and your own sign-in; no `ANTHROPIC_API_KEY` is needed. It is the required AI review: together with the in-session pair `quality-guardian || regression-detective` over the whole branch (Pre-Push Branch Gate) it is the gate, and a human then merges. The GitHub review (`pr-review`) is an optional, stronger second gate that runs only when `ANTHROPIC_API_KEY` is set; without the key its job is skipped and the green check is not a review. The script does not replace tests.

## What it does

| Step | Detail |
|------|--------|
| 1 | Computes `git diff <base>...HEAD` (default base `origin/main`; the parent branch for a stacked PR) |
| 2 | Splits the diff into chunks under `--max-chunk-bytes`; no code is dropped |
| 3 | Builds one prompt per chunk from the `pr-review` skill plus the `quality-guardian` and `regression-detective` instructions only (no security or infra reviewer), and runs `claude -p` headless |
| 4 | Merges findings, writes `.ai-review/findings.md`, `findings.json` and `state.json` (the round counter), prints a summary |

Exit codes: 0 no blocking findings, or skipped when the `claude` CLI is missing and `--require` is not set; 1 blocking findings, 2 usage or environment error (including malformed model output), 3 round cap reached.

## Flags

| Flag | Meaning |
|------|---------|
| `--base` | Base ref (env `AI_REVIEW_BASE`, default `origin/main`) |
| `--model` | Model alias or id (env `AI_REVIEW_MODEL`, default `sonnet`) |
| `--max-chunk-bytes` | Chunk size limit (default 60000) |
| `--max-rounds` | Local round cap (default 3) |
| `--out-dir` | Output directory (default `.ai-review`) |
| `--claude-bin` | Claude CLI binary (env `CLAUDE_BIN`) |
| `--timeout` | Seconds per model call (default 600) |
| `--require` | Exit 2 instead of skipping (exit 0) when the `claude` binary is not on PATH; use it for the gate |
| `--reset` | Reset the round counter (use after a human review) |
| `--dry-run` | Print the first prompt, call no model, spend nothing |

The round number is kept in `.ai-review/state.json`; there is no `--round` flag. Run `python3 scripts/ai_review_local.py --help` to confirm the current flags.

```bash
python3 scripts/ai_review_local.py --dry-run                       # inspect the prompt
python3 scripts/ai_review_local.py --base origin/main --require     # the gate command, default model
python3 scripts/ai_review_local.py --base origin/main --require --model opus # stronger pass for risky changes
python3 scripts/ai_review_local.py --reset                         # after a human review
```

## Model choice

| Situation | Model |
|-----------|-------|
| Routine branch, first pass | `sonnet` (default, cheap) |
| Auth, data model, migrations, money or core logic | `--model opus`, closer to what the GitHub review runs |

## Rounds and triage

Round cap 3 (round = review, fix, review). After round 3 with findings still open, stop and escalate to a human; do not loop further.

| Severity | Action |
|----------|--------|
| blocking | Fix now; re-run |
| warning | Fix, or record a deferral with reason in the PR description |
| info | Optional |
| False positive | Note the reason in the PR description; if it repeats, add a Known Non-Issue to `.claude/agents/_SHARED-PATTERNS.md` |

- A finding without file and line evidence is not actionable; discard it or re-run with a narrower scope.
- The agent that wrote the code applies fixes; the script judges them. Never mark a finding resolved without a re-run.

## Counters

Three counters exist and none shares state: the in-session Loop-Back cap (3 per gate chain; no stored state; it resets with each new gate chain), this script's `--max-rounds` (stored in `.ai-review/state.json` as `{"branches": {name: {rounds, findings}}}`, one entry per branch; `--reset` clears the current branch's entry. A corrupt state file exits 2 telling you to run `--reset`, and an old-format file is rejected the same way until `--reset`), and the GitHub `MAX_ROUNDS` (marker comments by `github-actions[bot]` on the PR, across pushes; a human resets it by deleting the markers, or lets it run on by raising `MAX_ROUNDS` and removing the label). Finishing local rounds does not use up GitHub rounds, and the reverse. See `.claude/agents/_SHARED-PATTERNS.md` Loop-Back Rule.

## Order

1. Build, tests and format green locally.
2. In-session pair over the whole branch, then this script with `--require`, up to 3 rounds (`--model opus` for risky changes).
3. Push and open the PR; a human merges. If `ANTHROPIC_API_KEY` is set, the GitHub review (`pr-review`) also runs as an optional second gate.
