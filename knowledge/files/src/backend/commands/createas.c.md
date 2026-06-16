# `src/backend/commands/createas.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~637
- **Source:** `source/src/backend/commands/createas.c`

Execution of `CREATE TABLE ... AS` (a.k.a. `SELECT INTO`) and
`CREATE MATERIALIZED VIEW`. Both syntaxes share the same plumbing:
the SELECT's output is captured by a private `DR_intorel` DestReceiver
that creates the target rel during `rStartup` and inserts the rows in
`receiveSlot`. [verified-by-code]

## API / entry points

- `ExecCreateTableAs(pstate, stmt, params, queryEnv, qc)` — top-level
  utility entry for `CREATE TABLE AS` / `CREATE MATERIALIZED VIEW`.
  Returns the new relation's `ObjectAddress`, or `InvalidObjectAddress`
  if `IF NOT EXISTS` matched. Dispatches between three code paths:
  (a) wrapped EXECUTE statement → `ExecuteQuery`; (b) `WITH NO DATA` →
  `create_ctas_nodata` (skip planner+executor); (c) ordinary SELECT →
  plan + exec via private receiver. [verified-by-code]
- `GetIntoRelEFlags(intoClause)` — returns `EXEC_FLAG_WITH_NO_DATA` if
  `skipData`. Exposed because EXPLAIN and PREPARE need the same flag.
  [verified-by-code]
- `CreateTableAsRelExists(stmt)` — pre-creation existence check;
  handles `IF NOT EXISTS` with the extension-membership safety check.
  [verified-by-code]
- `CreateIntoRelDestReceiver(intoClause)` — public factory for the
  `DR_intorel` receiver. Called from `dest.c` via `CreateDestReceiver`
  with NULL intoClause; the caller then fills in `self->into`.
  [from-comment]

## Notable invariants / details

- `DR_intorel` struct (line 51-61): receivers are stack-allocated
  pseudo-objects; `pub` is the DestReceiver public part. Private:
  `into`, `rel`, `reladdr`, `output_cid`, `ti_options`, `bistate`.
- MATVIEW pathway: always sets `skipData = true` for the initial
  `intorel_startup` and then re-enters via `RefreshMatViewByOid` (line
  274-298), which gives a single code path with locked-down security
  context (security-restricted ops + restricted `search_path`).
  [from-comment]
- `WITH NO DATA` path bypasses the rewriter, planner, and executor,
  building `ColumnDef`s directly from the SELECT's targetlist (line
  280-298). Comment justifies it as a dump/restore safety: avoids
  running planner before dependencies are set up. [from-comment]
- Snapshot dance (line 332-334): `PushCopiedSnapshot(GetActiveSnapshot)`
  + `UpdateActiveSnapshotCommandId()` so the SELECT sees results of
  preceding planner-stable-function calls; mirrors EXPLAIN path.
- `intorel_startup` (line 459) creates the target table, opens it at
  `AccessExclusiveLock`, rejects RLS via `check_enable_rls`, and
  conditionally initializes `BulkInsertState`. The MATVIEW-populated
  flag (`SetMatViewPopulatedState`) is set tentatively here, before
  actually filling. [verified-by-code]
- `intorel_receive` (line 583) skips inserts entirely if `skipData`.
  Otherwise calls `table_tuple_insert` with `TABLE_INSERT_SKIP_FSM`
  (set in startup) and `bistate`. Comment notes slot may not match
  target's slotcallback type; trade-off vs allocation of a typed slot.
  [from-comment]
- Lock release: `intorel_shutdown` closes the rel with `NoLock` to
  retain the lock until commit. [from-comment]

## Potential issues

- Line 541-546. RLS check rejects only `RLS_ENABLED`; comment "policies
  not yet implemented for this command". Tracked invariant. [ISSUE-undocumented-invariant: RLS-on-matview lifecycle not specified (maybe)]
- Line 575-576. Speculative defensive `Assert` on `smgr_targblock ==
  InvalidBlockNumber` flagged as "may be harmless, but this function
  hasn't planned for it". [ISSUE-stale-todo: speculative Assert (nit)]
- `intorel_destroy` does only `pfree(self)`; `bistate` is freed in
  `intorel_shutdown`. If `shutdown` were skipped (e.g. ExecutorEnd
  error after startup but before shutdown), `bistate` leaks. The
  `intorel_destroy` doesn't try to recover. May be OK if the per-query
  context is destroyed. [unverified]

## Synthesized by
<!-- backlinks:auto -->

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `commands`](../../../../issues/commands.md)
<!-- issues:auto:end -->
