# 2026-06-15 — Pre-compact handoff round 5

**Operative directive from the user, verbatim (most recent):**

> after being done with this iteration lets stop for compact

Before the prior message, user said "continue with all the next
mentioned i tell u to stop" — i.e. work through the corpus mining
catalog one trio at a time, autonomously, until told to stop. The
"stop for compact" message was received mid-JIT trio; that trio
was completed and merged before this handoff.

## What this session produced — 9 PRs, all merged

| PR | Trio | LOC |
|---|---|---|
| #284 | SLRU depth (page-replacement / CLOG / MultiXact dual) | 1,090 |
| #285 | MVCC depth (visibility gauntlet / hint bits / freeze) | 1,230 |
| #286 | Vacuum depth (HOT prune / TidStore / 3-phase orchestration) | 1,381 |
| #287 | Syscache depth (catcache / relcache / invalidation flow) | 1,551 |
| #288 | BRIN AM (revmap / tuple format / summarize+scan) | 1,405 |
| #289 | GIN AM (tree structure / fastupdate / scan+consistent) | 1,367 |
| #290 | Hash AM (page layout / bucket split / overflow pages) | 1,302 |
| #291 | Aggregate strategies (hash-vs-sort / grouping sets / partial-finalize) | 1,416 |
| #292 | JIT depth (provider+context / expression codegen / deform+inline) | 1,307 |

**Total: 12,049 LOC across 27 new idiom docs in 9 PRs.**

Average ~447 LOC per doc, ~1340 LOC per PR. All anti-target
audits clean. Cross-refs linked throughout, including back-links
to previously-existing docs ([[expression-evaluator-flow]],
[[parallel-bitmap-heap]], [[heap-tuple-visibility-mvcc]],
[[cost-units-gucs]], [[cache-invalidation-registration]],
[[sinvaladt-broadcast]], etc.).

## Current state on main

- **Open PRs:** 0
- **Anchor on `source/`:** `e18b0cb7344` (unchanged)
- **Corpus on main:** the count grew by 27 idiom docs this session.
  Pre-session: ~101 idiom docs (per round-4 handoff). Post: ~128.
- **Methodology**: established consistent ~440-LOC-per-doc rhythm
  with the structure Anchors → struct/flow → field commentary →
  Invariants → Useful greps → Cross-references.
- **Phase D**: unchanged (PARKED — 5 patches in `patches/` need
  explicit re-auth from user).

## Methodology that emerged

This session validated a steady-state corpus-mining loop:

1. **Catalog candidate**: pick from the round-4 handoff's
   mining catalog (10 trio candidates listed).
2. **Read sources at anchor `e18b0cb7344`**: README first (where
   exists — BRIN, GIN, Hash, JIT all have great READMEs), then
   key .c files (entry points + structural blocks).
3. **Triple-doc shape**: ~440 LOC each, covering distinct
   facets of the subsystem.
4. **Confidence tags**: `[verified-by-code]` for cite-resolved
   claims, `[from-comment]` for banner/inline-doc claims,
   `[unverified]` for things I'd need a deeper read on.
5. **Cross-refs liberally**: link to existing corpus docs;
   document the link even if the target doesn't exist yet.
6. **Per-PR anti-target audit before commit**: `git diff --stat
   origin/main..HEAD -- <8 paths>` must be empty.
7. **Merge immediately** to keep queue at 0; user values steady
   merge pace over batching.

The "Anchors" section at the top of each doc is the cite manifest;
the "Useful greps" at the bottom provides reproducible navigation.

## What's left in the mining catalog

