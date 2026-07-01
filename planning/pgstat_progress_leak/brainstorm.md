# Brainstorm — pgstat_progress_parallel_incr_param memory leak

**Slug:** `pgstat_progress_leak`
**Phase:** brainstorm (Phase 1 of the planner)
**Status:** blind — written without consulting the actual fix
(`b20c952ce70`); to be compared against it post-implement.

> **Blind constraint.** Methodology-validation run #2 (after
> `jsonpath_leak`). The fix already exists upstream at
> `b20c952ce70`. We derive the fix from inspection at the parent
> commit `a450dd7ad4f` and compare designs at Phase 4. Do NOT
> read `b20c952ce70` source until then.

## Context

Reproducer (validated against parent commit on 2026-06-23 in
`planning/memory-hunt/evidence/pgstat-{parent,fix}/`):

```sql
-- 10M-row, 16-index table; force a long parallel VACUUM with
-- cost-delay timing reporting; sample worker RSS every 0.5s.
CREATE TABLE big (id int, c1..c16 int);
INSERT INTO big ...
CREATE INDEX big_c1..c16 ...
UPDATE big SET c1 = c1 + 1 WHERE id % 2 = 0;
DELETE FROM big WHERE id % 7 = 0;
SET track_cost_delay_timing = on;
SET vacuum_cost_delay = '1ms';
VACUUM (PARALLEL 4, VERBOSE) big;
```

Pre-fix top parallel-vacuum worker peak RSS: **39,196 KB**, delta
from start: **+18,004 KB** over ~43 s lifetime. Post-fix top
worker: **38,236 KB peak, +6,384 KB delta** (the +6 MB is
legitimate working-set growth: dead_items array, page pins, etc.).
**Leak: ~12 MB per long-running worker.**

## Root cause (verified by reading source at parent)

`src/backend/utils/activity/backend_progress.c:92-110`
`pgstat_progress_parallel_incr_param()`:

```c
if (IsParallelWorker())
{
    static StringInfoData progress_message;

    initStringInfo(&progress_message);                    // line 1: alloc A

    pq_beginmessage(&progress_message, PqMsg_Progress);   // line 2: alloc B (LEAKS A)
    pq_sendint32(&progress_message, index);
    pq_sendint64(&progress_message, incr);
    pq_endmessage(&progress_message);                     // pfree(B), data=NULL
}
```

The relevant pq_ helpers (verified in `src/backend/libpq/pqformat.c`):

- `pq_beginmessage(buf, msgtype)` calls `initStringInfo(buf)`
  internally — **always palloc's a fresh buffer**, ignoring
  whatever `buf->data` pointed at before.
- `pq_endmessage(buf)` calls `pfree(buf->data)` and sets
  `buf->data = NULL`.

So the **begin/end pair self-manages buffer lifecycle**.  The
explicit `initStringInfo(&progress_message)` at line 1 is
redundant — its allocation is immediately orphaned by
pq_beginmessage's internal initStringInfo, and `data` is
overwritten with the second palloc.  Each call to
`pgstat_progress_parallel_incr_param` from a parallel worker
leaks one `initStringInfo`-sized buffer (~1024 bytes default).

In the worker context that persists for the worker's lifetime,
these leaked buffers compound: a worker that fires the progress
hook every cost-delay tick (~kHz when `track_cost_delay_timing`
is on and `vacuum_cost_delay > 0`) accumulates MB-scale leak
within seconds.

## §0 Concrete usage surface (what must NOT leak)

Every code path that reaches
`pgstat_progress_parallel_incr_param` from a parallel worker —
i.e. the function must remain leak-free for every caller in the
tree, not just the ones our reproducer hits.

| Caller | File:line | Trigger |
|---|---|---|
| `pgstat_progress_parallel_incr_param(PROGRESS_VACUUM_DELAY_TIME, ...)` | `commands/vacuum.c:2543` | VACUUM worker fires every `PARALLEL_VACUUM_DELAY_REPORT_INTERVAL_NS` while `track_cost_delay_timing` is on |
| `pgstat_progress_parallel_incr_param(PROGRESS_VACUUM_INDEXES_PROCESSED, 1)` | `commands/vacuumparallel.c:1151` | VACUUM worker fires once per index processed |
| `pgstat_progress_parallel_incr_param(PROGRESS_VACUUM_DELAY_TIME, ...)` | `commands/vacuumparallel.c:1321` | VACUUM worker fires at end if delay timing tracked |

Future callers (CREATE INDEX, parallel COPY, etc.) automatically
inherit the fix.

### Load-bearing test row (R15a)

**TC-LB-1:** *parallel VACUUM with cost-delay-timing on a multi-
index table runs to completion without worker RSS growing
unboundedly.*  Quantitative threshold: per-worker RSS delta over
its lifetime stays within 10 MB of legitimate working-set growth
(measured against the fix run; the parent overshoots this by ~12 MB).

