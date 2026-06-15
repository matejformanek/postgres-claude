# 2026-06-15 — Post-compact resume, round-5 run 2

This session is the **post-compact continuation** of the round-5
arc.  The prior handoff at
`sessions/2026-06-15-handoff-pre-compact-round5.md` captured 9
PRs (#284-#292) plus the handoff itself (#293).  Round 5
finished with TOAST round 2 left as the only catalog item and
10 adjacent gaps listed.

The user's operative directive from the prior arc — *"continue
with all the next mentioned i tell u to stop"* — was carried
into this run.  No "stop" was issued; this checkpoint is
proactive to bound context use across compacts.

## What this run produced — 5 PRs, all merged

| PR | Trio | LOC |
|---|---|---|
| #294 | SP-GiST (tree/tuples + insert+picksplit + scan+consistent) | 1,526 |
| #295 | Analyze + statistics (block/reservoir sampling + MCV/histogram/correlation + extended stats) | 1,621 |
| #296 | TIDBitmap (structure+lossy + build/iterate + AND/OR/Heap executor) | 1,736 |
| #297 | Logical-rep apply (loop+dispatch + DML handlers + streaming/parallel) | 1,711 |
| #298 | Snapshot management (static slots + stack/registered + export/historic/parallel) | 1,827 |

**Total: 8,421 LOC across 15 new idiom docs in 5 PRs.**

Average ~561 LOC per doc — slightly above the established
~440 target, reflecting these being depth-trios on subsystems
with substantial internal structure.  All PR anti-target audits
clean.

## Current state on main

- **Open PRs:** 0
- **Anchor on `source/`:** `e18b0cb7344` (unchanged)
- **Corpus on main:** the count grew by 15 idiom docs this
  run.  Pre-run: ~128 idiom docs (per pre-compact handoff).
  Post: ~143.
- **Methodology**: established steady-state corpus mining loop
  validated again across 5 more PRs.
- **Phase D**: unchanged (PARKED — 5 patches in `patches/`
  need explicit re-auth from user).

## What got covered, briefly

### PR #294 — SP-GiST depth trio

Space-partitioned GiST end-to-end: README + `spgist_private.h`
structs + `spgdoinsert.c` + `spgscan.c`.  Documented the
LIVE/REDIRECT/DEAD/PLACEHOLDER tuple-state alphabet, the
choose/picksplit/AddNode/SplitTuple dispatch, the
pairing-heap that doubles as DFS stack and KNN priority
queue, and the triple-parity trick that keeps deadlock rare.

Files added:
- `knowledge/idioms/spgist-tree-and-tuples.md` (487 LOC)
- `knowledge/idioms/spgist-insert-and-picksplit.md` (471 LOC)
- `knowledge/idioms/spgist-scan-and-consistent.md` (568 LOC)

### PR #295 — Analyze + statistics depth trio

`acquire_sample_rows` two-stage sampling (Knuth Algorithm S
blocks + Vitter Algorithm Z reservoir), the 300×attstattarget
rationale from Chaudhuri/Motwani/Narasayya, `std_typanalyze`
dispatch into compute_scalar/distinct/trivial, the tupnoLink
side-effect-during-qsort trick, statistical MCV cutoff via
hypergeometric 2-σ test, Bresenham equi-depth histogram
construction, closed-form Pearson correlation, and the four
extended-statistics kinds (d/f/m/e) with Duj1 ndistinct
estimator and soft-functional-dependency multi-sort
algorithm.

Files added:
- `knowledge/idioms/analyze-block-and-reservoir-sampling.md` (520 LOC)
- `knowledge/idioms/analyze-mcv-histogram-correlation.md` (535 LOC)
- `knowledge/idioms/extended-statistics-statext.md` (566 LOC)

### PR #296 — TIDBitmap depth trio

PagetableEntry bit-packed header, TBM_EMPTY/ONE_PAGE/HASH
lifecycle, PAGES_PER_CHUNK arithmetic, lossy-vs-exact storage,
the recheck flag propagation, tbm_add_tuples
currblk-optimization + lossify-then-invalidate dance,
three-way tbm_union/tbm_intersect branching, tbm_lossify
half-budget target + skip-chunk-boundary + admit-defeat
expansion, private vs. shared iteration via DSA index arrays
+ LWLock cursor, MultiExecProcNode convention, BitmapAnd
first-child-in-place + empty short-circuit, BitmapOr
streaming-into-shared-bitmap optimization, BitmapHeapScan
recheck handshake + MVCC-only restriction.

Files added:
- `knowledge/idioms/tidbitmap-structure-and-lossy.md` (551 LOC)
- `knowledge/idioms/tidbitmap-build-and-iterate.md` (662 LOC)
- `knowledge/idioms/bitmap-and-or-heap-executor.md` (523 LOC)

### PR #297 — Logical-rep apply depth trio

LogicalRepApplyLoop outer/inner loop, three transport message
types (WALData/Keepalive/PrimaryStatusUpdate), apply_dispatch
recursive save/restore for spooled replay, the
two-context memory model (ApplyContext + ApplyMessageContext),
gated between-transactions maintenance, common handler skeleton
(skip checks, REPLICA IDENTITY updatability, updatedCols
tracking), slot_modify_data UNCHANGED/TOASTED preservation,
cross-origin conflict detection, missing-vs-deleted
classification, partition tuple routing (DELETE-then-INSERT
on partition change), TransApplyAction five-way enum,
parallel apply DSM + shm_mq with deadlock-detection lock
graph (stream lock + transaction lock), subxact-info file
truncation, worker-pool half-cap threshold.

Files added:
- `knowledge/idioms/apply-worker-loop-and-dispatch.md` (527 LOC)
- `knowledge/idioms/apply-handlers-insert-update-delete.md` (595 LOC)
- `knowledge/idioms/apply-streaming-and-parallel.md` (589 LOC)

### PR #298 — Snapshot management depth trio

Six static SnapshotData slots
(Current/Secondary/Catalog/Self/Any/Toast),
GetTransactionSnapshot three-mode dispatch with
isolation-level Copy+Register difference for Repeatable Read,
GetCatalogSnapshot reuse pattern with manual heap add,
InvalidateCatalogSnapshot inval-callback hookup,
TransactionXmin vs RecentXmin distinction, dual refcount
model (active_count + regd_count), PushActiveSnapshot
static-slot auto-copy, ActiveSnapshotElt as_level invariant,
RegisteredSnapshots pairing heap with xmin_cmp, SnapshotResetXmin
skip-if-active-not-empty optimization, AtSubAbort_Snapshot
stack pop by level, pg_snapshots text file format
(vxid/xmin/xmax/xip/sof/sxp/rec), addTopXid inclusion when
topXid < xmax, SetupHistoricSnapshot logical-decoding catalog
shadow, tuplecid (cmin, cmax) hash for in-progress catalog
xacts, SerializedSnapshotData parallel-worker wire format with
EstimateSnapshotSpace, single-allocation RestoreSnapshot layout.

Files added:
- `knowledge/idioms/snapshot-static-and-current.md` (575 LOC)
- `knowledge/idioms/snapshot-active-stack-and-registered.md` (696 LOC)
- `knowledge/idioms/snapshot-export-historic-parallel.md` (556 LOC)

## Methodology that emerged (no change from prior arc)

The steady-state corpus-mining loop continues to validate:

1. **Pick adjacent gap from prior handoff catalog.**
2. **Refresh main + create new worktree** from current main —
   not from any pre-existing stale branch.
3. **Symlink `source/` and `dev/` into worktree.**
4. **Read at anchor `e18b0cb7344`**: README first where one
   exists, then key .c files (entry points + structural blocks).
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

This run's modest LOC inflation (~561 avg vs. ~440 historical
target) reflects covering substantial subsystems where
brevity would have lost detail.  No regression in cite
density or structure.

