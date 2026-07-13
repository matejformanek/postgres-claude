# Plan — fdw_directmodify_leak

**Plan shape:** single-file (small feature: 1 file edited, 2-3 phases,
no reference impl). Anchor at parent pin `d98cefe1143` in worktree
`postgresql-dev-feature-fdw-directmodify-leak`.

## Context

- **Date drafted:** 2026-07-13.
- **Anchor commit:** `d98cefe1143` (parent-of-fix).
- **Target commit (blind, forbidden to read):** `232d8caeaaa`.
- **Author posture:** N/A — this is a shadow-implementation
  calibration, not a thread response.
- **Thread engagement:** N/A (blind; discussion thread
  `postgr.es/m/2976982.1748049023@sss.pgh.pa.us` forbidden).
- **Scenario(s):** `fix-memory-leak` (pinned).
- **Anchor drift:** none — parent pin is the base for this run.
- **Verdict:** IMPLEMENT (not REJECT).
- **Brainstorm picked:** Approach E2 — register
  `MemoryContextRegisterResetCallback` on `es_query_cxt`; delete the
  now-redundant PG_TRY in `get_returning_data`.

## §1 What this plan is

Implementation plan for **Approach E2** from
`planning/fdw_directmodify_leak/brainstorm.md` §6: fix the
`postgres_fdw` DirectModify PGresult leak by registering a
memory-context reset callback on `estate->es_query_cxt` that owns
the PGresult across all executor exit paths (happy and error), and
deleting the now-redundant PG_TRY / PG_CATCH scaffolding inside
`get_returning_data`.

- Target PG version: master.
- CF window: PG20-1 (already-landed upstream; this is a shadow-implementation
  calibration, so no CF submission is intended).
- Back-patch: NOT in scope for this calibration (see brainstorm §7
  DECISION 2). Master only.

## §2 Scope contract

**IN SCOPE:**
- Register `MemoryContextCallback` on `estate->es_query_cxt` from
  `postgresBeginDirectModify` such that the callback frees
  `dmstate->result` on both happy-path End and error-path abort.
- Delete the now-redundant `PG_TRY { … } PG_CATCH { PQclear;
  PG_RE_THROW; } PG_END_TRY` block in `get_returning_data`.
- NULL-out `dmstate->result` after `PQclear` in
  `postgresEndDirectModify` to prevent double-free from the
  reset callback.
- Comment the invariant clearly.

**OUT OF SCOPE:**
- Sister leaks in `dblink`, `walreceiver`, other libpq-using
  contribs (deferred, per brainstorm §7 DECISION 3).
- Back-patch series to PG13-PG18 (deferred, per brainstorm §7
  DECISION 2).
- Broader refactor of PgFdwDirectModifyState struct.
- Any change to `store_returning_result` (`postgres_fdw.c:4352`)
  or `PgFdwModifyState` — that's the row-by-row (non-Direct)
  modify path, which does NOT have the same leak (its PG_TRY
  covers exactly the frame that can throw).

## §3 Files that change

| File | Change type | Size | Summary | Per-file doc |
|---|---|---|---|---|
| `contrib/postgres_fdw/postgres_fdw.c` | modify | small (~+15/−10 net) | Add reset-callback registration in `postgresBeginDirectModify` (before line 2760); delete PG_TRY block in `get_returning_data` at lines 4648-4666; NULL-out `dmstate->result` in `postgresEndDirectModify` at line 2820; add `pgfdw_result_reset_callback` static helper. See §7 for the F30 ownership map. | — |
| `contrib/postgres_fdw/sql/postgres_fdw.sql` | modify | tiny (+15 lines) | Add regression test row exercising DirectModify RETURNING with mid-batch div-by-zero, verifying no crash + no leak-under-Valgrind. See §9. | — |
| `contrib/postgres_fdw/expected/postgres_fdw.out` | modify | tiny (+~20 lines) | Regenerated expected output for the new regress row. | — |

**Pin contract:** `fix-memory-leak` scenario checklist rows — see
§7 F30 pass; all one-file checklist rows land in the §3 table (this
scenario's checklist is minimal because leak fixes are inherently
site-specific).

## §4 Catalog + on-disk impact

