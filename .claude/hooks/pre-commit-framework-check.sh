#!/usr/bin/env bash
# Pre-commit hook: lint staged agent and skill frontmatter.
# Scope: .claude/agents/*.md (names starting with "_" are skipped) and .claude/skills/<name>/SKILL.md.
# When scripts/framework_lint.py exists it lints a temp copy of the staged index (git checkout-index),
# so partial staging and staged deletions are judged correctly; otherwise the inline check below runs:
#   - frontmatter block present and valid YAML (PyYAML if installed, else a simple key: value parser)
#   - name present and equal to the file name (agent) or the folder name (skill)
#   - description present, <= 1024 characters
#   - agent: model is opus | sonnet | haiku; tools lists no Agent and no AskUserQuestion
# Install with: bash .claude/hooks/install-framework-check-hook.sh
# Self-test:    bash .claude/hooks/test-pre-commit-framework-check.sh
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# Staged changes in scope, deletions included (deleting a skill folder must update SKILL-INDEX.md).
CHANGED=()
while IFS= read -r line; do
  [ -n "$line" ] && CHANGED+=("$line")
done < <(git diff --cached --name-only --diff-filter=ACMD \
  | grep -E '^\.claude/(agents/[^/]+\.md|skills/[^/]+/SKILL\.md|skills/SKILL-INDEX\.md)$' || true)

if [ "${#CHANGED[@]}" -eq 0 ]; then
  echo "No agent or skill files staged, skipping framework check."
  exit 0
fi

# Added/copied/modified files only, for the inline fallback (a deleted file has no content to check).
STAGED=()
while IFS= read -r line; do
  [ -n "$line" ] && STAGED+=("$line")
done < <(git diff --cached --name-only --diff-filter=ACM \
  | grep -E '^\.claude/(agents/[^_/][^/]*\.md|skills/[^/]+/SKILL\.md)$' || true)

# Preferred: lint the STAGED content. Materialise the index (not the working tree) into a temp tree,
# so a partially staged bad file and staged deletions are judged as they will be committed.
if [ -f scripts/framework_lint.py ] && grep -q -- '--root' scripts/framework_lint.py; then
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  git ls-files -z -- .claude/agents .claude/skills | xargs -0 -r git checkout-index --prefix="$TMP/" --
  echo "Linting staged content with scripts/framework_lint.py ..."
  if python3 scripts/framework_lint.py --root "$TMP/.claude"; then
    echo "Framework lint OK."
    exit 0
  fi
  echo ""
  echo "COMMIT BLOCKED: fix the errors above and try again."
  echo "To bypass (not recommended): git commit --no-verify"
  exit 1
fi

if [ "${#STAGED[@]}" -eq 0 ]; then
  echo "Only deletions or non-checkable files staged and no scripts/framework_lint.py; nothing to check inline."
  exit 0
fi

echo "Checking ${#STAGED[@]} staged agent/skill file(s) (inline check)..."
if ! python3 -I - "${STAGED[@]}" <<'PY'
import os
import re
import subprocess
import sys

try:
    import yaml  # optional
except ImportError:
    yaml = None

MODELS = {"opus", "sonnet", "haiku"}
FORBIDDEN_TOOLS = {"Agent", "AskUserQuestion"}
errors = []


def simple_parse(block):
    data = {}
    for raw in block.splitlines():
        if not raw.strip() or raw.startswith((" ", "\t", "#")) or ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        data[key.strip()] = value
    return data


for path in sys.argv[1:]:
    shown = subprocess.run(["git", "show", ":" + path], capture_output=True, text=True)
    if shown.returncode != 0:
        errors.append(f"{path}: cannot read staged content")
        continue
    text = shown.stdout.replace("\r\n", "\n")
    match = re.match(r"\A---\n(.*?)\n---[ \t]*(?:\n|\Z)", text, re.S)
    if not match:
        errors.append(f"{path}: missing or unterminated frontmatter block")
        continue
    block = match.group(1)
    if yaml is not None:
        try:
            fm = yaml.safe_load(block)
        except yaml.YAMLError as exc:
            errors.append(f"{path}: invalid YAML frontmatter ({exc})")
            continue
    else:
        fm = simple_parse(block)
    if not isinstance(fm, dict):
        errors.append(f"{path}: frontmatter is not a mapping")
        continue
    is_skill = path.endswith("/SKILL.md")
    expected = os.path.basename(os.path.dirname(path)) if is_skill else os.path.basename(path)[:-3]
    name = fm.get("name")
    if not name:
        errors.append(f"{path}: missing 'name'")
    elif str(name) != expected:
        errors.append(f"{path}: name '{name}' must equal {'folder' if is_skill else 'file'} name '{expected}'")
    desc = fm.get("description")
    if not desc:
        errors.append(f"{path}: missing 'description'")
    elif len(str(desc)) > 1024:
        errors.append(f"{path}: description is {len(str(desc))} chars (max 1024)")
    if not is_skill:
        if fm.get("model") not in MODELS:
            errors.append(f"{path}: model must be one of {sorted(MODELS)}, got {fm.get('model')!r}")
        tools = fm.get("tools") or ""
        if isinstance(tools, str):
            tools = [t.strip() for t in tools.split(",")]
        bad = sorted(FORBIDDEN_TOOLS.intersection(str(t).strip() for t in tools))
        if bad:
            errors.append(f"{path}: tools must not list {', '.join(bad)} (subagents cannot spawn agents or ask the user)")

for e in errors:
    print("ERROR:", e)
sys.exit(1 if errors else 0)
PY
then
  echo ""
  echo "COMMIT BLOCKED: fix the errors above and try again."
  echo "To bypass (not recommended): git commit --no-verify"
  exit 1
fi
echo "Agent and skill frontmatter OK."