## Adjacent gaps remaining (round-5 list)

These were listed in the pre-compact handoff under "Adjacent
gaps to consider for next session".  Strikethrough = covered
this run; rest are still open.

- ~~SP-GiST internals~~ ✓ #294
- ~~TID scan + bitmap heap scan integration~~ ✓ #296 (TIDBitmap)
- ~~Logical replication apply worker depth~~ ✓ #297
- ~~Snapshot management depth~~ ✓ #298
- ~~Statistics target + analyze sampling~~ ✓ #295
- **Parallel query coordination** — Gather setup,
  ParallelContext + DSM segments, parallel_safe propagation
  through paths.
- **Subxact handling depth** — XidCache / committed-xids /
  subxact stack, PGPROC.subxids[] mechanics, lock conflict on
  parent-vs-subxact xids.
  - Note: `subtransaction-stack.md` exists at 26K but a depth
    trio could still split into per-mechanism docs.
- **CHECK / NOT NULL / foreign-key constraint enforcement** — RI
  trigger generation, constraint exclusion in planner, deferred
  vs immediate.
  - Note: FK triggers already covered in #276; CHECK constraint
    machinery is the missing piece.
- **Memory contexts depth** — AllocSet / BumpContext / Slab /
  Generation context internals, chunk-header bit packing,
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
  Note: TOAST round 1 covered varatt + chunk write + detoast
  in PR #273 (round 4).  Round 2 would dig deeper into
  compression algorithms + streaming paths.

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

## The stale-plan situation

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

## Post-compact resume checklist

1. **Read this doc** at
   `sessions/2026-06-15-handoff-post-compact-round5-run2.md`.
2. `git fetch origin && git log --oneline -5` to see what
   merged overnight (cloud routines, if any).
3. Verify anchor: `git -C ../../postgresql rev-parse HEAD`
   should be `e18b0cb7344` (unless `/refresh-upstream` ran).
4. Confirm 0 open PRs:
   `gh pr list --state open --json number | python3 -c
   'import json,sys; print(len(json.load(sys.stdin)))'`.
5. Pick the next trio:
   - **Parallel query coordination** — strong candidate; the
     snapshot-export-historic-parallel doc just landed
     references parallel mode extensively.
   - **Memory contexts depth** — would split the existing
     `memory-contexts.md` into AllocSet / Slab+Generation /
     BumpContext detailed docs.
   - **Type-cache depth** — coherent single-subsystem dig.
   - **TOAST round 2** — close the round-4 catalog item.
   - **CHECK constraint machinery** — fills the constraint gap.
   - Or one of the round-5 leftovers above.
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

## TL;DR for next-Claude

This run: 5 PRs merged, 8,421 LOC of new corpus docs across
15 idiom files.  Each PR was a coherent depth-trio for one
subsystem.  Adjacent-gap catalog from round 5 is now ~5/10
cleared.  Methodology unchanged: ~440-700 LOC per doc,
README + key .c files at anchor `e18b0cb7344`, anti-target
audit per commit, immediate merge.

Resume by picking from the remaining adjacent gaps:
parallel query coordination, memory contexts depth, type-cache
depth, TOAST round 2, CHECK constraints, subxact depth.  Or
follow user-directed pivot.

Anchor at `e18b0cb7344`.  0 open PRs.  Anti-targets clean.
Don't break the rules.
