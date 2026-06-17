#!/bin/bash
# pg-format.sh — format-check / auto-fix wrapper around pgindent + pgperltidy.
#
# Two modes:
#
#   Default (PostToolUse hook): auto-fix in place, ALWAYS exit 0,
#   emit one JSON line on stdout describing what happened so Claude
#   sees it as additionalContext on the next turn.
#
#   --check (pre-commit hook): exit nonzero + print a unified diff
#   if the file is dirty. Used by pg-precommit.sh stage A.
#
# Routing:
#   *.c / *.h         → pgindent (skipped if pg_bsd_indent is missing
#                       or the file matches exclude_file_patterns,
#                       which pgindent enforces internally)
#   *.pl / *.pm       → pgperltidy (best-effort; skipped silently if
#                       perltidy version != pinned 20230309)
#   anything else     → no-op exit 0
#
# Input:
#   PostToolUse mode reads JSON from stdin and extracts tool_input.file_path
#   via jq. --check mode takes the path as $2.

set -u

MODE="default"
FILE=""

# --- argument parsing ---------------------------------------------------------
case "${1:-}" in
  --check)
    MODE="check"
    FILE="${2:-}"
    ;;
  "")
    MODE="default"
    ;;
  *)
    # Treat any other single arg as a direct file path (escape hatch
    # for ad-hoc invocation; not used by the hooks).
    FILE="$1"
    ;;
esac

# --- repo root resolution -----------------------------------------------------
# CLAUDE_PROJECT_DIR is set by Claude Code when the hook fires. Outside the
# hook (e.g. pre-commit shell calling this script), fall back to walking up
# from this script's location.
if [ -z "${CLAUDE_PROJECT_DIR:-}" ]; then
  CLAUDE_PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
fi

DEV_ROOT="$CLAUDE_PROJECT_DIR/dev"
PGINDENT_BIN="$DEV_ROOT/src/tools/pgindent/pgindent"
PGINDENT_TYPEDEFS="$DEV_ROOT/src/tools/pgindent/typedefs.list"
PERLTIDY_PROFILE="$DEV_ROOT/src/tools/pgindent/perltidyrc"
PERLTIDY_PIN="20230309"

# --- telemetry helper ---------------------------------------------------------
# Emits a single-line JSON object on stdout in the shape Claude Code's
# PostToolUse hook documents as "additionalContext". In --check mode we
# emit human-readable text on stderr instead.
emit() {
  local msg="$1"
  if [ "$MODE" = "default" ]; then
    # Escape backslashes and quotes for JSON.
    local escaped
    escaped=${msg//\\/\\\\}
    escaped=${escaped//\"/\\\"}
    printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"%s"}}\n' "$escaped"
  else
    printf '%s\n' "$msg" >&2
  fi
}

# --- stdin extraction (default mode only) -------------------------------------
if [ "$MODE" = "default" ] && [ -z "$FILE" ]; then
  # Read JSON payload from stdin and pluck file_path. Quick-fail to exit 0
  # if jq is missing or the payload doesn't contain a path — we never
  # block edits, only annotate them.
  if ! command -v jq >/dev/null 2>&1; then
    exit 0
  fi
  PAYLOAD="$(cat || true)"
  if [ -z "$PAYLOAD" ]; then
    exit 0
  fi
  FILE="$(printf '%s' "$PAYLOAD" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)"
fi

if [ -z "$FILE" ]; then
  exit 0
fi