- New `pg_proc.dat` / `pg_operator.dat` / `pg_type.dat` /
  `pg_cast.dat` / `pg_opclass.dat` entries? **No.**
- `catversion.h` bump required? **No.**
- New on-disk format? **No.**
- `genbki.pl` re-run needed? **No.**

## §5 WAL impact

- New rmgr or new info byte? **No.**
- Existing record extended? **No.**
- Replay function changes? **No.**
- `pg_waldump` updates? **No.**
- Hot Standby conflict generation? **No.**

## §6 Locking + concurrency

- New LWLock? **No.**
- New heavyweight lock mode? **No.**
- Buffer lock ordering? **No.**
- Atomic vs spinlock decisions? **No.**
- SSI predicate-lock implications? **No.**

The change is purely local to the postgres_fdw DirectModify path
and does not touch any shared-memory synchronization primitive.
Note: `MemoryContextCallback` chain manipulation
(`mcxt.c:568-578`) is not thread-shared — it's a per-backend
per-context linked list, mutated only by the owning backend.

## §7 Memory + resource management (F30 ownership grep-pass)

**F30 mandate:** for every "PGresult X is owned by Y" claim, walk the
producer / consumer sites via grep and record the file:line map.

**Command run:**
```
grep -RnE 'PGresult|PQclear|PG_TRY|PG_CATCH' contrib/postgres_fdw/postgres_fdw.c
```
Results: 88 hits over 28 non-blank lines from the pattern group.
Below is the DirectModify-scoped subset (the fix's blast radius);
non-DirectModify sites are enumerated separately at the bottom to
confirm they are unaffected.

### PGresult acquisition + release sites in the DirectModify path

| Site | File:line | Kind | Ownership statement |
|---|---|---|---|
| A1 | `postgres_fdw.c:240` | struct decl | `PGresult *result;` in `PgFdwDirectModifyState`. Sole handle to the DirectModify PGresult. |
| A2 | `postgres_fdw.c:2670` | producer of dmstate | `dmstate = palloc0(sizeof(PgFdwDirectModifyState));` — `dmstate->result` starts NULL. |
| A3 | `postgres_fdw.c:4597` | ACQUIRE | `dmstate->result = pgfdw_get_result(dmstate->conn);` — sole acquisition. If this line does not execute (query error, connection error), `dmstate->result` remains NULL. |
| A4 | `postgres_fdw.c:4598-4601` | consumer / possible throw | `if (PQresultStatus(...) != ...) pgfdw_report_error(ERROR, dmstate->result, ...)`. `pgfdw_report_error` calls `PQclear(dmstate->result)` internally on this path (verified by inspection of `connection.c` `pgfdw_report_error`). |
| A5 | `postgres_fdw.c:4652` | reader | `make_tuple_from_result_row(dmstate->result, dmstate->next_tuple, ...)` inside `get_returning_data`'s PG_TRY. |
| A6 | `postgres_fdw.c:4661-4664` | RELEASE on catch | Current defensive `PG_CATCH { PQclear(dmstate->result); PG_RE_THROW(); } PG_END_TRY;` inside `get_returning_data`. **This is the block the plan DELETES.** |
| A7 | `postgres_fdw.c:2820` | happy-path RELEASE | `PQclear(dmstate->result);` in `postgresEndDirectModify`. |

**Ownership statement verified:** the ONLY code paths that hand
`dmstate->result` to something other than `dmstate` itself are:
- A4: passes to `pgfdw_report_error` — that function `PQclear`'s
  on the error report path (this branch does NOT leak; it's the
  "PQresultStatus failed" branch, not the "PQresultStatus OK
  then executor throws mid-iteration" branch).
- A5: passes as read-only argument to
  `make_tuple_from_result_row` — no ownership transfer.

**Every acquisition (A3) is paired with a release** on ONE of:
(A4 error-path in pgfdw_report_error, A6 catch, A7 happy-path End).
The BUG: paths where the executor throws mid-iteration OUTSIDE
`get_returning_data`'s PG_TRY (e.g. div-by-zero in the local
projection of `RETURNING id, 1000/(id-50)` firing inside
`ExecProject` after Iterate has returned the slot) skip A6 AND
A7, and A3 has already run. `dmstate->result` is orphaned in
libpq's malloc pool.

### Sites OUTSIDE DirectModify — confirmed unaffected

| Site | File:line | Function | Why unaffected |
|---|---|---|---|
| N1 | `postgres_fdw.c:1653-1712` | `create_cursor` and friends | Uses local `PGresult *res`; explicit `PQclear` at line 1712; no PG_TRY needed (comment at 1706 says so). Path throws only if PQresultStatus check fails, and PQclear happens before the throw. |
| N2 | `postgres_fdw.c:3604-3638` | `close_cursor` variant | Uses `PGresult *volatile res = NULL`; PG_TRY block with PQclear at 3636 in the try, PG_END_TRY at 3638. Correct. |
| N3 | `postgres_fdw.c:3810-3888` | (see grep) | Same shape as N2. Correct. |
| N4 | `postgres_fdw.c:4352-4378` | `store_returning_result` | Row-by-row modify (non-Direct); PG_TRY at 4356, PG_CATCH at 4373 PQclears. Correct — this is the pattern DirectModify should have but doesn't across function boundaries. |
| N5 | `postgres_fdw.c:4648-4666` | `get_returning_data` (INSIDE the DirectModify path) | This IS the redundant PG_TRY the plan deletes. |
| N6-N10 | `postgres_fdw.c:4953, 5015, 5096, 5469` | analyze / cursor / async execution helpers | All use `PGresult *volatile res = NULL` + PG_TRY around the local scope; PQclears in the try; correct. |

**Conclusion of the F30 pass:** the DirectModify path is the
UNIQUE place where PGresult ownership crosses a FdwRoutine
callback boundary (`Begin` acquires nothing — `Iterate` acquires
via `execute_dml_stmt` — `End` releases). Every other libpq-using
site in `postgres_fdw.c` acquires-and-releases inside a single
function's stack frame, wrapped in that same function's PG_TRY.
The lifetime hook the fix needs (`es_query_cxt` reset callback) is
therefore ONLY needed at the DirectModify site; other sites are
already correct.

### Memory context choice

- New `MemoryContext`? **No new context** — the fix REGISTERS a
  callback on `estate->es_query_cxt`, which is created by the
  executor at `standard_ExecutorStart` and deleted at
  `standard_ExecutorEnd` (as well as on any abort path via
  `AbortCurrentTransaction` → `ExecutorEnd` in the abort branch
  or via top-level TopTransactionContext deletion cascading).
- Callback struct allocation: palloc'd in `estate->es_query_cxt`
  itself, per `palloc.h:559-561`:
  *"Typically the callback struct should be allocated within the
  specified context, since that means it will automatically be
  freed when no longer needed."*
- Long-lived state? None. Everything the callback references
  (`PGresult **` handle → `dmstate->result`) lives in state that
  outlives `es_query_cxt`'s deletion by exactly enough (see
  brainstorm §5 Approach C "cons"). `dmstate` is palloc'd in
  the executor's per-node state, whose parent is the executor's
  overall memory context (`estate->es_query_cxt`'s parent —
  `PortalContext` in ordinary Portal execution, or SPI's plan
  context in SPI paths). When es_query_cxt is being deleted, the
  parent is still alive (`MemoryContextDelete` is bottom-up:
  child first, parent still valid during child's callbacks).
  Verified in `mcxt.c:581-620` `MemoryContextCallResetCallbacks`.

## §8 Phased implementation

### Phase 1 — Add callback registration + delete PG_TRY

**Files touched:** `contrib/postgres_fdw/postgres_fdw.c`.

**Concrete edits:**

1. **New static helper** near the top of the DirectModify section
   (before `postgresBeginDirectModify` at line 2650), e.g. after
   the struct definitions block ending at line 251:

   ```c
   /*
    * Memory-context reset callback used to release the PGresult that
    * postgresBeginDirectModify / execute_dml_stmt stashes in
    * dmstate->result.  Registered on estate->es_query_cxt so that
    * happy-path End and error-path abort both release the PGresult
    * exactly once.
    */
   static void
   pgfdw_result_reset_callback(void *arg)
   {
       PGresult  **resultp = (PGresult **) arg;

       if (*resultp != NULL)
       {
           PQclear(*resultp);
           *resultp = NULL;
       }
   }
   ```

2. **Registration in `postgresBeginDirectModify`** — insert between
   the `dmstate = palloc0(...)` at line 2670 and the userid
   determination at line 2677 (OR right before line 2760, the
   function's last statement; the exact position matters little as
   long as `estate` and `dmstate` are both in scope):

   ```c
   {
       MemoryContextCallback *cb;

       cb = MemoryContextAlloc(estate->es_query_cxt,
                                sizeof(MemoryContextCallback));
       cb->func = pgfdw_result_reset_callback;
       cb->arg  = &dmstate->result;
       MemoryContextRegisterResetCallback(estate->es_query_cxt, cb);
   }
   ```

   (Using `MemoryContextAlloc` on `es_query_cxt` — NOT `palloc` in
   the current context — so the callback struct itself dies with
   the context that owns the callback list, per `palloc.h:559-561`.)

3. **Delete the PG_TRY block** in `get_returning_data` at
   `postgres_fdw.c:4648-4666`. Replace with:

   ```c
   HeapTuple    newtup;

   newtup = make_tuple_from_result_row(dmstate->result,
                                        dmstate->next_tuple,
                                        dmstate->rel,
                                        dmstate->attinmeta,
                                        dmstate->retrieved_attrs,
                                        node,
                                        dmstate->temp_cxt);
   ExecStoreHeapTuple(newtup, slot, false);
   ```

   Update the comment at line 4645-4647 to:

   ```c
   /*
    * If make_tuple_from_result_row throws, the reset callback
    * registered on es_query_cxt in postgresBeginDirectModify will
    * PQclear dmstate->result during executor teardown.  No PG_TRY
    * needed here.
    */
   ```

4. **NULL-out `dmstate->result` after happy-path release** in
   `postgresEndDirectModify` at line 2820:

   ```c
   /* Release PGresult (callback on es_query_cxt is a no-op after this). */
   PQclear(dmstate->result);
   dmstate->result = NULL;
   ```

**Inline citations:**
- `[scenarios: fix-memory-leak (primary), fdw-iterate-scan
  (call-shape context), add-startup-hook (callback-registration
  idiom)]`
- `[personas: tom-lane (postgres_fdw maintainer + memory-context
  invariant), andres-freund (per-error hot path + resource
  ownership)]`
- `[idioms: memory-contexts.md,
  memory-context-api-and-dispatch.md, error-handling.md]`
- `[calibration: L6 mandatory-approach-E (nodesubplan_leak
  precedent, brainstorm §5 Approach E section), F30 grep-pass
  (jsonpath_leak precedent, plan §7 above)]`

**Phase-end check** (R13 scope ladder application):

The edit is in `contrib/postgres_fdw/postgres_fdw.c` — a contrib
module. Applying R13:

- Not a helper-only change (affects executor-visible ownership
  invariant).
- Not a catalog change (no `.dat` / `.h` catalog).
- Not a grammar/lexer change.
- Not core executor / planner (it's contrib, and the callback
  API it uses is already public + stable).
- Not WAL / replication.
- Not ruleutils.

R13 tier match: **contrib module change**, closest to
"helper-only" but with the correctness-critical wrinkle that the
change touches error-path unwinding. The right scope is:

```
meson test -C build-debug --no-rebuild --suite postgres_fdw --suite regress
```

If the `postgres_fdw` meson suite name is different in the parent
pin, fall back to:

```
meson test -C build-debug --no-rebuild --suite regress \
    && cd build-debug/testrun/postgres_fdw && ninja test
```

**PLUS the amplified reproducer** from `baseline.md`:

```
# Manual reproducer, not automated in regress (too slow):
psql -X -f /tmp/setup.sql
(psql -X -c 'BEGIN; UPDATE t_fdw SET val=val WHERE id BETWEEN 1 AND 100 RETURNING id, 1000/(id-50); ROLLBACK;' | grep ERROR) \
    | ( for i in $(seq 1 20000); do echo 'BEGIN; UPDATE t_fdw ... RETURNING id,1000/(id-50); ROLLBACK;'; done ) \
    | psql -X &
BGPID=$!
sleep 5; ps -o rss= -p $(pgrep -f "postgres:.*t_fdw" | head -1)
sleep 20; ps -o rss= -p $(pgrep -f "postgres:.*t_fdw" | head -1)
```

RSS delta at t=25s must be **≤ 5 MB** (post-fix flat) vs the
parent-pin baseline of **+79 MB / 24 s**. If RSS still climbs
by more than 10 MB in 25s, the fix has not landed correctly.

**Tests covered by this phase:**

- TC-Direct-1: happy-path DirectModify UPDATE (no RETURNING).
- TC-Direct-2: DirectModify UPDATE with RETURNING, all rows OK.
- TC-Direct-3: DirectModify UPDATE with mid-batch failing
  RETURNING projection (`1/(id-50)`), transaction rolls back,
  no crash.
- TC-Direct-4: TC-Direct-3 in a loop of 100 iterations; RSS
  climb ≤ 1 MB.

### Phase 2 — Regression + comprehensive test suite

**Files touched:** `contrib/postgres_fdw/sql/postgres_fdw.sql` +
`contrib/postgres_fdw/expected/postgres_fdw.out`.

**Concrete edits:**

Append to `sql/postgres_fdw.sql` a new test section (before the
final `\c` or end of file):

```sql
-- ===================================================================
-- Test PGresult lifetime under DirectModify RETURNING error paths.
-- Regression for the mid-fetch error causing PGresult leak.
-- ===================================================================
BEGIN;
-- Trigger div-by-zero in local RETURNING projection.
SAVEPOINT s;
UPDATE ft2 SET c2 = c2 WHERE c1 BETWEEN 1 AND 100
    RETURNING c1, 1000/(c1-50);
ROLLBACK TO s;
-- Verify session is still healthy after the mid-fetch error.
SELECT count(*) FROM ft2 WHERE c1 BETWEEN 1 AND 100;
-- Verify a subsequent DirectModify still works.
UPDATE ft2 SET c2 = c2 WHERE c1 = 1 RETURNING c1;
COMMIT;
```

**Inline citations:** same as Phase 1 (test file inherits the
citation set).

**Phase-end check:**

```
meson test -C build-debug --no-rebuild --suite postgres_fdw
```

Expected outcome: the new regress rows pass. Expected output
(`.out`) captured on the first Phase-2 run; committed in the
same commit as the SQL.

**Tests covered by this phase:**
- TC-Direct-3 (formal regress case).
- TC-Direct-5 (session-still-healthy after the error).
- TC-Direct-6 (subsequent DirectModify works).

Note that the amplified 20 k-iteration RSS canary is NOT in the
regress suite — too slow (~25 s) and its threshold is
environment-sensitive. It stays as the manual gate in the
phase-end check per Phase 1.

## §9 Test surface

- **Regress**: `contrib/postgres_fdw/sql/postgres_fdw.sql` (see
  Phase 2). The comprehensive own-test-suite (R14) is thin here
  because the fix is a single ownership-invariant repair, not a
  new feature: the required cross-feature integration cases
  (savepoint, PL/pgSQL, prepared, transactions) are exercised by
  TC-Direct-3 through TC-Direct-6 in the SQL file above.
- **Isolation**: none needed (single-backend leak).
- **TAP**: none needed (no cross-backend / replication path).
- **`src/test/modules/`**: none.
- **amcheck**: none.
- **pgbench**: none.
- **Contrib regression**: the fix IS in contrib; regress covers it.
- **Manual reproducer**: the 20 k-iteration RSS canary from
  `baseline.md`. Not in the regress suite; documented as the
  Phase-1 phase-end check gate.
- **Valgrind**: the commit message hint says
  "visible under Valgrind". Optional additional verification:
  `meson test -C build-debug --setup valgrind --suite postgres_fdw`
  if the Valgrind harness is available. Not required for this
  calibration.

## §10 Docs

- SGML page(s)? **No** — postgres_fdw's public docs describe
  behaviour, not internals; there's no user-observable change.
- `release-N.sgml` entry? **Would be needed if this were being
  submitted upstream** — the entry lives in the fix commit's
  message + the release notes section (Tom's actual commit
  presumably touched `doc/src/sgml/release-*.sgml`). For this
  calibration, **out of scope**: we're not submitting.
- GUC docs? **No** — no new GUC.
- System-catalog doc? **No** — no catalog change.

## §11 Patch-series structure

Single patch. Two commits in `dev/` per R5 (one per phase), but
squashed to a single upstream patch if submitted.

- **Commit 1 (Phase 1):** "Fix PGresult leak in postgres_fdw
  DirectModify via reset callback."
- **Commit 2 (Phase 2):** "Add regression coverage for
  DirectModify RETURNING error paths."

Both use upstream commit-message style (per R5 + the
`commit-message-style` skill).

## §12 CommitFest landing strategy

**Not applicable** — this is a shadow-implementation calibration
against an already-landed upstream commit (`232d8caeaaa` by Tom
Lane, landed 2025-05-30). No CF submission is intended.

If it WERE being submitted:

- CF window: N/A (already landed).
- Likely reviewer: Tom Lane (postgres_fdw maintainer, memory-context
  invariants). Persona reflex from `knowledge/personas/tom-lane.md`
  (per SKILL.md guidance).
- Second reviewer: Andres Freund (per-error hot-path, resource
  ownership).
- Pre-mail self-review checklist: `review-checklist` skill.
- Commit message style: `commit-message-style` skill (upstream PG
  style, NOT meta).

## §13 Known risks + unknowns

1. **Blocker: the plpgsql EXCEPTION handler unwinding path.**
   [severity: high] When a plpgsql `EXCEPTION WHEN OTHERS`
   handler catches a mid-fetch error, the sub-transaction that
   ran the failing DirectModify aborts. Does the sub-abort delete
   the executor state's `es_query_cxt`? plpgsql runs the SQL via
   SPI (`SPI_execute`), which creates its own executor state
   whose `es_query_cxt` is a child of SPI's "SPI plan" memory
   context. On sub-abort, SPI's plan context is reset (see
   `spi.c` `AtEOSubXact_SPI` → `SPI_freetuptable` etc.), which
   cascades to `es_query_cxt` deletion, which fires our
   callback. **Verify at Phase-2 test time** by adding a
   plpgsql-wrapped test case, if we haven't hit it inadvertently
   via the SAVEPOINT test in TC-Direct-3.

   **Mitigation:** add TC-Direct-7:

   ```sql
   DO $$
   BEGIN
     UPDATE ft2 SET c2 = c2 WHERE c1 BETWEEN 1 AND 100
       RETURNING c1, 1000/(c1-50);
   EXCEPTION WHEN division_by_zero THEN NULL;
   END; $$;
   -- Then run a 100-iteration loop of the same DO block; verify RSS flat.
   ```

