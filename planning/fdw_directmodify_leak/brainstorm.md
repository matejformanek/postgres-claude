# Brainstorm — fdw_directmodify_leak

**Slug:** `fdw_directmodify_leak`
**Target upstream commit (blind):** `232d8caeaaa` (Tom Lane, 2025-05-30)
**Parent pin:** `d98cefe1143`
**Worktree:** `postgresql-dev-feature-fdw-directmodify-leak` on branch
`feature_fdw_directmodify_leak`.
**Blind constraint:** we have NOT read `232d8cae`'s source, its
commit message body beyond the summary quoted in `triage.md`, or the
discussion thread `postgr.es/m/2976982.1748049023@sss.pgh.pa.us`.
This brainstorm is done from evidence in the parent-pin source only.

**Fallback in use:** running as a subagent with no nested `Agent`
tool; parallel Read + Bash calls in a single message substitute for
subagent fan-out. Documented per SKILL.md §Method fallback note.

## §0 Usage surface (what the fix must NOT break)

Unlike the sesvars-style feature brainstorm, this is a BUG FIX — the
"usage surface" is: every user-visible query shape that today exercises
the DirectModify path and must continue to work identically after the
fix. The 20 rows below are the SQL surface the fix protects.

### Happy-path DirectModify (must still work)
1. `UPDATE t_fdw SET c = 1 WHERE id = 42;` — no RETURNING, no error.
2. `UPDATE t_fdw SET c = c+1 WHERE id BETWEEN 1 AND 100;` — batch.
3. `DELETE FROM t_fdw WHERE id > 900;` — delete direct-modify.
4. `DELETE FROM t_fdw WHERE id = 1 RETURNING id, val;` — RETURNING
   consumed in full, no error.
5. `UPDATE t_fdw SET val = val*2 WHERE id BETWEEN 1 AND 10 RETURNING *;`
   — RETURNING with all columns.
6. `UPDATE t_fdw SET val = val WHERE id = 1 RETURNING val, val*2;` —
   RETURNING with local projection over a returned column.

### The failing DirectModify shape (leak trigger)
7. `UPDATE t_fdw SET val=val WHERE id BETWEEN 1 AND 100 RETURNING id, 1000/(id-50);`
   — 100-row batch, div-by-zero fires mid-iteration on id=50.
8. `DELETE FROM t_fdw WHERE id BETWEEN 40 AND 60 RETURNING 1/(id-50);`
   — delete variant.
9. `UPDATE t_fdw SET val=val WHERE id BETWEEN 1 AND 100 RETURNING id::text::int4range;`
   — a returning-projection cast that can fail on some rows.
10. RETURNING projection invokes user PL/pgSQL function that RAISEs.

### Join-DirectModify shape (also leaks)
11. `UPDATE t_fdw1 SET val = t2.val FROM t_fdw2 t2 WHERE t_fdw1.id = t2.id`
    with an EXPLAIN-verified `Foreign Update` shape and a failing
    RETURNING projection.