## Candidate approaches

### Approach A — remove the redundant initStringInfo call

```c
if (IsParallelWorker())
{
    static StringInfoData progress_message;

    pq_beginmessage(&progress_message, PqMsg_Progress);
    pq_sendint32(&progress_message, index);
    pq_sendint64(&progress_message, incr);
    pq_endmessage(&progress_message);
}
```

**Pros:**
- Minimal diff (1 line removed).
- Matches the documented contract of `pq_beginmessage` /
  `pq_endmessage` — caller is NOT expected to pre-allocate.
- Other `pq_beginmessage` call sites in the tree do not
  pre-call `initStringInfo`. Removing makes this call site
  consistent.

**Cons:**
- None observed.

**Storage representation** (per L5): `StringInfoData` itself
remains a by-value `static` (resides in BSS), with the
`data` field as a by-pointer to a palloc'd buffer. The fix
doesn't change representation — it just stops the redundant
allocation that orphaned a buffer. Both `static`-as-BSS and
`data` as palloc'd-pointer are correct for the pq_ contract
(begin allocates fresh, end frees + nulls).

### Approach B — remove `static` and `initStringInfo` together

Make `progress_message` a stack-local automatic and let
pq_beginmessage / pq_endmessage manage its buffer lifecycle:

```c
StringInfoData progress_message;
pq_beginmessage(&progress_message, PqMsg_Progress);
pq_sendint32(&progress_message, index);
pq_sendint64(&progress_message, incr);
pq_endmessage(&progress_message);
```

**Pros:** symmetric with how other call sites in `pqformat.c`
use these helpers (always stack-local).

**Cons:**
- `static StringInfoData progress_message;` was presumably added
  on purpose — likely to keep the struct out of stack-bounded
  warnings or to support reuse intent. Removing it changes a
  more visible aspect of the function shape than Approach A.
- The 16-byte StringInfoData struct on stack is trivial, but
  the change is more invasive than Approach A.

### Approach C — switch to a per-worker MemoryContext

Wrap the whole begin/end pair in a short-lived MemoryContext
that gets deleted after each call. This is brainstorm-skill's
"approach B from jsonpath_leak" applied to this site.

**Pros:** structurally absorbs any future leak inside
pq_beginmessage/sendXXX/endmessage.

**Cons:**
- `pq_beginmessage`/`pq_endmessage` already manage their own
  lifecycle correctly — the bug is the EXTRA `initStringInfo`
  outside the begin/end pair.  Wrapping the entire site in a
  per-call context is a sledgehammer for a 1-line bug.
- Per-call `AllocSetContextCreate` + `Delete` cost
  (~400 ns) is gratuitous when the underlying machinery is
  already correct.

## Recommended approach

**Approach A.** The bug is a single redundant call to
`initStringInfo`; the fix is to delete it. Approach B's
`static`-removal is plausible refactoring but unrelated to the
leak. Approach C over-engineers a problem that already has a
1-line answer.

**§0 ownership-invariant grep-pass (per F30):** before locking
this recommendation, grep every other call site of
`pq_beginmessage` in the tree and confirm none of them call
`initStringInfo` first.

```bash
grep -rn 'pq_beginmessage' /tmp/pg-pgstat-parent/src --include='*.c' \
  | head -20
```

If any site DOES call `initStringInfo` first, we have either
(a) the same latent leak elsewhere, or (b) a non-trivial reason
for the redundant init that constrains our fix. Both cases
demand a follow-up. (Spoiler: confirmed during plan §7 that no
other site does this — see `plan.md` §7.)

## DECISION questions for the user

**DECISION 1 — Approach.** A (delete redundant init) vs B
(also remove `static`) vs C (per-call MemoryContext).
**Recommended: A.**

**DECISION 2 — Backport scope.** The upstream fix should
back-port to all branches that have the bug. The leak commit
is identified by the §0 grep-pass as touching whatever PG
version introduced `pgstat_progress_parallel_incr_param`.
For our calibration purposes, parent-commit-only is fine.

**DECISION 3 — Test coverage.** A regress test that
asserts bounded worker RSS is hard to write portably (cgroups
differ, slow CI flakes). Options:
- (a) Skip regress; rely on Valgrind in the buildfarm to catch
  any regression.
- (b) Add a TAP test under `src/test/recovery/` that runs a
  parallel VACUUM and asserts the worker process's RSS delta
  is below a threshold (Linux-specific).
- (c) No new test; the bug is so small that adding one would
  flake more than it would protect.

**Recommended: (c)** — the bug is a single-line oversight in
an obvious code path; the diff is too small to justify
test infrastructure.

## Hand-off

Next step: `/pg-plan pgstat_progress_leak` for the heavy plan,
then `/pg-implement pgstat_progress_leak` (which will be very
short given Approach A is a 1-line delete).
