---
name: pg-corpus-graph-refresh
schedule: "17 4 * * * Europe/Prague"
fetches_source_via_url: false
queue: null
output_dirs: [knowledge, knowledge/idioms, knowledge/scenarios, knowledge/subsystems, progress]
skills_required: [pg-claude, memory-keeping]
max_input_tokens: 60000
max_output_tokens: 20000
---

# pg-corpus-graph-refresh

**Purpose.** Keep the pg-claude knowledge graph's five auto-generated
edge layers in sync with the current corpus prose. Every night, re-run
the five extractors in order and open a PR if anything changed.

The graph edges maintained here:

1. **Idiom → file (primary)** — `## Call sites` blocks in
   `knowledge/idioms/*.md`, extracted from inline `source/<path>:<line>`
   cites. Script: `scripts/populate-idiom-callsites.py`.
2. **Data-structure → file** — same script with `--layer
   data-structures`; populates `## Call sites` in
   `knowledge/data-structures/*.md` from the same evidence format.
3. **Idiom → file (v2, glossary-based)** — for the 4 identifier-only
   idioms (fmgr, node-types-and-lists, parser-pipeline, spi) where
   the primary extractor finds zero cites. Script:
   `scripts/populate-idiom-callsites-v2.py`.
4. **Subsystem → file** — `## Files owned` blocks in
   `knowledge/subsystems/*.md`, derived from slug → directory
   mapping + include-header filters. Script:
   `scripts/populate-subsystem-files.py`.
5. **Scenario ↔ idiom** — `## Idioms invoked` (scenarios) +
   `## Scenarios that use me` (idioms) + central
   `progress/scenario-idiom-matrix.md`. Union of direct refs +
   transitive file-overlap. Script:
   `scripts/build-scenario-idiom-matrix.py`.

The `corpus-chain` query engine (`scripts/corpus-chain.py`) reads
these blocks live — it doesn't need its own generator step.

## Why this exists

The five scripts are idempotent. Left alone, they don't drift the
graph on their own. But the SOURCE material drifts constantly:

- Interactive sessions edit idioms (add call-site cites in prose).
- `pg-file-backfiller` (retired 2026-06-15) and the `pg-anchor-refresh`
  routine change file docs in ways that could add new subsystem-owned
  files or invalidate old ones.
- `pg-quality-auditor` fixes drift in per-file cites — the corresponding
  idiom Call sites need re-derivation.
- Interactive scenario edits can add new `Files:` rows.

Without a nightly re-run, the auto-blocks become slightly stale.
Downstream (`corpus-chain` queries) sees fewer edges than exist.

## Scheduling rationale

Runs at 04:17 — after `pg-anchor-refresh` (03:37) has bumped the
anchor and queued audits, before `pg-state-keeper` (05:43) briefs.
Runs BEFORE `pg-quality-auditor` (variable time) so a fresh
quality-audit run sees the freshly refreshed graph.

## Method

1. **Setup.** Confirm on `main`, no local changes. Run `git pull`.

2. **Run all refreshers.**

   ```bash
   python3 scripts/populate-idiom-callsites.py > /tmp/refresh-1.log
   python3 scripts/populate-idiom-callsites.py --layer data-structures > /tmp/refresh-2.log
   python3 scripts/populate-idiom-callsites-v2.py > /tmp/refresh-3.log
   python3 scripts/populate-subsystem-files.py > /tmp/refresh-4.log
   python3 scripts/build-scenario-idiom-matrix.py > /tmp/refresh-5.log
   ```

   Capture each script's stdout for the run log.

3. **Diff check.** Run `git status --short`. If empty, log
   `exit_reason: no-change` and exit clean.

4. **Sanity check.** If diff is non-empty:
   - `git diff --stat` — should show only:
     - `knowledge/idioms/*.md` (blocks between callsites markers +
       scenarios markers)
     - `knowledge/scenarios/*.md` (blocks between idioms-invoked markers)
     - `knowledge/subsystems/*.md` (blocks between files-owned markers)
     - `progress/scenario-idiom-matrix.md`
   - Anything outside these paths → STOP + log as anomaly. Do NOT
     commit. This routine touches only auto-blocks.
   - Verify no file's total diff exceeds ±80 lines (would be
     abnormal drift for a graph refresh — flag for interactive
     review).

5. **Compute deltas for the PR body.** For each script, extract from
   its log:
   - Idiom callsites: X idioms updated, Y new call sites total.
   - Idiom callsites v2: X of 4 idioms updated.
   - Subsystems: X of 65 subsystems updated.
   - Matrix: X scenario→idiom edges, Y zero-idiom scenarios,
     Z zero-scenario idioms.

6. **Commit + PR.** Single commit, single PR. Title format:

   ```
   [cloud:pg-corpus-graph-refresh] N-file graph refresh (<X idioms · Y scenarios · Z subsystems>)
   ```

   Body summarizes the deltas + links to the run log. Merge-safe:
   pure auto-block edits, no prose changes.

## Anti-patterns

- **Do NOT touch prose outside auto-blocks.** If a script produces a
  diff outside a marker block, that's a script bug, not corpus drift.
  STOP and file an issue.
- **Do NOT run the scripts in a different order.** The chain matrix
  reads the idiom Call-sites tables — refresh those FIRST or the
  transitive edges will be stale.
- **Do NOT rerun steps in isolation.** If step 3 fails, don't just
  re-run step 3 — re-run the whole chain in order. Order-independent
  claims aren't proven.

## Failure modes

- **Python not available** — log + email operator. This shouldn't
  happen in the cloud env but is possible.
- **A script diverges from prior structure** — e.g. someone changes
  the marker text. Compare against the last successful run's diff
  shape; if unusual, STOP.
- **Merge conflict at commit time** — someone edited an auto-block
  by hand mid-window. The correct answer is: the SCRIPT wins. The
  by-hand edit was going to be overwritten on next refresh anyway.
  Rebase, drop the by-hand hunk, re-commit.

## Cross-references

- `scripts/populate-idiom-callsites.py` — primary extractor.
- `scripts/populate-idiom-callsites-v2.py` — glossary-based v2.
- `scripts/populate-subsystem-files.py` — subsystem → files.
- `scripts/build-scenario-idiom-matrix.py` — join builder.
- `scripts/corpus-chain.py` — the query engine that reads all four
  layers live.
- `.claude/skills/corpus-chain/SKILL.md` — how to interpret query output.
