# 2026-06-15 — Pre-compact handoff, round 5 run 3

This handoff supersedes the intra-run checkpoint at
`sessions/2026-06-15-handoff-post-compact-round5-run2.md` (PR
#299).  It captures the **full post-compact session** from PR
#294 through #302, including the parallel-query trio that
landed after the intra-run checkpoint.

The user's operative directive carried from the prior arc —
*"continue with all the next mentioned i tell u to stop"* —
was honored throughout.  The current pause was user-initiated
("prepare compact first") to enable a clean compact boundary.

## What this run produced — 7 PRs, all merged

| PR | Trio | LOC |
|---|---|---|
| #294 | SP-GiST (tree/tuples + insert+picksplit + scan+consistent) | 1,526 |
| #295 | Analyze + statistics (block/reservoir sampling + MCV/histogram/correlation + extended stats) | 1,621 |
| #296 | TIDBitmap (structure+lossy + build/iterate + AND/OR/Heap executor) | 1,736 |
| #297 | Logical-rep apply (loop+dispatch + DML handlers + streaming/parallel) | 1,711 |
| #298 | Snapshot management (static slots + stack/registered + export/historic/parallel) | 1,827 |
| #299 | Intra-run handoff (5-PR summary, superseded by this doc) | 309 |
| #302 | Parallel query coordination (context/DSM + launch/wait/errors + state propagation) | 1,886 |

**Total: 10,616 LOC across 19 new files (18 idiom docs + 1
handoff).**

Average ~561 LOC per idiom doc — slightly above the
established ~440 target, reflecting these being depth-trios
on subsystems with substantial internal structure.  All PR
anti-target audits clean.

## Current state on main

- **Open PRs:** 0
- **Anchor on `source/`:** `e18b0cb7344` (unchanged across the
  whole run)
- **Corpus on main:** the count grew by 18 idiom docs this run.
  Pre-run baseline (per prior pre-compact handoff): ~128
  idiom docs.  Post-run: ~146.
- **Methodology**: steady-state corpus mining loop validated
  again — 18/18 docs landed clean, 7/7 PRs merged on first
  attempt.
- **Phase D**: unchanged (PARKED — 5 patches in `patches/`
  need explicit re-auth from user).

## What got covered, briefly

### PR #294 — SP-GiST depth trio (1,526 LOC)

Space-partitioned GiST end-to-end: README + `spgist_private.h`
structs + `spgdoinsert.c` + `spgscan.c`.  Documented the
LIVE/REDIRECT/DEAD/PLACEHOLDER tuple-state alphabet, the
choose/picksplit/AddNode/SplitTuple dispatch, the
pairing-heap that doubles as DFS stack and KNN priority
queue, and the triple-parity trick that keeps deadlocks rare.

Files: `spgist-tree-and-tuples.md` (487),
`spgist-insert-and-picksplit.md` (471),
`spgist-scan-and-consistent.md` (568).

### PR #295 — Analyze + statistics depth trio (1,621 LOC)

`acquire_sample_rows` two-stage sampling (Knuth Algorithm S +
Vitter Algorithm Z), 300×attstattarget rationale, `std_typanalyze`
dispatch, tupnoLink side-effect-during-qsort trick,
statistical MCV cutoff via hypergeometric 2-σ test, Bresenham
equi-depth histogram, closed-form Pearson correlation; plus
extended-statistics four kinds (d/f/m/e), Duj1 ndistinct
estimator, soft-functional-dependency multi-sort.

Files: `analyze-block-and-reservoir-sampling.md` (520),
`analyze-mcv-histogram-correlation.md` (535),
`extended-statistics-statext.md` (566).

### PR #296 — TIDBitmap depth trio (1,736 LOC)

`PagetableEntry` bit-packed header, TBM_EMPTY/ONE_PAGE/HASH
lifecycle, `PAGES_PER_CHUNK` arithmetic, lossy/exact storage,
recheck flag propagation, `tbm_add_tuples`
currblk-optimization + lossify-then-invalidate dance, three-way
union/intersect branching, lossify half-budget +
skip-chunk-boundary + admit-defeat, private vs. shared
iteration (DSA index arrays + LWLock cursor), MultiExecProcNode
convention, BitmapAnd first-child-in-place + empty
short-circuit, BitmapOr streaming optimization, BitmapHeapScan
recheck handshake + MVCC-only restriction.

Files: `tidbitmap-structure-and-lossy.md` (551),
`tidbitmap-build-and-iterate.md` (662),
`bitmap-and-or-heap-executor.md` (523).

### PR #297 — Logical-rep apply depth trio (1,711 LOC)

`LogicalRepApplyLoop` outer/inner loop, three transport
message types, `apply_dispatch` recursive save/restore for
spooled replay, two-context memory model, gated
between-transactions maintenance, common handler skeleton
(skip checks, REPLICA IDENTITY updatability, updatedCols
tracking), `slot_modify_data` UNCHANGED/TOASTED preservation,
cross-origin conflict detection, missing-vs-deleted
classification, partition tuple routing,
`TransApplyAction` five-way enum, parallel apply DSM + shm_mq
with deadlock-detection lock graph, subxact-info file
truncation.

Files: `apply-worker-loop-and-dispatch.md` (527),
`apply-handlers-insert-update-delete.md` (595),
`apply-streaming-and-parallel.md` (589).

### PR #298 — Snapshot management depth trio (1,827 LOC)

Six static `SnapshotData` slots,
`GetTransactionSnapshot` three-mode dispatch,
`GetCatalogSnapshot` reuse pattern with manual heap add,
`InvalidateCatalogSnapshot` inval-callback hookup,
`TransactionXmin` vs `RecentXmin` distinction, dual refcount
model (`active_count` + `regd_count`),
`PushActiveSnapshot` static-slot auto-copy,
`ActiveSnapshotElt.as_level` invariant,
`RegisteredSnapshots` pairing heap with `xmin_cmp`,
`SnapshotResetXmin` skip-if-active-not-empty optimization,
`AtSubAbort_Snapshot` stack pop by level,
pg_snapshots text file format,
`SetupHistoricSnapshot` logical-decoding catalog shadow,
tuplecid (cmin, cmax) hash, `SerializedSnapshotData`
parallel-worker wire format, single-allocation
`RestoreSnapshot` layout.

Files: `snapshot-static-and-current.md` (575),
`snapshot-active-stack-and-registered.md` (696),
`snapshot-export-historic-parallel.md` (556).

### PR #302 — Parallel query coordination depth trio (1,886 LOC)

`IsInParallelMode` contract, `ParallelContext` struct with
`nworkers` / `nworkers_to_launch` / `nworkers_launched`,
`TopMemoryContext` fallback when DSM fails,
four-phase `InitializeParallelDSM`,
`FixedParallelState` fields, `PARALLEL_KEY_*` registry with
framework-reserved high bits, per-session DSM for RECORD
typmod registry, `ReinitializeParallelDSM` cheap relaunch,
`BecomeLockGroupLeader` prerequisite, `BackgroundWorker`
template with `BgWorkerStart_ConsistentState`,
`bgw_function_name="ParallelWorkerMain"` always, `bgw_extra`
carrying worker number, three-state attach polling,
Finish vs Exit distinction, async error path via
`ParallelMessagePending` flag + `ProcessParallelMessages`,
four message types (Error/Notice / Notification / Progress /
Terminate), worker-FATAL capped at leader-ERROR, AtEOXact
warn-on-leak; 26-step `ParallelWorkerMain` boot sequence,
`BecomeLockGroupMember` gate before any heavyweight lock,
identity restoration in three layers, library load inside
its own tx, four catalog-affecting states (PendingSyncs /
RelationMap / ReindexState / ComboCIDState),
`AttachSession` for typmod registry, snapshot restore +
`InvalidateSystemCaches` order, GUC restore after catalog
state and snapshot, `pq_redirect_to_shm_mq` making elog
transparent, `ParallelWorkerReportLastRecEnd` spinlocked WAL
coordination.

Files: `parallel-context-and-dsm.md` (530),
`parallel-worker-launch-wait-and-errors.md` (625),
`parallel-state-propagation.md` (731).

## Methodology — unchanged from prior arc, validated again

The steady-state corpus-mining loop continues to work
reliably:

1. **Pick adjacent gap** from the prior handoff's catalog.
2. **Refresh main + new worktree** from current main.
3. **Symlink `source/` and `dev/` into worktree.**
4. **Read at anchor `e18b0cb7344`**: README first where one
   exists, then key .c files (entry points + structural
   blocks).
5. **Triple-doc shape**: 3 docs averaging ~440-700 LOC each,
   covering distinct facets.
6. **Confidence tags** throughout:
   `[verified-by-code]` / `[from-comment]` / `[from-README]` /
   `[unverified]`.
7. **Cross-refs liberally** to existing corpus + to siblings
   in this trio.
8. **Per-PR anti-target audit before commit**:
   `git diff --stat origin/main..HEAD -- <8 paths>`.
9. **Merge immediately** to keep queue at 0.

LOC inflation (~561 avg vs. ~440 target) reflects covering
substantial subsystems where brevity would have lost detail.
No regression in cite density or structure.  The 18 docs
landed clean on first PR — no follow-up fixups required.

## Adjacent gaps remaining (round-5 catalog)

Strikethrough = covered this session; rest are still open.

- ~~SP-GiST internals~~ ✓ #294
- ~~TID scan + bitmap heap scan integration~~ ✓ #296
- ~~Logical replication apply worker depth~~ ✓ #297
- ~~Snapshot management depth~~ ✓ #298
- ~~Statistics target + analyze sampling~~ ✓ #295
- ~~Parallel query coordination~~ ✓ #302
- **Subxact handling depth** — XidCache /
  committed-xids / subxact stack, PGPROC.subxids[] mechanics,
  lock conflict on parent-vs-subxact xids.
  - Note: `subtransaction-stack.md` exists at 26K but a depth
    trio could still split into per-mechanism docs.
- **CHECK / NOT NULL / foreign-key constraint enforcement**
  — RI trigger generation, constraint exclusion in planner,
  deferred vs immediate.
  - Note: FK triggers already covered in #276; CHECK constraint
    machinery is the missing piece.
- **Memory contexts depth** — AllocSet / BumpContext / Slab
  / Generation context internals, chunk-header bit packing,
  per-context callback chains.
  - Note: `memory-contexts.md` exists at 12.8K but a per-context
    depth trio (AllocSet / Slab+Generation / BumpContext+ASan)
    would fit the established pattern.
- **Type-cache depth** — typcache.c TypeCacheEntry mechanics,
  composite-type RECORD typmod registry, equality / hash /
  comparison operator resolution.

Plus from the round-4 catalog:

- **TOAST round 2** — chunk-fetch-table-am /
  compression-pglz-vs-lz4 / decompression-streaming-callers.
  TOAST round 1 covered varatt + chunk write + detoast in
  PR #273.  Round 2 would dig deeper into compression
  algorithms + streaming paths.

**4 of 10 round-5 adjacent gaps remain.**

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

## The stale-plan situation (unchanged from intra-run checkpoint)

At the start of this run, the post-compact context contained a
plan file at `.claude/plans/use-this-repo-u-idempotent-spindle.md`
proposing a 4-PR sweep of `/skill-creator:skill-creator` over
all 27 skills.  The 5 cluster branches it described
(`ft_skills_workflow_tooling`, `ft_skills_planner_suite`,
`ft_skills_patch_review`, `ft_skills_domain_knowledge`,
`ft_knowledge_contrib_docs`) all exist on origin but **were
never PR'd** — and the work has since been **superseded** via
other paths.

Inspection of `ft_skills_workflow_tooling` showed its diff
against current main would REVERT a large amount of merged
work (it deletes `bgworker-and-extensions/SKILL.md` and
re-adds `gucs-bgworker-parallel/SKILL.md` — but the SPLIT was
done by other PRs that landed first).

**Decision**: do NOT PR the 5 stale branches.  They're left
on origin for forensic value but should be considered
abandoned.  If the user wants the skill-creator sweep
re-done, it must start from current main.

## Cloud-routine activity during this run

Two PRs landed from cloud routines between my PRs:
**#300 and #301** (numbering gap between #299 and #302).  I
did not inspect them — assumed to be the standard
pg-anchor-refresh / pg-state-keeper / pg-evening-merger
cadence.  Anchor on `source/` did not change, so they were
not anchor refreshes.  Anti-target paths are exclusively
their lane; my work hasn't touched them.

## Post-compact resume checklist

1. **Read this doc** at
   `sessions/2026-06-15-handoff-pre-compact-round5-run3.md`.
2. `git fetch origin && git log --oneline -10` to see what
   merged overnight.
3. Verify anchor: `git -C ../../postgresql rev-parse HEAD`
   should be `e18b0cb7344` (unless `/refresh-upstream` ran).
4. Confirm 0 open PRs:
   `gh pr list --state open --json number | python3 -c
   'import json,sys; print(len(json.load(sys.stdin)))'`.
5. Pick the next trio from remaining adjacent gaps:
   - **Memory contexts depth** — strong candidate; multiple
     recent docs (every parallel/snapshot/apply doc) reference
     memory-context patterns, so depth here would tie the
     corpus together.
   - **Type-cache depth** — coherent single-subsystem dig
     (typcache.c is ~3K lines).
   - **TOAST round 2** — close the round-4 catalog item.
   - **Subxact depth** — split the existing
     `subtransaction-stack.md` into mechanism-specific docs.
   - **CHECK constraints** — fills the constraint gap left
     by #276 (FK only).
   - Or follow a user-directed pivot.
6. Apply the established per-PR pattern (anchor → read source
   → write 3 docs ~440-700 LOC each → anti-target audit →
   commit → push → PR → merge).

## What the user has NOT authorized (hold the line)

- **Phase D send to pgsql-hackers** — staged patches stay
  parked.
- **`pip install anthropic` or `claude-agent-sdk`** —
  requires explicit OK.
- **Touching anti-target paths** — never.
- **PR'ing the 5 stale `ft_skills_*` branches** — would
  revert merged work.

## TL;DR for post-compact-Claude

This run: 6 corpus depth-trios + 1 intra-run handoff = 7 PRs
merged, 10,616 LOC across 19 files.  Each PR was a coherent
depth-trio for one subsystem.  Adjacent-gap catalog from
round 5 is now 6/10 cleared.  Methodology unchanged: ~440-700
LOC per doc, README + key .c files at anchor `e18b0cb7344`,
anti-target audit per commit, immediate merge.

Resume by picking from the remaining adjacent gaps: memory
contexts depth, type-cache depth, TOAST round 2, subxact
depth, CHECK constraints.  Or follow user-directed pivot.

Anchor at `e18b0cb7344`.  0 open PRs.  Anti-targets clean.
Don't break the rules.
