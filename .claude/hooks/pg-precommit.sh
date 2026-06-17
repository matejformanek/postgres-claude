#!/bin/bash
# pg-precommit.sh — body of dev/.git/hooks/pre-commit.
#
# Two stages:
#   A. Format-check every staged C/H/Perl file via pg-format.sh --check.
#      Any dirty file fails the commit and prints the diff.
#   B. Run meson test --no-rebuild for the R13-aware suite list emitted
#      by pg-phase-detect.sh. Any red suite fails the commit.
#
# Environment overrides:
#   PG_PRECOMMIT_SCOPE=skip    — both stages no-op (rare escape hatch)
#   PG_PRECOMMIT_SCOPE=regress — force stage B to "regress" only
#   PG_PRECOMMIT_SCOPE=full    — force stage B to full meson test
#   PG_PRECOMMIT_SCOPE=phase   — (default) ask pg-phase-detect.sh
#   PG_DRY_RUN=1               — print the suite list and exit 0
#                                without running tests (verification path)

set -u

if [ -z "${CLAUDE_PROJECT_DIR:-}" ]; then
  CLAUDE_PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
fi
export CLAUDE_PROJECT_DIR

DEV_ROOT="$CLAUDE_PROJECT_DIR/dev"
BUILD_DIR="$DEV_ROOT/build-debug"
HOOK_DIR="$CLAUDE_PROJECT_DIR/.claude/hooks"

SCOPE="${PG_PRECOMMIT_SCOPE:-phase}"

if [ "$SCOPE" = "skip" ]; then
  echo "pg-precommit: PG_PRECOMMIT_SCOPE=skip — bypassing both stages" >&2
  exit 0
fi

# --- preflight ---------------------------------------------------------------
if [ ! -d "$BUILD_DIR" ]; then
  echo "pg-precommit: $BUILD_DIR does not exist — run /setup-pg first" >&2
  exit 1
fi

STAGED="$(git -C "$DEV_ROOT" diff --cached --name-only --diff-filter=ACM 2>/dev/null || true)"
if [ -z "$STAGED" ]; then
  # Nothing to check (e.g. --allow-empty). Don't gate.
  exit 0
fi

# --- stage A: format-check ---------------------------------------------------
fail_a=0
while IFS= read -r path; do
  [ -n "$path" ] || continue
  case "$path" in
    *.c|*.h|*.pl|*.pm) : ;;
    *) continue ;;
  esac
  # The format script accepts an absolute or repo-relative path.
  abs="$DEV_ROOT/$path"
  if ! bash "$HOOK_DIR/pg-format.sh" --check "$abs"; then
    fail_a=1
  fi
done <<EOF
$STAGED
EOF

if [ $fail_a -ne 0 ]; then
  echo "" >&2
  echo "pg-precommit: format-check FAILED. Fix with:" >&2
  echo "  bash $HOOK_DIR/pg-format.sh <path>   # rewrites in place" >&2
  echo "or run pgindent / pgperltidy directly. Bypassing with --no-verify" >&2
  echo "is forbidden inside /pg-implement phases (R4 amendment, v1.3)." >&2
  exit 1
fi

# --- stage B: scoped meson test ---------------------------------------------
case "$SCOPE" in
  regress) SUITES="regress" ;;
  full)    SUITES="" ;;  # empty → run everything
  phase|*)
    # pg-phase-detect prints telemetry on stderr and the suite list on stdout.
    # Let stderr flow through to the user; capture stdout into SUITES.
    SUITES="$(bash "$HOOK_DIR/pg-phase-detect.sh")"
    ;;
esac

if [ "${PG_DRY_RUN:-0}" = "1" ]; then
  echo "pg-precommit: DRY RUN — would run suites: ${SUITES:-<full>}" >&2
  exit 0
fi

# Build the suite args. Empty SUITES means full meson test (no --suite filter).
SUITE_ARGS=()
if [ -n "$SUITES" ]; then
  for s in $SUITES; do
    SUITE_ARGS+=(--suite "$s")
  done
fi

echo "pg-precommit: meson test --no-rebuild -C $BUILD_DIR ${SUITE_ARGS[*]}" >&2
if ! meson test --no-rebuild -C "$BUILD_DIR" "${SUITE_ARGS[@]}"; then
  echo "" >&2
  echo "pg-precommit: meson test FAILED. Inspect:" >&2
  echo "  $BUILD_DIR/meson-logs/testlog.txt" >&2
  echo "Re-run targeted suite locally before committing." >&2
  exit 1
fi

exit 0