# --- path filter --------------------------------------------------------------
# Only act on files inside dev/src/ (or dev/contrib/) with C/H/Perl
# extensions. Anything else exits 0 silently so neither Claude nor the
# pre-commit gate ever blocks on unrelated edits.
case "$FILE" in
  "$DEV_ROOT"/src/*|"$DEV_ROOT"/contrib/*) : ;;
  */dev/src/*|*/dev/contrib/*)             : ;;
  *)
    exit 0
    ;;
esac

if [ ! -f "$FILE" ]; then
  exit 0
fi

case "$FILE" in
  *.c|*.h)   LANG_KIND="c" ;;
  *.pl|*.pm) LANG_KIND="perl" ;;
  *)         exit 0 ;;
esac

# --- C / H path: pgindent -----------------------------------------------------
if [ "$LANG_KIND" = "c" ]; then
  # pg_bsd_indent must be on PATH (or pointed to by PGINDENT). One-time
  # availability check — skip with telemetry if absent rather than fail.
  if ! command -v pg_bsd_indent >/dev/null 2>&1 \
       && ! { [ -n "${PGINDENT:-}" ] && command -v "$PGINDENT" >/dev/null 2>&1; }; then
    emit "pg-format: pg_bsd_indent not on PATH — skipping ${FILE##*/}. Build it via: ninja -C dev/build-debug src/tools/pg_bsd_indent/pg_bsd_indent"
    exit 0
  fi

  if [ ! -x "$PGINDENT_BIN" ]; then
    emit "pg-format: pgindent script not found at $PGINDENT_BIN — skipping"
    exit 0
  fi

  TYPEDEF_ARG=()
  if [ -f "$PGINDENT_TYPEDEFS" ]; then
    TYPEDEF_ARG=(--typedefs "$PGINDENT_TYPEDEFS")
  fi

  if [ "$MODE" = "check" ]; then
    # --check returns 2 on dirty per pgindent:6-10.
    if "$PGINDENT_BIN" "${TYPEDEF_ARG[@]}" --check "$FILE" >/dev/null 2>&1; then
      exit 0
    fi
    # Dirty — produce the diff for the pre-commit error output.
    TMP="$(mktemp -t pgfmt.XXXXXX)"
    trap 'rm -f "$TMP"' EXIT
    cp "$FILE" "$TMP"
    "$PGINDENT_BIN" "${TYPEDEF_ARG[@]}" "$TMP" >/dev/null 2>&1 || true
    printf 'pg-format: %s requires pgindent reformat:\n' "$FILE" >&2
    diff -u "$FILE" "$TMP" >&2 || true
    exit 1
  fi

  # Default (auto-fix) mode — rewrite in place. Capture line counts so
  # Claude knows whether anything actually changed.
  BEFORE_LINES="$(wc -l < "$FILE" | tr -d ' ')"
  TMP="$(mktemp -t pgfmt.XXXXXX)"
  cp "$FILE" "$TMP"
  if "$PGINDENT_BIN" "${TYPEDEF_ARG[@]}" "$FILE" >/dev/null 2>&1; then
    if ! cmp -s "$TMP" "$FILE"; then
      AFTER_LINES="$(wc -l < "$FILE" | tr -d ' ')"
      DIFF_LINES="$(diff -u "$TMP" "$FILE" | grep -c '^[+-][^+-]' || true)"
      emit "pg-format: pgindent reformatted ${DIFF_LINES} line(s) in ${FILE##*/} (was ${BEFORE_LINES} → now ${AFTER_LINES} lines)"
    fi
  else
    # pgindent failed; restore the pristine file rather than leaving a
    # half-rewritten copy on disk.
    cp "$TMP" "$FILE"
    emit "pg-format: pgindent failed on ${FILE##*/} — left file untouched"
  fi
  rm -f "$TMP"
  exit 0
fi

# --- Perl path: pgperltidy (best-effort) --------------------------------------
if [ "$LANG_KIND" = "perl" ]; then
  PERLTIDY_BIN="${PERLTIDY:-perltidy}"
  if ! command -v "$PERLTIDY_BIN" >/dev/null 2>&1; then
    emit "pg-format: perltidy not installed — skipping ${FILE##*/}"
    exit 0
  fi
  # Verify the pinned version. pgperltidy hard-fails on mismatch; we
  # mirror its check but skip-silently instead of failing.
  if ! "$PERLTIDY_BIN" -v 2>/dev/null | grep -q "$PERLTIDY_PIN"; then
    emit "pg-format: perltidy version != $PERLTIDY_PIN — skipping ${FILE##*/}"
    exit 0
  fi
  if [ ! -f "$PERLTIDY_PROFILE" ]; then
    emit "pg-format: perltidy profile missing at $PERLTIDY_PROFILE — skipping"
    exit 0
  fi

  if [ "$MODE" = "check" ]; then
    TMP="$(mktemp -t pgfmt.XXXXXX)"
    trap 'rm -f "$TMP"' EXIT
    "$PERLTIDY_BIN" --quiet --profile="$PERLTIDY_PROFILE" --standard-output < "$FILE" > "$TMP" 2>/dev/null || true
    if cmp -s "$FILE" "$TMP"; then
      exit 0
    fi
    printf 'pg-format: %s requires perltidy reformat:\n' "$FILE" >&2
    diff -u "$FILE" "$TMP" >&2 || true
    exit 1
  fi

  # Default mode — rewrite in place.
  TMP="$(mktemp -t pgfmt.XXXXXX)"
  "$PERLTIDY_BIN" --quiet --profile="$PERLTIDY_PROFILE" --standard-output < "$FILE" > "$TMP" 2>/dev/null || true
  if [ -s "$TMP" ] && ! cmp -s "$FILE" "$TMP"; then
    DIFF_LINES="$(diff -u "$FILE" "$TMP" | grep -c '^[+-][^+-]' || true)"
    cp "$TMP" "$FILE"
    emit "pg-format: perltidy reformatted ${DIFF_LINES} line(s) in ${FILE##*/}"
  fi
  rm -f "$TMP"
  exit 0
fi

exit 0
