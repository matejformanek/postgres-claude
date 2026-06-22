#!/bin/bash
# pg-phase-detect.sh — derive an R13-aware meson test suite list from
# the active branch + planning notes.md + staged file paths.
#
# Output: space-separated bare meson suite names (e.g. "regress isolation
# pg_stat_statements"). Default on detection failure: "regress".
#
# Used by pg-precommit.sh stage B to scope the per-commit test run to
# the phase's blast radius per .claude/rules/pg-implement-discipline.md R13.

set -u

if [ -z "${CLAUDE_PROJECT_DIR:-}" ]; then
  CLAUDE_PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
fi

# Worktree-aware DEV_ROOT discovery (see pg-precommit.sh for rationale).
# When called from pg-precommit.sh stage B, $PWD is the working tree
# root that git fired the pre-commit hook in; for a worktree commit
# this is the worktree's own root, not the canonical main clone.
if [ -n "${PG_HOOK_DEV_ROOT:-}" ]; then
  DEV_ROOT="$PG_HOOK_DEV_ROOT"
elif DEV_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" && [ -n "$DEV_ROOT" ]; then
  :
else
  DEV_ROOT="$CLAUDE_PROJECT_DIR/dev"
fi
PLANNING_ROOT="$CLAUDE_PROJECT_DIR/planning"

# --- staged file list --------------------------------------------------------
# `git rev-parse --git-dir` works for both regular clones and worktrees,
# so a simple `git -C "$DEV_ROOT" diff --cached` always indexes the
# right ref store regardless of whether DEV_ROOT is main or a worktree.
STAGED="$(git -C "$DEV_ROOT" diff --cached --name-only --diff-filter=ACM 2>/dev/null || true)"

# --- phase number from notes.md (informational) ------------------------------
# The pg-implement skill appends a "Plan-phase: N" trailer to each phase
# entry in planning/<slug>/notes.md. We pick the LAST one across all
# notes.md files. Used for telemetry only — the suite list is path-driven.
PHASE_NUM=""
if [ -d "$PLANNING_ROOT" ]; then
  for nf in "$PLANNING_ROOT"/*/notes.md; do
    [ -f "$nf" ] || continue
    last="$(grep -E '^Plan-phase:[[:space:]]*[0-9]+' "$nf" 2>/dev/null | tail -n1 | awk '{print $2}')"
    if [ -n "$last" ]; then
      PHASE_NUM="$last"
    fi
  done
fi

# --- tier detection ----------------------------------------------------------
# Walk the staged paths once; flip tier flags. Broadest match wins,
# composed at the end. Suite name choices follow source/meson.build and
# each contrib/*/meson.build 'name:' field (bare names, no prefix).

tier_recovery=0
tier_isolation=0
tier_ecpg=0
tier_contrib=0
tier_ruleutils=0

while IFS= read -r path; do
  [ -n "$path" ] || continue
  case "$path" in
    # WAL / replication / xlog → recovery
    src/backend/access/transam/xlog*|\
    src/backend/access/transam/twophase*|\
    src/backend/replication/*|\
    src/include/access/xlog*|\
    src/include/replication/*)
      tier_recovery=1
      tier_isolation=1
      tier_contrib=1
      ;;
    # Grammar / lexer → ecpg
    src/backend/parser/gram.y|\
    src/backend/parser/scan.l|\
    src/pl/plpgsql/src/pl_gram.y|\
    src/pl/plpgsql/src/pl_scanner.l|\
    src/interfaces/ecpg/preproc/*)
      tier_ecpg=1
      tier_contrib=1
      ;;
    # Executor / planner → isolation + contrib
    src/backend/executor/execExpr*.c|\
    src/backend/executor/node*.c|\
    src/backend/optimizer/util/clauses.c|\
    src/backend/utils/cache/plancache.c|\
    src/backend/optimizer/*)
      tier_isolation=1
      tier_contrib=1
      ;;
    # ruleutils → spot-check tier
    src/backend/utils/adt/ruleutils.c)
      tier_ruleutils=1
      tier_contrib=1
      ;;
    # Catalog data / headers → contrib (R13 catalog tier)
    src/include/catalog/pg_*.dat|\
    src/include/catalog/pg_*.h)
      tier_contrib=1
      ;;
  esac
done <<EOF
$STAGED
EOF

# --- compose suite list ------------------------------------------------------
# Start with regress (always present), append broader tiers.
suites="regress"
if [ $tier_isolation -eq 1 ]; then
  suites="$suites isolation"
fi
if [ $tier_ecpg -eq 1 ]; then
  suites="$suites ecpg"
fi
# pg_stat_statements is the canonical contrib watchdog (catalog edits
# break it first; sesvars F12).
if [ $tier_contrib -eq 1 ]; then
  suites="$suites pg_stat_statements"
fi
if [ $tier_recovery -eq 1 ]; then
  suites="$suites recovery"
fi

# Emit telemetry to stderr (pre-commit prints this); suite list to stdout.
{
  if [ -n "$PHASE_NUM" ]; then
    echo "pg-phase-detect: Plan-phase $PHASE_NUM, suites: $suites"
  else
    echo "pg-phase-detect: no Plan-phase marker, suites: $suites"
  fi
  if [ $tier_ruleutils -eq 1 ]; then
    echo "pg-phase-detect: ruleutils.c staged — spot-check CREATE VIEW / EXPLAIN VERBOSE / pg_get_*def after commit"
  fi
} >&2

echo "$suites"