### Nested / re-entrancy shapes (must still work OR must still leak-safely)
12. `WITH x AS (UPDATE t_fdw SET ... RETURNING id, 1/(id-N)) SELECT ...`
    — CTE eager-execution variant (baseline dead-end #1).
13. `DO $$ BEGIN UPDATE t_fdw ... RETURNING 1/(id-N); EXCEPTION WHEN
    OTHERS THEN ... END; $$;` — PL/pgSQL EXCEPTION handler catching
    the mid-fetch error (baseline dead-end #3).
14. UPDATE inside a savepoint that's rolled back on the mid-fetch
    error, followed by more work in the outer transaction.
15. Prepared statement of a DirectModify-shape UPDATE, executed 5000
    times in a row with div-by-zero on 500 of them.

### Cross-feature integration
16. DirectModify RETURNING inside `SELECT count(*) FROM (UPDATE ...)`
    — outer aggregation reads the RETURNING tuple stream.
17. DirectModify RETURNING with async-append parent (`postgres_fdw`
    async execution can interact with DirectModify's `pendingAreq`
    handling at `execute_dml_stmt` line 4568).
18. DirectModify inside SPI — extension calling `SPI_exec` on a
    DirectModify-shape UPDATE that errors mid-fetch.
19. DirectModify in a query with `SET LOCAL statement_timeout='1ms'`
    firing during the remote fetch (timeout interrupt = mid-fetch
    abort).
20. Session-close during pending DirectModify — proc-exit-time
    cleanup path.

### Load-bearing rows (per R15a)

Two rows are architecturally load-bearing — the fix exists FOR these:

- **§0-7** (`... RETURNING id, 1000/(id-50)` on a 100-row batch) — the
  amplified reproducer from `baseline.md`. If the fix does not make
  this loop's RSS stay flat across 20 000 iterations, the fix has
  not shipped.
- **§0-13** (PL/pgSQL `EXCEPTION WHEN OTHERS` catching a mid-fetch
  error) — the semantically hardest case. The plpgsql handler
  catches the ereport, control returns to the plpgsql frame, but
  the surrounding executor state (including the DirectModify's
  `dmstate`) is unwound. Whichever mechanism carries the fix must
  free the PGresult on this shape too, not just on
  transaction-abort.

Every candidate approach in §5 must handle both rows or it is
disqualified.

## §0.5 Existing PG mechanism survey (reuse vs invent)

Approaches for reclaiming a libpq PGresult on error boil down to
picking a *lifetime hook* to piggyback on. libpq's PGresult is
malloc'd outside PG's MemoryContext system, so the naive
`MemoryContextReset` on `es_query_cxt` does NOT free it — the
malloc pool survives the context. Every candidate mechanism below
answers "what PG lifetime hook can I attach a PQclear-caller to?".

| Mechanism                                      | Could it carry this? | Cost of reuse                                                                                                                                                                              | Cost of invent                                  |
|------------------------------------------------|----------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------|
| PG_TRY / PG_CATCH block                        | YES but limited      | zero — pattern used 20+ times in postgres_fdw.c. Downside: only covers errors thrown within THIS PG_TRY's `try` clause; a mid-iteration error thrown from LOCAL projection is outside.       | n/a                                             |
| `MemoryContextRegisterResetCallback` on `es_query_cxt` | YES              | tiny — API signature at `src/include/utils/palloc.h:134`. Callback fires on context RESET or DELETE. `es_query_cxt` is deleted at end of executor run for the query, including error-abort.  | n/a                                             |
| `MemoryContextRegisterResetCallback` on `dmstate->temp_cxt` | NO         | temp_cxt is per-tuple (reset each iteration per usage at `postgres_fdw.c:2723`). PGresult must outlive temp_cxt.                                                                             | n/a                                             |
| ResourceOwner-tracked resource                 | YES but heavy        | requires a new ResourceOwner "kind" — `ResourceOwnerRememberXxx` / `ResourceOwnerForgetXxx` funcs, a `ReleaseCallback`. See `src/backend/utils/resowner/resowner.c`. Overkill for one call site. | 5× more touch points than callback              |
| `AtEOXact_*` callback (RegisterXactCallback)   | NO                   | Fires at transaction end. Wrong lifetime — the PGresult must be released at query end (before COMMIT), else the transaction can hold the connection state indefinitely.                     | n/a                                             |
| `before_shmem_exit` / `on_proc_exit`           | NO                   | Fires only at backend shutdown. Session-lifespan leak IS the shape we're fixing.                                                                                                            | n/a                                             |
| A new "cleanup-on-error" hook in FdwRoutine    | maybe                | requires a new FdwRoutine callback, back-patching implications for other FDWs.                                                                                                             | large — API surface change                       |

**Row that wins on cost-of-reuse:** `MemoryContextRegisterResetCallback`
on `es_query_cxt`. It matches the exact lifetime the PGresult needs
(alive through the DirectModify's IterateDirectModify iterations,
dead at query end regardless of success or abort), it's exactly the
API `resowner`-style tracking would want to invent, and it needs 0
new APIs. This is the recommended row.

## §0.7 User-reference-implementation readthrough

**None available.** This is a blind trilogy calibration — the user
has explicitly forbidden reading `232d8caeaaa`'s source, commit
message body, or discussion thread until Phase 4. No reference impl
exists on the user's side either. Continuing at the brainstorm's
scope with no external ceiling.

The `baseline.md` file quotes:

- The commit title: "Fix memory leakage in postgres_fdw's
  DirectModify code path."
- A hint from the commit message: "the ensuing session-lifespan
  leak is visible under Valgrind" — confirming this is a
  session-lifespan, not query-lifespan, leak. The PGresult
  survives the executor's memory-context teardown.
- The diff shape: **+35 / −27, single file, back-patched-through
  PG13.** This is a small, surgical fix. Any candidate approach
  that would produce a +200-line refactor is out-of-shape for a
  back-patch to five stable branches.

Diff-shape constraint on candidates: prefer approaches that hit
`postgres_fdw.c` only, ≤ +50 / −30 net.

## 1 Problem statement

`contrib/postgres_fdw`'s DirectModify path builds a remote UPDATE /
DELETE that pushes the whole modification to the remote server. On
`postgresBeginDirectModify`, the plan is prepared; on the first
`postgresIterateDirectModify` call, `execute_dml_stmt`
(`postgres_fdw.c:4560-4608`) sends the query and stashes the
returned PGresult in `dmstate->result` (line 4597). Subsequent
Iterate calls walk `dmstate->result` row-by-row via
`get_returning_data` (`postgres_fdw.c:4614-4681`). The PGresult is
freed exactly once, in `postgresEndDirectModify` at line 4820:
`PQclear(dmstate->result)`.

The leak: **if any error is thrown by the surrounding executor
BETWEEN `execute_dml_stmt` succeeding and `postgresEndDirectModify`
running**, `postgresEndDirectModify` never runs, and the PGresult
is orphaned in libpq's malloc pool. The classic trigger is a
locally-computed RETURNING projection (`RETURNING id, 1000/(id-50)`)
that fires div-by-zero mid-iteration. The reproducer at
`baseline.md` §Amplified reproducer shows this leaks ~4 KB per
iteration, 3.3 MB/s of RSS growth under a 20 k-iteration loop.

Beneficiary: any operator running long-lived sessions against
foreign tables with DirectModify-shape queries where a small
fraction throw errors. Real workload example: batch-UPDATE ETL
where a rare bad row triggers a division-by-zero, constraint
violation, or trigger raise; the pool of connection-pooled
sessions leaks memory across days.

## 2 Why this might matter

Today the operator sees monotonic RSS growth on postgres_fdw-heavy
sessions and has to `\connect` (or bounce PgBouncer's transaction
pool) periodically to reclaim memory. There's no user-visible
signal short of `ps -o rss=` or `MemoryContextStats` (which won't
show the PGresult because it lives outside PG's context system —
it's plain `malloc`'d by libpq). The fix restores the
correctness invariant: PGresult is always freed regardless of
control-flow escape.

## 3 Relevant subsystems

- `knowledge/idioms/fdw-iterate-scan.md` — the FDW `IterateForeignScan`
  state-machine pattern that DirectModify piggybacks on.
- `knowledge/idioms/memory-contexts.md` +
  `knowledge/idioms/memory-context-api-and-dispatch.md` — the
  reset-callback API the recommended approach hooks into.
- `knowledge/idioms/error-handling.md` — PG_TRY / PG_CATCH /
  PG_END_TRY semantics; volatility of stack-locals across
  siglongjmp.
- `knowledge/scenarios/fix-memory-leak.md` — the change-class
  scenario this brainstorm pins to.

## 4 Has this been tried?

Blind constraint forbids reading the actual fix commit + discussion
thread. What we CAN check:

- **git log at parent-pin `d98cefe1143`**: `git log --grep='DirectModify'
  contrib/postgres_fdw/` shows the introduction of DirectModify
  (`0bf3ae88af` 2015, `1bc0100d27` 2019 for join-pushdown) but no
  leak-fix hits at or before parent-pin. This is the first fix of
  its kind.
- **Corpus**: `knowledge/scenarios/fix-memory-leak.md` is the
  canonical playbook for this change-class. `knowledge/idioms/
  memory-contexts.md` documents the reset-callback API.
- **Prior calibrations**: `planning/jsonpath_leak/`,
  `planning/pgstat_progress_leak/`, `planning/nodesubplan_leak/`
  — three prior leak-fix targets, each with a `comparison.md`
  documenting how the AI-driven fix compared to Tom's actual
  commit. Read for methodology, not for the fix pattern (F30 +
  L5 + L6 lessons).
- **Extensions**: no PGXN extension "fixes this for you". This is
  a fundamental postgres_fdw internal bug.
- **Scenario match**: `fix-memory-leak` is the unambiguous match.
  §3 file table in `plan.md` will PIN to that scenario's checklist.

## 5 Candidate approaches

### Approach A — Add explicit `PQclear` at every mid-iteration exit path

**Description.** Wrap every code region between
`execute_dml_stmt`'s successful return and
`postgresEndDirectModify` in `PG_TRY` / `PG_CATCH` blocks that
`PQclear(dmstate->result)` on error. In practice:
- `postgresIterateDirectModify` (`postgres_fdw.c:2767-2804`) gets a
  PG_TRY covering `execute_dml_stmt(node)` plus
  `get_returning_data(node)`.
- `execute_dml_stmt` gets a PG_TRY that wraps its own store into
  `dmstate->result`, so a throw between store and Iterate return
  is caught. Actually — the throw path is OUTSIDE Iterate, in the
  surrounding executor, so this doesn't help. Escalate.

- **Pros:**
  - Familiar idiom; matches sibling functions in the same file
    (`store_returning_result` at line 4352, `analyze_row_processor`
    surroundings).
  - Small delta; changes are local.
- **Cons / risks:**
  - Fundamentally doesn't work: the error is thrown by the LOCAL
    projection AFTER `get_returning_data` returns. That's in
    `nodeForeignscan.c` (`ExecScan` slot-projection), not in
    `postgres_fdw.c` at all. `postgresIterateDirectModify` has
    already returned; there's no PG_TRY in its frame to catch.
  - Would require pushing PG_TRY blocks up into `nodeForeignscan.c`
    or `ExecScan`, which is core-executor surgery for a contrib
    bug — clear scope violation.
  - Adds noise; harder to maintain than a lifetime-hook approach.
- **Scope:** small in `postgres_fdw.c` but large if the fix must
  extend into core. Actual fix scope: does not cover the reproducer.
- **Existing PG mechanism it reuses:** row 1 of §0.5 (PG_TRY /
  PG_CATCH). Insufficient — see cons.
- **Storage representation:** the PGresult is a libpq malloc'd
  opaque struct; no by-value / by-pointer / by-reference-to-pool
  choice on our side. `dmstate->result` holds a raw pointer.
  (Question fires — answer: only by-pointer is available for
  libpq PGresult; the storage-representation dimension is
  degenerate here.)
- **Coverage of §0 usage surface:** rows 1-6 (happy paths) fine;
  rows 7-11 (the leak trigger) **not covered** because the throw
  is outside our PG_TRY's `try` clause. Row 13 (plpgsql exception
  handler) partially covered iff the PG_TRY sits at exactly the
  right frame — but that frame is in the executor, not our code.
- **Citations:** `[scenarios: fix-memory-leak (this scenario),
  fdw-iterate-scan (call shape)]` `[personas: tom-lane (postgres_fdw
  maintainer + reflex on PG_TRY correctness), andres-freund
  (per-error hot-path)]` `[idioms: error-handling.md, memory-contexts.md]`

**Verdict:** REJECT. Doesn't actually address the leak because
the throw site is outside our reach. Kept in the enumeration
because it's the naive-obvious approach and the brainstorm has
to explicitly rule it out.

### Approach B — Hoist PGresult ownership into a wrapper function with a single PG_TRY covering all inner logic

**Description.** Introduce a helper that owns the PGresult
lifetime end-to-end: acquire in Begin, hold across iterations,
release in End; wrap the entire span in a PG_TRY block installed
somewhere the wrapper controls. The natural place: `execute_dml_stmt`
becomes the acquirer; a new `release_dml_result` becomes the
releaser; `postgresIterateDirectModify` and `postgresEndDirectModify`
call the release under all exit shapes.

But wait: **there is no single function whose PG_TRY can span
Begin → Iterate → End.** These are separate FdwRoutine callbacks
invoked at different points by the executor. A single PG_TRY block
can't straddle the FdwRoutine boundary.

The realistic form of Approach B: install a PG_TRY block inside
`postgresIterateDirectModify` that spans `execute_dml_stmt` +
`get_returning_data` + returning the slot. On CATCH, `PQclear`
and re-throw. This covers throw sites INSIDE Iterate; still
does not cover the local-projection-fires-in-executor case.

- **Pros:**
  - Idiomatic; same shape as `store_returning_result` at line 4352
    which wraps `make_tuple_from_result_row` in PG_TRY.
  - No new lifetime hook.
- **Cons / risks:**
  - Doesn't cover throws that happen AFTER Iterate returns the
    slot to the executor. And that's exactly the reproducer's
    shape.
  - Adds two nested PG_TRYs in Iterate (there's already one at
    line 4648 in `get_returning_data`).
- **Scope:** small.
- **Existing PG mechanism it reuses:** row 1 of §0.5.
- **Storage representation:** by-pointer only (see A).
- **Coverage of §0 usage surface:** rows 1-6 OK; row 7 (the
  reproducer) NOT covered — the throw is in `ExecProject` for
  `1000/(id-50)`, outside our Iterate frame.
- **Citations:** same as A.

**Verdict:** REJECT for the same reason as A — misses the actual
reproducer's throw site. Interesting variant: what if the outer
executor did wrap FdwRoutine calls in a PG_TRY on our behalf?
It doesn't (search `ExecScan` / `ExecForeignScan`). So even a
"perfectly-placed PG_TRY" approach can't reach.

### Approach C — MemoryContext reset callback on `es_query_cxt`

**Description.** Register a `MemoryContextCallback` on
`estate->es_query_cxt` (the per-query executor context that lives
from `standard_ExecutorStart` to `standard_ExecutorEnd`, and is
deleted on both success and abort). The callback holds a pointer
to the PGresult (or to a small heap-allocated struct with a
`PGresult **` handle) and calls `PQclear(*handle)` on reset/delete.

The signature (from `src/include/utils/palloc.h:47-52`):

```c
typedef void (*MemoryContextCallbackFunction) (void *arg);
typedef struct MemoryContextCallback {
    MemoryContextCallbackFunction func;
    void       *arg;
    struct MemoryContextCallback *next;
} MemoryContextCallback;
extern void MemoryContextRegisterResetCallback(MemoryContext context,
                                               MemoryContextCallback *cb);
```

Registration point: in `postgresBeginDirectModify` right after
`dmstate = palloc0(...)` at `postgres_fdw.c:2670`, register a
callback on `estate->es_query_cxt`. The callback frees whatever
PGresult `dmstate->result` currently points to (nullable if
never set, or already cleared by End).

The tricky part: if `postgresEndDirectModify` runs successfully,
it too calls `PQclear(dmstate->result)`. We need to null the
handle after PQclear so the reset callback doesn't double-free.
Standard idiom: `PQclear(dmstate->result); dmstate->result = NULL;`
and the callback checks for NULL.

- **Pros:**
  - Correct lifetime match: `es_query_cxt` is deleted at end of
    every executor run, including error-abort. The PGresult
    always gets a `PQclear` call.
  - Handles the reproducer (row 7) correctly: mid-iteration
    div-by-zero triggers `AbortCurrentTransaction`, which calls
    `AtEOXact_*` cleanups; the executor's teardown deletes
    `es_query_cxt`; the callback fires; `PQclear` runs.
  - Handles row 13 (plpgsql EXCEPTION handler): the sub-transaction
    abort still deletes the executor state's context tree — the
    query's es_query_cxt is deleted regardless of whether the
    error is caught up-stack.
  - Zero new API surface. Small diff, back-patchable.
  - Matches existing pattern in `nodeSubplan.c` — but wait, we
    can't cite that from prior calibrations per the constraint.
    Independent grep: `git -C source grep -l MemoryContextRegisterResetCallback`
    shows ~15 call sites in-tree, this is a well-worn idiom.
- **Cons / risks:**
  - Requires care about the NULL-out-after-PQclear invariant.
    Miss it → double free. Straightforward if we're disciplined.
  - Doesn't help other FDWs — narrow fix. That's fine; scope is
    postgres_fdw only per triage.
  - `MemoryContextCallback` struct allocation must live in a
    context that outlives `dmstate` — probably palloc it in
    `es_query_cxt` itself (the callback's arg is the callback
    struct itself, and the callback pfrees / clears through the
    stored pointer).
- **Scope:** small — diff is ~30 lines net.
- **Existing PG mechanism it reuses:** row 2 of §0.5. Winner.
- **Storage representation:** by-pointer (no choice). The
  callback holds a pointer into `dmstate` OR a heap-alloc'd
  handle. The former is simpler if dmstate is guaranteed to
  outlive es_query_cxt-delete — and it is: dmstate is palloc'd
  in the executor's `PortalContext` which is the parent of
  `es_query_cxt`; when es_query_cxt is deleted, dmstate is still
  valid because Portal cleanup comes later. Confirmed via
  memory-context hierarchy documented in
  `knowledge/idioms/memory-contexts.md` §"Standard executor
  contexts".
- **Coverage of §0 usage surface:** rows 1-20 all covered. Rows
  1-6 unchanged. Rows 7-11 fixed. Rows 12-14 fixed. Rows 15-20
  each unwind through the same `es_query_cxt` deletion path.
- **Refactor shape:** minimal restructuring. `postgresBeginDirectModify`
  gets ~10 lines of callback registration. `postgresEndDirectModify`
  gets a `dmstate->result = NULL;` after `PQclear`. Callback
  function is ~5 lines.
- **Citations:** `[scenarios: fix-memory-leak, add-startup-hook
  (callback-registration idiom), fdw-iterate-scan]` `[personas:
  tom-lane (PostgresFDW maintainer + memory-context correctness),
  andres-freund (per-error hot path, resource tracking)]`
  `[idioms: memory-contexts.md, memory-context-api-and-dispatch.md,
  error-handling.md]`

### Approach D — ResourceOwner-tracked resource

**Description.** Register the PGresult on `CurrentResourceOwner`
via a new resource-owner "kind" (something like
`ResourceOwnerRememberPGresult` / `ResourceOwnerForgetPGresult`).
The `ResourceOwnerRelease` path on abort will iterate the
resource list and call our release callback, which does
`PQclear`.

- **Pros:**
  - Standard PG resource-tracking pattern; used by
    `src/backend/utils/resowner/` for buffers, tuple descriptors,
    dsm segments, files, snapshots.
  - Automatic on abort, symmetric with acquisition. Textbook.
- **Cons / risks:**
  - `resowner.c` (`ResourceOwnerCreate`, `ResourceOwnerRelease`)
    ships an API for `ResourceOwnerRememberXxx` /
    `ResourceOwnerForgetXxx` for each resource kind. Adding a new
    kind means defining the ReleaseCallback + registering it —
    ~15 lines of new API surface in `resowner.h` /`resowner.c`.
    Too invasive for a stable-branch back-patch.
  - `CurrentResourceOwner` is per-transaction (subtransaction);
    lifetime doesn't quite match query-lifespan. Getting the
    right owner requires care in nested contexts.
  - Overkill: `es_query_cxt` reset callback (Approach C) delivers
    the exact same guarantee with 0 new API.
- **Scope:** medium — touches resource-manager surface. Not
  back-patch-friendly.
- **Existing PG mechanism it reuses:** row 4 of §0.5. Ranks
  worse than row 2 on cost-of-reuse.
- **Storage representation:** by-pointer.
- **Coverage of §0 usage surface:** would cover rows 1-20 in
  principle, but back-patch cost is prohibitive.
- **Citations:** `[scenarios: fix-memory-leak, add-new-shared-memory-region
  (resowner-adjacent)]` `[personas: tom-lane, robert-haas]`
  `[idioms: memory-contexts.md, error-handling.md]`

**Verdict:** REJECT for back-patch reasons. In master-only,
Approach D would be reasonable. For a 5-branch back-patch, it's
API surface expansion.

### Approach E — RESTRUCTURE the DirectModify state machine to a single-exit control flow (mandatory per L6)

**L6 trigger check.**

- Target functions: `postgresIterateDirectModify`
  (`postgres_fdw.c:2767-2804`) and `postgresEndDirectModify`
  (`postgres_fdw.c:2810-2827`) — plus their delegates
  `execute_dml_stmt` (`4560-4608`) and `get_returning_data`
  (`4614-4681`).
- Exit paths in `postgresIterateDirectModify`:
  1. `!resultRelInfo->ri_projectReturning` early return
     (line 2797, `return ExecClearTuple(slot);`)
  2. `return get_returning_data(node);` (line 2803, the RETURNING
     path)
- Exit paths in `get_returning_data`:
  1. `if (dmstate->next_tuple >= dmstate->num_tuples) return
     ExecClearTuple(slot);` (line 4626, end-of-data)
  2. `if (!dmstate->has_returning) { ExecStoreAllNullTuple(...); }`
     fall-through (line 4639)
  3. Successful `PG_TRY` completion → fall-through to
     `apply_returning_filter` (line 4672)
  4. `PG_CATCH` block does `PQclear(dmstate->result);
     PG_RE_THROW();` (lines 4661-4664) — this exit RE-THROWS, so
     it's an ereport-exit not a normal return.

Total: 4 exit paths across the two functions if we count
`get_returning_data`, PLUS the "control has already returned to
the executor caller and errors out there" implicit exit path
which is FIVE. **L6 trigger fires** (≥3 exit paths + the fix's
new invariant "PGresult is always freed" must run at every exit
path, including the implicit outside-our-frame one).

**Description.** Restructure the DirectModify state machine so
PGresult ownership follows a single-exit control flow. Two variants:

**E1 — Consolidate PG_TRY blocks into one wrapping the whole
Iterate body.**
Replace the current shape:
```
Iterate:
   if first-call: execute_dml_stmt (stashes result)
   if no RETURNING: return ExecClearTuple
   return get_returning_data
     get_returning_data:
       if EOD: return
       if !has_returning: fall-through
       PG_TRY { make_tuple... } PG_CATCH { PQclear; RE_THROW }
       PG_END_TRY;
       return
```
with:
```
Iterate:
   PG_TRY {
      if first-call: execute_dml_stmt
      if no RETURNING: result = ExecClearTuple
      else result = get_returning_data
   }
   PG_CATCH { PQclear(dmstate->result); dmstate->result = NULL; PG_RE_THROW; }
   PG_END_TRY;
   return result;
```

Adds a single PG_TRY that covers everything Iterate does. **But
still doesn't help the reproducer** — the div-by-zero fires in
`ExecProject` of `1000/(id-50)`, after Iterate returns to
`ExecScan`, so it's OUTSIDE our PG_TRY. E1 is a control-flow
cleanup that doesn't fix the bug. Reject.

**E2 — Move PGresult ownership OUT of the Begin/Iterate/End state
machine entirely; use the memory-context reset callback as the
sole owner.**
This is E collapsing with C. The refactor:
- `postgresBeginDirectModify` allocates the callback + registers
  it on `es_query_cxt`. `dmstate->result` is INITIALIZED to NULL.
- `execute_dml_stmt` writes into `dmstate->result` after successful
  fetch. No PG_TRY around the store — if the store never happens,
  the callback sees NULL and no-ops.
- `postgresIterateDirectModify` no longer has any PGresult
  cleanup responsibility.
- `postgresEndDirectModify` still calls `PQclear(dmstate->result);
  dmstate->result = NULL;` for the happy-path release. On
  error-path, the callback fires, dmstate->result is non-NULL,
  it clears, then nulls the field.
- The internal PG_TRY inside `get_returning_data` (`postgres_fdw.c:4648`)
  now becomes REDUNDANT and can be REMOVED. Its comment (line
  4646: "On error, be sure to release the PGresult on the way
  out. Callers do not have PG_TRY blocks to ensure this happens")
  is no longer true — the callback ensures it. Delete the
  PG_TRY, delete the PG_CATCH, delete the PG_END_TRY, delete
  the redundant PQclear + PG_RE_THROW.

Net delta:
- +5 lines callback struct + registration in Begin
- +5 lines callback function
- −8 lines (delete PG_TRY block in get_returning_data)
- +2 lines NULL-guard sentinels in End + callback
- Net ≈ +4 lines executable

**This E2 shape produces a NET LINE-COUNT REDUCTION for a bug
fix that improves correctness AND simplifies the control flow.**
That's the L6 pattern from the nodesubplan_leak comparison
(§F32): Tom's fix was −16 executable lines vs our +11 because
he restructured to a single-exit + reset-at-exit shape. Here,
Approach E2 = Approach C + delete-redundant-PG_TRY. The C-only
form works but leaves the now-unused PG_TRY in place; the E2
form deletes it because the invariant now covers what the
PG_TRY covered.

- **Pros (E2):**
  - Fixes the reproducer.
  - Simplifies the code path (deletes 8 lines of now-redundant
    error-handling scaffolding).
  - Correctness invariant becomes: "PGresult is owned by the
    callback registered on `es_query_cxt`; End nullifies on
    happy path; callback nullifies on error path" — a single
    ownership statement, not four.
- **Cons / risks (E2):**
  - The plpgsql EXCEPTION handler case (row 13) needs to be
    verified: does the sub-transaction abort reset the ExecutorState
    context of the failed sub-txn's executor invocation? YES —
    plpgsql runs the UPDATE via SPI, and SPI creates its own
    executor state whose `es_query_cxt` is torn down when SPI's
    memory context is reset on sub-abort. Verify at plan time.
  - Deleting the existing PG_TRY changes the diff shape — a
    reviewer will want to understand WHY it's OK to remove it.
    We must document the invariant clearly in the comment
    that replaces it.
  - Removes a defensive pattern; if a future edit re-introduces
    a mid-iteration ownership question, the callback is easy to
    overlook.
- **Scope:** small — same touch pattern as C, plus a deletion.
- **Refactor shape:**
  - Target functions: `postgresBeginDirectModify` (add
    registration), `get_returning_data` (delete PG_TRY),
    `postgresEndDirectModify` (add NULL-out).
  - Current exit-path count: 5 (per L6 check above).
  - Proposed collapsed shape: single ownership invariant carried
    by the callback; explicit PGresult cleanup at
    happy-path End; NULL sentinel prevents double-free. No
    explicit control-flow collapse (the exit paths remain), BUT
    the *invariant that must hold at every exit* is now
    maintained by the callback, not by scattered PQclear-on-error
    scaffolding. **The refactor is "collapse the error-cleanup
    logic to a single site, not the control flow itself".** That's
    still the L6 shape — collapse the DUPLICATED CLEANUP to a
    single site.
  - Behavioral delta: none observable. The `PG_CATCH` in
    `get_returning_data` currently does `PQclear` then
    `PG_RE_THROW`. Under the new invariant, the re-throw still
    happens (the executor's error propagation is unchanged), and
    the `PQclear` still happens (now via the callback firing
    during `es_query_cxt` deletion during error unwinding).
    Purely mechanical, no behavioral delta.
- **Existing PG mechanism it reuses:** row 2 of §0.5 (identical
  to C). Approach E is Approach C's mechanism + a mandatory
  deletion pass.
- **Coverage of §0 usage surface:** rows 1-20, same as C.
- **Citations:** `[scenarios: fix-memory-leak, fdw-iterate-scan,
  add-startup-hook (callback-registration idiom)]` `[personas:
  tom-lane (postgres_fdw + memory-context invariants),
  andres-freund (per-error hot path + resource ownership)]`
  `[idioms: memory-contexts.md, memory-context-api-and-dispatch.md,
  error-handling.md]`

**Verdict:** WIN — approach E2 (C-mechanism + PG_TRY deletion)
is the recommended shape.

## 6 Recommended approach

**Approach E2** — the L6-mandatory approach: register a
`MemoryContextCallback` on `estate->es_query_cxt` at Begin, own
the PGresult through it, and **delete the now-redundant PG_TRY
block in `get_returning_data`** as part of the fix. This is the
minimal-diff shape that also collapses the duplicated cleanup
scaffolding.

- **§0.5 mechanism row:** row 2 (`MemoryContextRegisterResetCallback`
  on `es_query_cxt`) — cheapest reuse, zero new API.
- **§0 coverage:** rows 1-20 all covered. Rows 7 and 13 (the
  load-bearing rows per R15a) verified in the plan's phase-end
  check via the amplified reproducer.
- **Comparison to reference impl:** none available (blind
  trilogy). Phase 4 comparison hook is in `plan.md` §14.
- **Scenarios:** `fix-memory-leak` (primary), `fdw-iterate-scan`
  (call shape), `add-startup-hook` (callback-registration
  idiom).
- **Personas:** Tom Lane (postgres_fdw maintainer + memory-context
  invariants), Andres Freund (per-error hot path + resource
  ownership).
- **Idioms:** `memory-contexts.md`,
  `memory-context-api-and-dispatch.md`, `error-handling.md`.

**What would have to be true for the alternatives to win:**

- **A or B (PG_TRY-only fixes) win** if the reproducer's error
  actually fires inside `postgresIterateDirectModify`'s frame.
  It doesn't — the div-by-zero fires in `ExecProject`. Flag if
  the user believes otherwise.
- **C-only (no PG_TRY deletion) wins** if reviewers think the
  redundant PG_TRY is defense-in-depth worth keeping. Then
  Approach C (register callback + leave PG_TRY alone) is the
  fallback. A reviewer arguing "belt-and-suspenders is fine"
  would push us there.
- **D wins** if master-only fix is acceptable. Diff-shape hint
  (+35/−27, back-patched-through PG13) says NO — back-patch is
  required.

## 7 Decisions for the user

1. **DECISION: Approach E2 vs Approach C.** E2 = register
   callback AND delete the existing PG_TRY block in
   `get_returning_data`. C = register callback, leave PG_TRY as
   belt-and-suspenders. E2 is smaller net, cleaner invariant;
   C is more conservative. Given the diff-shape hint from the
   commit message (+35/−27 SUGGESTS deletions happened), we
   default to E2. Approve, or opt for C?

2. **DECISION: Back-patch scope.** The commit is back-patched
   through PG13. Our implementation targets master. Does the
   user want us to also produce a back-patch series for PG18,
   17, 16, 15, 14, 13, or just master? Default: master only for
   the calibration; user opts in for back-patch practice.

3. **DECISION: Sister leaks (dblink, walreceiver, other
   contribs).** The commit message hints "similar leaks may
   exist in other backend modules using libpq" and Tom defers
   the universal fix to v19. Do we in-scope any sister-leak
   audit for this calibration, or hold to postgres_fdw only?
   Default: postgres_fdw only.

4. **DECISION: Where to place the callback struct.** Options:
   (a) embed `MemoryContextCallback` INSIDE
   `PgFdwDirectModifyState` as a member — simplest, no separate
   alloc; (b) palloc a separate small struct in `es_query_cxt`
   itself so it dies WITH the callback firing. (b) is idiomatic
   per `palloc.h:559-561` ("Typically the callback struct should
   be allocated within the specified context"). Default: (b).

## 8 What this brainstorm explicitly did NOT figure out

- Exact line numbers for the plan's §3 file table (Phase 2
  produces them from grep + verification).
- Whether the callback should live on `es_query_cxt` or a
  different context (Phase 2 verifies by walking the
  memory-context hierarchy at the DirectModify's Begin call
  site).
- Test surface: whether `contrib/postgres_fdw/sql/postgres_fdw.sql`
  already has a DirectModify + failing-projection test case
  that can be extended, or whether a new test file is needed
  (Phase 2 greps).
- Whether a Valgrind suppression or `MemoryContextStats` output
  needs any doc update.
- The exact wording of the comment that replaces the deleted
  PG_TRY block (Phase 2 decides once the invariant is stated).
- Regression-test scope: `postgres_fdw` has its own regress
  suite; verifying that `--suite postgres_fdw` is the right
  `meson test` invocation is Phase 2 work.

## Hand-off

Run `/pg-plan fdw_directmodify_leak` when you've picked between
Approach E2 and Approach C (DECISION 1 above) and answered
DECISIONs 2-4 inline. Default is Approach E2 with postgres_fdw-only
scope, callback struct in `es_query_cxt`.