| Trio | Loci | Status |
|---|---|---|
| SLRU depth | clog/multixact/page-replacement | **done (PR #284)** |
| JIT compilation depth | llvm-emit/tuple-deform/expression-compile | **done (PR #292)** |
| BRIN AM internals | tuple-format/summarize/revmap | **done (PR #288)** |
| GIN AM internals | tuple-format/fastupdate/vacuum | **done (PR #289)** |
| Hash AM internals | page-format/bucket-split/overflow | **done (PR #290)** |
| Syscache | cache-tuple/invalidation/relcache | **done (PR #287)** |
| Aggregate strategies | hash-vs-sort/grouping-sets/partial-finalize | **done (PR #291)** |
| TOAST round 2 | chunk-fetch-table-am / compression-pglz-vs-lz4 / decompression-streaming-callers | not started |
| Vacuum depth | prune/freeze/dead-tid-array | **done (PR #286)** |
| MVCC depth | xmin-xmax-cmin-cmax / hint-bits / heap-tuple-visibility-algorithm | **done (PR #285)** |

**Only TOAST round 2 remains from the round-4 catalog.**

## Adjacent gaps to consider for next session

If extending the catalog past TOAST round 2, candidate trios that
match the corpus's depth target:

- **SP-GiST internals** — quadrant/k-d tree page layout, inner
  tuple format, range search.
- **TID scan + bitmap heap scan integration** — TIDBitmap struct
  (lossy vs exact, page-vs-tuple representation), `tbm_add_tuples`
  vs `tbm_add_page`, BitmapHeapScan's recheck integration.
- **Logical replication apply worker depth** — apply_worker_main
  loop, message dispatch, conflict detection, two-phase
  decoding internals.
- **Snapshot management depth** — GetSnapshotData internals,
  procarray scanning, snapshot stack, PortalSnapshot vs
  ActiveSnapshot vs CatalogSnapshot.
- **Parallel query coordination** — Gather setup,
  ParallelContext + DSM segments, parallel_safe propagation
  through paths.
- **Subxact handling depth** — XidCache / committed-xids /
  subxact stack, PGPROC.subxids[] mechanics, lock conflict on
  parent-vs-subxact xids.
- **Statistics target + analyze sampling** — vacuum_random_seed
  + reservoir sampling, MCV vs histogram + correlation, extended
  statistics dependencies.
- **CHECK / NOT NULL / foreign-key constraint enforcement** — RI
  trigger generation, constraint exclusion in planner, deferred
  vs immediate.
- **Memory contexts depth** — AllocSet / BumpContext / Slab /
  Generation context internals, chunk-header bit packing,
  per-context callback chains.
- **Type-cache depth** — typcache.c TypeCacheEntry mechanics,
  composite-type RECORD typmod registry, equality / hash /
  comparison operator resolution.

## Anti-target paths (reminder — NEVER touch in foreground work)

```
knowledge/calibration/**
knowledge/personas/**
knowledge/files/**
patches/**
progress/STATE.md             (except consolidation PRs)
progress/cloud-routines/**    (cloud-routine lane only)
CLAUDE.md
pg-claude-plan.md
```

Pre-commit check (run before every commit):

```bash
git diff --stat origin/main..HEAD -- \
    knowledge/calibration knowledge/personas knowledge/files \
    patches progress/STATE.md progress/cloud-routines \
    CLAUDE.md pg-claude-plan.md
```

Empty = clean. Non-empty = STOP and re-think.

## Post-compact resume checklist

1. **Read this doc** at `sessions/2026-06-15-handoff-pre-compact-round5.md`.
2. `git fetch origin && git log --oneline -10` to see what
   merged overnight (cloud routines, if any).
3. Verify anchor: `cat ../../postgresql/.git/HEAD` or
   `git -C ../../postgresql rev-parse HEAD` should be
   `e18b0cb7344` (unless `/refresh-upstream` ran).
4. Confirm 0 open PRs:
   `gh pr list --state open --json number | python3 -c
   'import json,sys; print(len(json.load(sys.stdin)))'`.
5. Pick the next trio:
   - **TOAST round 2** to close the round-4 catalog, OR
   - One of the new adjacent gaps listed above, OR
   - A different direction if user signals one.
6. Apply the established per-PR pattern (anchor → read source →
   write 3 docs ~440 LOC each → anti-target audit → commit →
   push → PR → merge).

## What the user has NOT authorized (hold the line)

- **Phase D send to pgsql-hackers** — staged patches stay
  parked.
- **`pip install anthropic` or `claude-agent-sdk`** — requires
  explicit OK.
- **Touching anti-target paths** — never.

## One accidental write to source/ noted, immediately reverted

During the aggregate trio, I called `Write` on
`/Users/matej/Work/postgres/postgresql/src/backend/executor/nodeAgg.c`
with empty contents (an off-by-one accident with the tool path).
Immediately reverted via `git checkout` on the upstream tree. The
`source/` symlink points to a read-only PG clone; that clone now
shows a clean working tree (verified). Worth keeping the tool
discipline in mind: **never Write to `source/`**; all writes must
go through the worktree's `knowledge/` or `progress/` paths.

## TL;DR for post-compact-Claude

This session: 9 PRs merged, 12,049 LOC of new corpus docs across
27 idiom files. Each PR was a coherent depth-trio for one
subsystem. The mining catalog from round-4 is now ~9/10 cleared
(only TOAST round 2 remains). Methodology validated: ~440 LOC
per doc, README + key .c files at anchor e18b0cb7344, anti-target
audit per commit, immediate merge.

Resume by picking either TOAST round 2 (close the catalog) or
one of the adjacent gaps (SP-GiST / TIDBitmap / logical-rep apply
/ snapshot mgmt / parallel coordination / subxact / statistics /
constraints / memory contexts depth / type cache depth).

Anchor at e18b0cb7344. 0 open PRs. Anti-targets clean. Don't
break the rules.
