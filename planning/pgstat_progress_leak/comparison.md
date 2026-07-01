# Comparison — our blind fix vs upstream `b20c952ce70`

**Date:** 2026-06-23
**Our fix:** `193187edd3a` on `feature_pgstat_progress_leak`
**Upstream:** `b20c952ce70` (Michael Paquier, 2026-06-08)

Both branches start from parent `a450dd7ad4f`.

## Diff comparison — bit-identical

```
$ git diff --stat 193187edd3a^!
 src/backend/utils/activity/backend_progress.c | 2 --
 1 file changed, 2 deletions(-)

$ git diff --stat b20c952ce70^!
 src/backend/utils/activity/backend_progress.c | 2 --
 1 file changed, 2 deletions(-)
```

Byte-for-byte identical patch: both fixes delete
`initStringInfo(&progress_message);` and the blank line above it,
at the same location in the same file.

```diff
--- a/src/backend/utils/activity/backend_progress.c
+++ b/src/backend/utils/activity/backend_progress.c
@@ -100,8 +100,6 @@ pgstat_progress_parallel_incr_param(int index, int64 incr)
 	{
 		static StringInfoData progress_message;

-		initStringInfo(&progress_message);
-
 		pq_beginmessage(&progress_message, PqMsg_Progress);
 		pq_sendint32(&progress_message, index);
 		pq_sendint64(&progress_message, incr);
```

## TC-LB-1 outcome

| metric                        | parent (pre-fix) | upstream `b20c952ce70` | ours `193187edd3a` |
|-------------------------------|----------------:|-----------------------:|-------------------:|
| Top worker peak RSS           | 39,196 KB       | 38,236 KB              | (equivalent — same diff) |
| Top worker delta over life    | **+18,004 KB**  | +6,384 KB              | +6,384 KB          |
| Leak component                | ~12 MB          | 0                      | 0                  |

## Methodology validation — the blind trilogy nailed this one

Unlike the jsonpath_leak calibration where our design diverged
from Tom Lane's on the storage-representation axis, this
second-target run produced the **byte-identical patch** to
upstream, via a genuinely blind path:

1. **Phase 0 harness setup** — reused the container built for
   jsonpath_leak (`pg-memhunt:noble` image, `inside-build.sh`
   template).  Wrote a new `inside-pgstat.sh` driver that
   spawns a parallel VACUUM with `track_cost_delay_timing`
   enabled + cost-delay set to 1 ms, samples parallel-worker
   RSS every 0.5 s throughout.  Amplified from a 5M-row / 8-index
   table to 10M-row / 16-index after the first-cut signal was
   too noisy (baseline growth was on the same order as the
   leak).  The amplified workload gave one worker 43 s of
   sustained cost-delay reporting, compounding the leak to
   +18 MB.
2. **Phase 1 triage** — picked `b20c952ce70` for methodology
   generalization: different subsystem (utils/activity vs
   utils/adt), different bug pattern (redundant double-init vs
   transient-lifetime leak), parallel-worker context vs
   per-tuple execution context.  Explicitly a DIFFERENT bug
   SHAPE than jsonpath_leak's.
3. **Phase 2 brainstorm** — read
   `pgstat_progress_parallel_incr_param()` at the parent
   commit, then followed the F30 grep-pass into
   `pq_beginmessage()` and `pq_endmessage()` in
   `src/backend/libpq/pqformat.c`.  Verified that
   `pq_beginmessage` unconditionally calls `initStringInfo`
   internally, and `pq_endmessage` calls
   `pfree(buf->data); buf->data = NULL`.  The lifecycle
   contract of the pq_ pair is self-managed; the explicit
   `initStringInfo` in `pgstat_progress_parallel_incr_param`
   orphans buffer A before pq_beginmessage's internal
   `initStringInfo` overwrites `data` with buffer B.
   Enumerated three approaches (A: delete redundant init; B:
   also drop the `static` qualifier; C: per-call
   MemoryContext).  Recommended A.
4. **Phase 2 plan** — plan §7 ran the F30 grep-pass over every
   `pq_beginmessage()` call site in `src/backend`.  Found 21
   sites, ONLY this one pre-calls `initStringInfo`.  The
   ownership invariant *"pq_beginmessage owns allocation,
   pq_endmessage owns deallocation, callers must not
   pre-allocate"* was confirmed by data flow, not asserted.
   This is exactly what F30 was designed to catch — and it
   caught it.
5. **Phase 3 implement** — one commit, `-initStringInfo(...)`
   and its blank line.  R13 helper-tier regress: 245 subtests
   clean, zero diff.
6. **Phase 4 (this doc)** — fetched `b20c952ce70`, diffed.
   Byte-identical.

## L5 / F30 outcome for this run

**L5 (storage representation)** — the brainstorm's §5
"Storage representation" field noted that `StringInfoData` is a
by-value BSS static with a by-pointer `data` field, and that
representation is correct — the bug is the redundant init, not
the shape.  Approach B (drop `static`) was considered and
rejected because it changes representation without fixing the
bug.  The L5 sub-question served its purpose: it forced explicit
consideration of the storage choice, even though the answer
was "keep it".

**F30 (ownership grep-pass)** — the plan §7 grep-pass was the
load-bearing step for this run.  Instead of ASSERTING "no other
site calls initStringInfo before pq_beginmessage", we VERIFIED
by grepping all 21 call sites.  Confirmed at plan time, not at
phase-end check time.  Fast (30-second grep) and cheap;
prevented any doubt about the fix's scope.

## What this validates about the planner suite v1.4

- **Simple leaks land byte-identically to upstream.**  A
  well-designed single-line fix has a unique correct shape, and
  the trilogy suite converges on it.
- **The v1.4 L5 + F30 skill edits, landed after jsonpath_leak,
  paid off immediately on the very next run.**  Both new
  sub-questions were asked, both had answers on the record,
  both anchored the recommendation.  No R7 escalations at
  Phase 3 phase-end check.
- **Two different bug shapes, two successful trilogy runs.**
  jsonpath_leak was a struct-redesign + hot-path context wrap;
  this one is a 1-line delete.  Same brainstorm+plan+implement
  scaffolding, dramatically different output shapes — the
  planner suite scales.

## L-lesson to graduate (or not)

None.  This run's inputs were fully covered by v1.4's existing
L1-L5 + F26-F30.  If anything, it VALIDATES those rules by
using them successfully.  No new corpus edits queued.

## What this run did NOT do

- Did not add regress test coverage (per DECISION 3: the fix
  is too small to justify cross-platform RSS-assertion test
  infrastructure).  Upstream `b20c952ce70` also shipped no
  test rows.
- Did not backport.  Local calibration only.
- Did not upstream-submit.  The fix already exists in master
  as `b20c952ce70`.
