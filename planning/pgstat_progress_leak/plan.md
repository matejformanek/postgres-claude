# Plan — pgstat_progress_parallel_incr_param leak fix

**Slug:** `pgstat_progress_leak`
**Brainstorm:** [brainstorm.md](brainstorm.md)
**Approach:** A — delete the redundant `initStringInfo` call.
**Source pin (parent):** `a450dd7ad4ff80c65f565f1a2bd24be8ff0bf3e3`
**Comparison commit (not consulted during planning):** `b20c952ce70`
**Implementation site:** dev worktree
`postgresql-dev-feature-pgstat_progress_leak` branched at the
parent.

## §0 Context

Calibration plan #2 — methodology generalization test after
`jsonpath_leak`. Single-line bug in
`pgstat_progress_parallel_incr_param()`: an explicit
`initStringInfo(&progress_message)` palloc's a buffer that is
immediately orphaned by `pq_beginmessage`'s own internal
`initStringInfo`. Each parallel-worker call leaks one
`initStringInfo`-sized allocation (~1024 bytes) into the
worker's MemoryContext. Long-running parallel VACUUM workers
accumulate ~12 MB of leak in ~45 s under TC-LB-1.

## §1 What this plan is

Delete line 103 of `backend_progress.c`:
`initStringInfo(&progress_message);`. That's the entire fix.

## §2 Scope contract

**IN scope:**
- One line removed in
  `src/backend/utils/activity/backend_progress.c`.

**OUT of scope:**
- Refactoring `progress_message`'s `static` qualifier
  (Approach B).
- Wrapping the begin/end pair in a per-call MemoryContext
  (Approach C).
- Audit of other `pq_beginmessage` call sites — completed at
  brainstorm § F30 grep-pass; no other site has the same
  redundant-init pattern.
- Regression test addition — the bug is too small to justify
  cross-platform RSS-assertion test infrastructure (DECISION 3
  resolved as "no test"). Valgrind in the buildfarm will catch
  any regression.

## §3 Files that change

| File | Change | Size | Summary |
|------|:------:|:----:|---------|
| `src/backend/utils/activity/backend_progress.c` | modify | tiny (1 line) | Delete the redundant `initStringInfo(&progress_message)` call at line 103 — pq_beginmessage already initializes the buffer. Source:line confirmed at `/tmp/pg-pgstat-parent/src/backend/utils/activity/backend_progress.c:103`. |

## §4 Catalog + on-disk impact

None.

## §5 WAL impact

None.

## §6 Locking + concurrency

None — the bug is per-worker memory leak, no shared state
involved.

## §7 Memory + resource management

The fix's core. `StringInfoData`'s `data` field lifecycle:

- **Before fix**: caller-side `initStringInfo` palloc's buffer A;
  `pq_beginmessage` internally palloc's buffer B (overwriting
  `data`); `pq_endmessage` pfrees B and nulls `data`. Buffer A
  leaks every call.
- **After fix**: only `pq_beginmessage`'s internal `initStringInfo`
  runs; `pq_endmessage` cleanly pfrees the matching allocation.

The `static StringInfoData progress_message` remains — it lives
in BSS (zero-initialized once, no per-call allocation overhead
for the struct itself). The `data` pointer inside is the only
field that takes allocations; `pq_endmessage`'s `data = NULL`
keeps the static struct in a clean state between calls.

### F30 ownership-invariant grep-pass (per pg-feature-plan §7 v1.4)

Run at brainstorm-time, results re-confirmed here:

```bash
grep -rB5 'pq_beginmessage' /tmp/pg-pgstat-parent/src/backend --include='*.c' \
  | grep -E '(initStringInfo|pq_beginmessage)' \
  | grep -B1 'pq_beginmessage' | grep 'initStringInfo'
```

Hits: **1** —
`backend_progress.c:103` (the site we're fixing). All 21 other
`pq_beginmessage` call sites in the backend either declare
their `StringInfoData` fresh (stack-local) or reuse a
`static`/struct-member without pre-init'ing.  No latent
duplicate of this bug.

Ownership invariant stated cleanly: **`pq_beginmessage` owns
the `data` buffer's allocation; `pq_endmessage` owns the
deallocation; callers must not pre-allocate.**  The fix
restores this contract at the one site that violated it.

## §8 Phased implementation

One phase.

### Phase 1 — Delete the redundant init call

- **Files:** `src/backend/utils/activity/backend_progress.c`.
- **Edits:** delete line 103
  `initStringInfo(&progress_message);` (and its preceding
  blank line for cleanliness).
- **Phase-end check** (R13 scope: "helper-only change, no
  cross-cutting impact"): `--suite regress` is sufficient.
  Plus the TC-LB-1 harness re-run showing worker RSS delta
  drops from ~18 MB to ~6 MB (legitimate working-set growth).
- **Tests covered:** TC-LB-1 (parallel VACUUM with
  track_cost_delay_timing).

## §9 Risks

1. **`static` lifetime question.** Removing `initStringInfo`
   means the `static StringInfoData progress_message` is no
   longer pre-initialized to "valid empty buffer" — but
   pq_beginmessage's internal `initStringInfo` doesn't depend
   on prior state; it's safe to call against a zero-initialized
   or freshly-pfree'd struct. (Verified: `initStringInfo`
   inside pq_beginmessage does an unconditional palloc; no
   check of pre-existing `data`.)
2. **Concurrent parallel workers.** Each worker has its own
   process and its own `progress_message` BSS slot, so there's
   no inter-worker race introduced or removed by this fix.

## §10 R13 tier

Helper tier → `--suite regress` is sufficient. No catalog,
grammar, executor, or ruleutils touch. No isolation gate
needed.

## §11 Performance

Removes a redundant palloc + repalloc + (eventually orphaned).
Slight per-call speedup, more from skipping the orphaned
allocation's deferred-OS-reclaim than from the palloc itself.

## §12 Plan-end gate

After Phase 1:
- `meson test --suite regress --no-rebuild` clean.
- Container harness re-runs amplified TC-LB-1; top worker RSS
  delta < 10 MB threshold.
- One commit with `Plan:` trailer.
- Phase 4 (comparison) runs separately.

## §13 Open questions

None substantive — the bug is fully diagnosed and the fix has
a unique correct shape.

## §14 Citation chain + comparison hook

**Plan → source citations** (parent commit
`a450dd7ad4f`):
- `src/backend/utils/activity/backend_progress.c:92-110` —
  `pgstat_progress_parallel_incr_param` body.
- `src/backend/utils/activity/backend_progress.c:103` —
  the redundant `initStringInfo` line.
- `src/backend/libpq/pqformat.c:88-95` — `pq_beginmessage`
  internal `initStringInfo`.
- `src/backend/libpq/pqformat.c:pq_endmessage` —
  the `pfree(buf->data)` + `buf->data = NULL` cleanup.

**Phase 4 comparison hook (not executed during planning):**
- After Phase 1 lands, fetch `b20c952ce70` and diff our 1-line
  delete vs upstream's 2-line delete. Write
  `planning/pgstat_progress_leak/comparison.md`. Expected: ours
  is 1 line, upstream's is 2 (commit msg said "2 deletions" in
  `git show --stat`).

## Hand-off

Next step: `/pg-implement pgstat_progress_leak`. Single phase,
single commit.
