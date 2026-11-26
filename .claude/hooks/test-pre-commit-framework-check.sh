#!/usr/bin/env bash
# Self-test for pre-commit-framework-check.sh and the installer, in a throwaway git repo.
# Expects: good frontmatter exits 0; each bad case exits non-zero; installer refuses a foreign hook.
# Run: bash .claude/hooks/test-pre-commit-framework-check.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
fail=0

cd "$TMP"
git init -q .
git config user.email t@example.com
git config user.name tester
mkdir -p .claude/hooks .claude/agents .claude/skills/demo-skill
cp "$HERE/pre-commit-framework-check.sh" .claude/hooks/

expect() { # expect <0|nonzero> <label>
  local want="$1" label="$2" rc=0
  bash .claude/hooks/pre-commit-framework-check.sh >/dev/null 2>&1 || rc=$?
  if { [ "$want" = 0 ] && [ "$rc" -eq 0 ]; } || { [ "$want" = nonzero ] && [ "$rc" -ne 0 ]; }; then
    echo "PASS: $label (exit $rc)"
  else
    echo "FAIL: $label (exit $rc, wanted $want)"; fail=1
  fi
}
sedi() { # sedi <expr> <file>: in-place edit that works with GNU and BSD sed
  sed -i.bak "$1" "$2" && rm -f "$2.bak"
}
stage() { git add -f .claude >/dev/null; }
reset() { git rm -rq --cached .claude/agents .claude/skills >/dev/null 2>&1 || true; rm -f .claude/agents/* .claude/skills/*/SKILL.md; }

# 1 good agent and skill
cat > .claude/agents/demo.md <<'EOF'
---
name: demo
description: A fine description.
model: sonnet
tools: Read, Grep
---
body
EOF
cat > .claude/skills/demo-skill/SKILL.md <<'EOF'
---
name: demo-skill
description: A fine skill description.
---
body
EOF
stage; expect 0 "good agent and skill"

# 2 bad agent: wrong name
sedi 's/^name: demo$/name: other/' .claude/agents/demo.md; stage
expect nonzero "agent name differs from filename"
sedi 's/^name: other$/name: demo/' .claude/agents/demo.md

# 3 bad agent: bad model
sedi 's/^model: sonnet$/model: gpt/' .claude/agents/demo.md; stage
expect nonzero "agent model not allowed"
sedi 's/^model: gpt$/model: sonnet/' .claude/agents/demo.md

# 4 bad agent: forbidden tool
sedi 's/^tools: Read, Grep$/tools: Read, Agent/' .claude/agents/demo.md; stage
expect nonzero "agent lists Agent tool"
sedi 's/^tools: Read, Agent$/tools: Read, Grep/' .claude/agents/demo.md

# 5 skill: name differs from folder
sedi 's/^name: demo-skill$/name: wrong/' .claude/skills/demo-skill/SKILL.md; stage
expect nonzero "skill name differs from folder"
sedi 's/^name: wrong$/name: demo-skill/' .claude/skills/demo-skill/SKILL.md

# 6 skill: description too long
long="$(python3 -c 'print("x"*1030)')"
sedi "s/^description: A fine skill description.$/description: $long/" .claude/skills/demo-skill/SKILL.md; stage
expect nonzero "skill description over 1024 chars"

# 7 skill: no frontmatter
printf 'no frontmatter here\n' > .claude/skills/demo-skill/SKILL.md; stage
expect nonzero "skill without frontmatter"

# 8 installer refuses to overwrite a foreign pre-commit hook
cp "$HERE/install-framework-check-hook.sh" .claude/hooks/
mkdir -p .git/hooks
printf '#!/bin/sh\necho foreign\n' > .git/hooks/pre-commit
if bash .claude/hooks/install-framework-check-hook.sh >/dev/null 2>&1; then
  echo "FAIL: installer overwrote a foreign hook"; fail=1
else
  echo "PASS: installer refuses a foreign hook"
fi
rm -f .git/hooks/pre-commit
if bash .claude/hooks/install-framework-check-hook.sh >/dev/null 2>&1 && grep -q quorum-hooks-managed .git/hooks/pre-commit; then
  echo "PASS: installer installs into a clean hooks dir"
else
  echo "FAIL: installer did not install"; fail=1
fi

# 8b installer run from a subdirectory installs into the repo's hooks dir, not a path relative to the subdirectory
rm -f .git/hooks/pre-commit
mkdir -p deep/sub
if (cd deep/sub && bash "$TMP/.claude/hooks/install-framework-check-hook.sh" >/dev/null 2>&1) \
    && grep -q quorum-hooks-managed .git/hooks/pre-commit && [ ! -e deep/sub/.git ] && [ ! -e deep/.git ]; then
  echo "PASS: installer run from a subdirectory installs into the repo hooks dir"
else
  echo "FAIL: installer run from a subdirectory did not install into .git/hooks"; fail=1
fi
rm -rf deep

# 9 delegated path: scripts/framework_lint.py present, judged on STAGED content
LINT="$HERE/../../scripts/framework_lint.py"
if [ -f "$LINT" ]; then
  D="$TMP/delegated"
  mkdir -p "$D" && cd "$D"
  git init -q . && git config user.email t@example.com && git config user.name tester
  mkdir -p .claude/hooks .claude/agents .claude/skills/demo-skill scripts
  cp "$HERE/pre-commit-framework-check.sh" .claude/hooks/
  cp "$LINT" scripts/framework_lint.py
  cat > .claude/agents/demo.md <<'EOF2'
---
name: demo
description: A fine description.
model: sonnet
tools: Read, Grep
---
body
EOF2
  cat > .claude/skills/demo-skill/SKILL.md <<'EOF2'
---
name: demo-skill
description: A fine skill description.
---
body
EOF2
  cat > .claude/skills/SKILL-INDEX.md <<'EOF2'
# Skill index

| Skill | Purpose | Used by |
|-------|---------|---------|
| demo-skill | Demo | main |
EOF2
  git add -f . >/dev/null
  expect 0 "delegated: good tree"
  git commit -qm base --no-verify

  # staged blob bad, working tree fixed afterwards (partial staging): must fail
  sedi 's/^name: demo$/name: other/' .claude/agents/demo.md; git add .claude/agents/demo.md
  sedi 's/^name: other$/name: demo/' .claude/agents/demo.md
  expect nonzero "delegated: partially staged bad file is caught"
  git reset -q --hard

  # staged blob good, working tree broken afterwards (unstaged edit): must pass
  sedi 's/^description: A fine description.$/description: Changed./' .claude/agents/demo.md; git add .claude/agents/demo.md
  sedi 's/^model: sonnet$/model: gpt/' .claude/agents/demo.md
  expect 0 "delegated: unstaged breakage is not judged"
  git reset -q --hard

  # staged deletion of a skill folder without updating SKILL-INDEX.md: must fail
  git rm -rq .claude/skills/demo-skill
  expect nonzero "delegated: deleting a skill without updating SKILL-INDEX.md is caught"
  cd "$TMP"
else
  echo "SKIP: delegated-path cases (scripts/framework_lint.py not found at $LINT)"
fi

[ "$fail" -eq 0 ] && echo "ALL SELF-TESTS PASSED" || echo "SELF-TEST FAILURES"
exit "$fail"