2. **High: sister leaks in other contribs may lull us into a
   false sense of security.** [severity: medium] The plan
   deletes ONE PG_TRY block. Other sites in the file
   (`store_returning_result`, `close_cursor`, etc.) use the same
   PG_TRY idiom AND still need it, because they acquire+release
   within a single stack frame. **Mitigation:** the F30 grep-pass
   in §7 categorized the 28 PG_TRY/PGresult sites; only the
   DirectModify path was flagged as needing lifetime-hook
   ownership. Do NOT delete PG_TRY blocks at N1-N10.

3. **Medium: `MemoryContextCallback` struct lifetime.** [severity:
   medium] The `cb` is palloc'd via `MemoryContextAlloc` on
   `es_query_cxt`. When `es_query_cxt` is deleted, the callback
   runs, THEN the context memory is freed. If the callback tried
   to read from `cb->arg`'s target after the callback ran, we'd
   have UAF. It doesn't — the callback ends with `*resultp =
   NULL` and returns. Safe.

4. **Medium: double-registration under async execution.**
   [severity: medium] `postgres_fdw` supports asynchronous
   execution (line 4568: `dmstate->conn_state->pendingAreq`). If
   `postgresBeginDirectModify` is called twice on the same node
   (rescan?), we'd register two callbacks. `es_query_cxt` fires
   ALL callbacks; on the second fire, `dmstate->result` is
   already NULL (first callback nulled it), so the second is a
   safe no-op. **Verify** by grepping `postgres_fdw.c` for
   `ReScanForeignScan` — if DirectModify supports rescan,
   confirm the pattern is safe. Search: `git grep
   ReScanDirectModify contrib/postgres_fdw/`. Handle in Phase 1
   if issue found.

5. **Medium: PG_TRY volatile-local semantics.** [severity:
   medium] After deleting the PG_TRY in `get_returning_data`, are
   there any locals that used to be `volatile`-annotated because
   of PG_TRY? Inspection of the current code (lines 4648-4666)
   shows only `HeapTuple newtup` inside the try, which is a
   local write-once value; no `volatile` needed. Safe.

6. **Low: callback fires on `MemoryContextReset` (not just
   Delete).** [severity: low] If some code path RESETS
   `es_query_cxt` mid-query (e.g. `MemoryContextResetOnly`), the
   callback would fire prematurely — we'd `PQclear` a still-in-use
   PGresult. Verify no such site exists.
   `grep 'MemoryContextReset.*es_query_cxt' src/backend/executor/`
   — if hits, we need to switch to a callback on a different
   context. **Result:** none — `es_query_cxt` is deleted, not
   reset, by executor.

7. **Low: back-patch to PG13-PG18.** [severity: low] Out of scope
   per §2, but noted: the `MemoryContextRegisterResetCallback`
   API predates PG13 (`palloc.h:134`; API landed in PG10 or
   earlier). Compatible for back-patch if user opts in later.

## §14 Phase-zero validation + Phase-4 comparison hook

### Phase-zero (pre-implementation) checks

Before Phase 1 starts, verify:

- `postgres_fdw.c:240` still declares `PGresult *result` in
  `PgFdwDirectModifyState`.
- `postgres_fdw.c:2670` still calls `palloc0` for the dmstate.
- `postgres_fdw.c:4597` still writes into `dmstate->result` from
  `pgfdw_get_result`.
- `postgres_fdw.c:4648-4666` still contains the PG_TRY /
  PG_CATCH / PQclear / PG_RE_THROW block.
- `postgres_fdw.c:2820` still calls `PQclear(dmstate->result)` in
  `postgresEndDirectModify`.
- `src/include/utils/palloc.h:134` still declares
  `MemoryContextRegisterResetCallback` with the signature the
  plan assumes.
- `git grep ReScanForeignScan contrib/postgres_fdw/` — check
  §13 risk 4.
- `git grep -n 'MemoryContextResetOnly.*es_query_cxt'
  src/backend/executor/` — check §13 risk 6.

### Phase-4 comparison hook (post-implementation)

Pre-declared axes for `comparison.md` (Phase 4 of the
calibration, run after Phase-3 implementation lands the fix and
we unblind against `232d8caeaaa`):

- **Axis 1: approach chosen.** Did Tom pick A / B / C / D / E2?
  Our recommendation is E2.
- **Axis 2: placement of registration.** Where in
  `postgresBeginDirectModify` did the registration land? Ours is
  positioned after `palloc0` at line 2670 (top of function). Did
  Tom put it elsewhere?
- **Axis 3: callback struct location.** Ours is a separate
  `MemoryContextAlloc` on `es_query_cxt`. Did Tom embed it in
  `PgFdwDirectModifyState`?
- **Axis 4: did the PG_TRY get deleted?** Our fix deletes it
  (Approach E2). Did Tom's? If not, that's an L6 miss on our
  part or a defensive-programming choice on Tom's.
- **Axis 5: what got NULLed out?** We NULL `dmstate->result`
  after happy-path `PQclear`. Did Tom?
- **Axis 6: comment shape.** How does Tom document the new
  invariant?
- **Axis 7: back-patch shape.** Does the fix look identical on
  master / PG18 / … / PG13, or did it need per-branch adaptation?
- **Axis 8: L6 approach-E pick.** Did Tom pick the
  restructure-to-single-exit shape (our E2), or the
  add-on-top shape (Approach C)? If E2, L6 fires correctly and
  matches the L6 rule intent. If C, L6's mandatory-enumeration
  is still validated but the "recommended approach" default
  needs re-thinking.
- **Axis 9: diff size.** We estimate +15/−10. Tom's is +35/−27.
  If our diff is smaller by a factor of 2, we likely miscounted
  the docs / comment updates. Reconcile.
- **Axis 10: sister-leak scope.** Did Tom's commit or its
  discussion address dblink / walreceiver? (Per triage: he
  explicitly deferred to v19. Confirm.)

Phase-4 `comparison.md` writes results against each axis + names
the L-lesson (L7?) if a new failure mode emerges.

## Hand-off

Run `/pg-implement fdw_directmodify_leak` to start Phase 1.
