# 2026-06-02 — corpus-maintainer (run 2): glossary +15

## What I did
- Re-ran `pg-corpus-maintainer` (recipe `.claude/cloud/pg-corpus-maintainer.md`)
  on branch `cloud/pg-corpus-maintainer/2026-06-02`, after run 1 (PR #13) was
  already merged to `main` by pg-evening-merger (#18).
- Pass 1 (backlinks): idempotent no-op — 0 `[[...]]` wikilinks, all 652
  source-path backlinks from run 1 present.
- Pass 2 (glossary): grew `knowledge/glossary.md` 15 → 30 entries. Added the
  next top-15 most-frequent undefined internals terms by corpus doc-frequency.

## What I learned
- The corpus-maintainer is designed to grow the glossary by ~15 terms per run;
  re-running the same day simply advances Pass 2 while Pass 1 stays flat.
- A purely mechanical CamelCase/ALL_CAPS tokenizer **misses `LWLock`** (two
  leading caps then lowercase fits neither pattern), despite it being a
  load-bearing term. Frequency-driven term selection needs a hand-curated
  jargon list as a safety net; logged `LWLock` for next run explicitly.
- Generic `slot` ranks high (179) but is ambiguous (`TupleTableSlot` vs
  replication slot); skipped rather than define imprecisely.

## What I'm unsure about
- Whether two runs sharing a calendar-day branch name is intended; the prior
  branch was deleted on merge so the name was free to reuse, but the run log
  needed a "run 2" section to avoid clobbering the audit trail.

## Pointers left for next time
- Next glossary batch: `LWLock`, `MemoryContext`, `BLCKSZ`, `ResourceOwner`,
  `RelOptInfo`, `AllocSet`, `BlockNumber`, `SLRU`, `PlannerInfo`/`PlannedStmt`,
  scoped `replication slot`.
- Quality pass still pending from run 1: prune spurious `optimizer.md`
  basename-era backlinks (e.g. `walsender.c.md`, `postgres.c.md`).
