---
description: Install the pg-precommit git hook into dev/.git/hooks/pre-commit. Idempotent; refuses to overwrite a foreign hook.
---

# pg-install-hooks

Installs `dev/.git/hooks/pre-commit` as a thin shim into
`postgres-claude/.claude/hooks/pg-precommit.sh`, plus makes sure
`pg_bsd_indent` is built (pgindent needs it).

Re-run after `/pg-reclone-dev` (the re-cloned `dev/.git/` has no hooks)
or after any time the hook went missing. `/setup-pg` chains into this
command automatically; running it manually is only needed when those
flows are skipped.

## What it does

1. Resolves the absolute path of `postgres-claude/.claude/hooks/pg-precommit.sh`.
2. Inspects `dev/.git/hooks/pre-commit`:
   - **Absent** → writes the shim.
   - **Present + contains `# pg-precommit-guard v1` marker** → no-op.
   - **Present + no marker** → exits nonzero with a "manual hook"
     message. Touching a hand-written hook is the user's call.
3. Makes the shim executable.
4. Confirms `pg_bsd_indent` exists in `dev/build-debug/`; builds it via
   ninja if missing so pgindent works on the first commit.

## Run this

From the project root (`/Users/matej/Work/postgres/postgres-claude/`):

```bash
set -e

PROJECT_DIR="$PWD"
DEV_ROOT="$PROJECT_DIR/dev"
HOOK_SRC="$PROJECT_DIR/.claude/hooks/pg-precommit.sh"
HOOK_DST="$DEV_ROOT/.git/hooks/pre-commit"
MARKER="# pg-precommit-guard v1"

# Sanity
if [ ! -f "$HOOK_SRC" ]; then
  echo "ERROR: $HOOK_SRC not found — run from postgres-claude/ root" >&2
  exit 1
fi
if [ ! -d "$DEV_ROOT/.git" ]; then
  echo "ERROR: $DEV_ROOT/.git not found — run /setup-pg / /pg-reclone-dev first" >&2
  exit 1
fi

# Idempotent install
if [ -f "$HOOK_DST" ]; then
  if grep -qF "$MARKER" "$HOOK_DST"; then
    echo "pg-install-hooks: pre-commit already installed (marker found) — no-op"
  else
    echo "ERROR: $HOOK_DST exists without the pg-precommit-guard marker." >&2
    echo "       A manual hook is in place; remove or merge it before re-running." >&2
    exit 1
  fi
else
  cat > "$HOOK_DST" <<EOF
#!/bin/bash
$MARKER
# Auto-installed by /pg-install-hooks. Source of truth:
#   $HOOK_SRC
# Re-install via /pg-install-hooks (idempotent).
export CLAUDE_PROJECT_DIR="$PROJECT_DIR"
exec bash "$HOOK_SRC"
EOF
  chmod +x "$HOOK_DST"
  echo "pg-install-hooks: installed $HOOK_DST"
fi

# pg_bsd_indent — pgindent needs this binary on PATH at hook time.
BSD_INDENT_BIN="$DEV_ROOT/build-debug/src/tools/pg_bsd_indent/pg_bsd_indent"
if [ ! -x "$BSD_INDENT_BIN" ]; then
  if [ -f "$DEV_ROOT/build-debug/build.ninja" ]; then
    echo "pg-install-hooks: building pg_bsd_indent..."
    ninja -C "$DEV_ROOT/build-debug" src/tools/pg_bsd_indent/pg_bsd_indent
  else
    echo "WARN: dev/build-debug not configured — run /setup-pg, then re-run /pg-install-hooks" >&2
  fi
fi

echo "pg-install-hooks: done"
```

## After running

Tell the user:

- Pre-commit hook now active on `dev/`. Format-check + R13-scoped meson
  test run automatically on each commit.
- The PostToolUse hook (configured in `.claude/settings.json`) auto-fixes
  `.c/.h/.pl/.pm` files on edit.
- Escape hatches: `PG_PRECOMMIT_SCOPE=skip git commit ...` bypasses both
  stages; `PG_PRECOMMIT_SCOPE=regress` skips the broader R13 tiers.
- `--no-verify` is **forbidden inside `/pg-implement` phases** (R4
  amendment, v1.3). Tune the scope env var instead.

## Troubleshooting

- **"manual hook" error**: another tool wrote `dev/.git/hooks/pre-commit`
  (e.g. `husky`, a teammate's setup). Inspect, merge logic if needed,
  then re-run.
- **`pg_bsd_indent` build fails**: usually a stale `build.ninja`. Run
  `/setup-pg --force` and retry.
- **Hook never fires**: verify `dev/.git/hooks/pre-commit` is executable
  (`ls -la dev/.git/hooks/pre-commit`). Git silently skips non-executable
  hooks.

## Cross-references

- `.claude/hooks/pg-precommit.sh` — the body the shim execs.
- `.claude/hooks/pg-format.sh` — invoked per staged file in stage A.
- `.claude/hooks/pg-phase-detect.sh` — emits the R13 suite list for stage B.
- `.claude/rules/pg-implement-discipline.md` — R4 + R13 amendments
  (v1.3) describe the gate's contract.
- `.claude/commands/setup-pg.md` — chains into this command on first build.
- `.claude/commands/pg-reclone-dev.md` — re-cloning wipes `dev/.git/hooks/`,
  so `/setup-pg` reinstalls.
