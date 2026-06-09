# verify_common.c + verify_common.h

Covers `source/contrib/amcheck/verify_common.c` (191 lines) and
`source/contrib/amcheck/verify_common.h` (28 lines). Source pin: `4b0bf0788b0`.

## One-line summary

Shared locking + sanity-check wrapper used by `bt_index_check`,
`bt_index_parent_check`, and `gin_index_check` to open the heap-then-index pair
under the requested LOCKMODE, switch userid to the table owner, sandbox GUC
changes, and reject indexes that aren't checkable (wrong AM, other-session
temp, `!indisvalid`, unlogged-on-standby).

## Public API / entry points

- `void amcheck_lock_relation_and_check(Oid indrelid, Oid am_id,
  IndexDoCheckCallback check, LOCKMODE lockmode, void *state)` —
  `verify_common.c:62-150`. The one extern. Callback signature
  `void (*)(Relation rel, Relation heaprel, void *state, bool readonly)` is
  defined in `verify_common.h:20-23`. `readonly` is derived from `lockmode ==
  ShareLock` at `verify_common.c:134` [verified-by-code].
- Static helpers (file-local):
  - `index_checkable(rel, am_id)` — `verify_common.c:161-191` — relkind / AM /
    other-temp / `indisvalid` checks; raises `ERROR` on failure.
  - `amcheck_index_mainfork_expected(rel)` — `verify_common.c:37-50` —
    swallows unlogged-during-recovery with `NOTICE`, returns `false`.

## Key invariants

- **Table-before-index lock order.** `IndexGetRelation()` looked up without a
  lock first, then `table_open(heapid, lockmode)`, then `index_open(indrelid,
  lockmode)` — `verify_common.c:83-119`. The comment at `:75-82` explicitly
  cites deadlock avoidance as the reason. After both opens, the heap-OID
  lookup is repeated under the lock (`verify_common.c:126`) to defend against
  a drop/recreate race that could have netted us the wrong table.
- **Userid switch + security restriction.** Once `heaprel` is opened, the
  function calls `SetUserIdAndSecContext(heaprel->rd_rel->relowner,
  save_sec_context | SECURITY_RESTRICTED_OPERATION)` —
  `verify_common.c:93-95` [verified-by-code]. The comment at `:88-92` calls
  out the reason: any expression-index function evaluated below this point
  runs **as the table owner, not the SQL invoker**. This is the same defense
  that REINDEX / index build uses against owner-trojaned index expressions.
- **GUC nest level.** `NewGUCNestLevel()` at `:96` and matching `AtEOXact_GUC(false,
  save_nestlevel)` at `:137` — any `SET LOCAL` an opclass / index expression
  fires while we are checking is rolled back at end, even on success.
- **Lock release before commit.** Comment at `verify_common.c:142-146` says
  release is safe early because nothing called underneath triggers shared
  cache invalidations, so the usual "hold-locks-until-commit" pattern can be
  relaxed [from-comment].
- **No permission check.** Comment at `verify_common.c:155-159` is explicit:
  permissions are intentionally NOT checked here. The functions are kept
  unsafe by default via `REVOKE ALL ... FROM PUBLIC` in the install scripts
  (see `amcheck--1.0.sql:23-24`, `amcheck--1.3--1.4.sql:27-28`,
  `amcheck--1.4--1.5.sql:9`). **A superuser GRANT bypasses the safety
  layer entirely**; the C side trusts that the GRANT was deliberate.
- **`relkind` must be `RELKIND_INDEX`** (`:163-167`), `relam` must equal
  `am_id` passed in (`:169-174`), no other-session temp (`:176-181`),
  `indisvalid` must be true (`:183-188`).
- **Unlogged on standby is silently NOTICEd, not failed.** `:44-48` — checker
  function returns NULL/void.

## Notable internals

- The lock mode is chosen by the caller (`AccessShareLock` for the basic
  flavor, `ShareLock` for parent / readonly flavor) and propagated unchanged.
  Lock release at `:147-149` uses the same mode.
- The `IndexGetRelation(indrelid, true)` call (missing_ok=true) at `:83` is
  deliberate so we postpone the not-an-index complaint to `index_checkable`,
  which produces a nicer error.
- The `index_checkable` failure path returns `false` from
  `amcheck_index_mainfork_expected` for unlogged-on-standby, in which case
  `:133` short-circuits past the callback. No corruption is reported — the
  fork doesn't exist.

## Trust boundary / Phase D surface

- **REVOKE FROM PUBLIC is the only access control.** There is no
  `superuser()` check, no `has_privs_of_role()` check. If the DBA has
  `GRANT EXECUTE` on `bt_index_check(regclass)` to a non-superuser, that user
  can call it on any index they can resolve a `regclass` for (which is
  effectively any visible index). The install-script intent (`amcheck--1.0.sql`
  comment "Don't want these to be available to public") is the contract.
  [verified-by-code, `verify_common.c:155-159`]
- **`SECURITY_RESTRICTED_OPERATION` defense is correct but narrow.** The
  switch-to-owner-uid blocks owner-trojaned expression-index code from running
  as the invoker, mirroring `REINDEX`. But the invoker still sees the
  `ereport` output of whatever the checker does, including
  `errdetail_internal` payloads with tid / lp / lsn coords (see e.g.
  `verify_nbtree.c:1322-1326`, `:1397-1399`). For an index on a table the
  invoker can't `SELECT` from but holds amcheck EXECUTE on, that's a
  side-channel of TID layout. [ISSUE-security: amcheck error details leak
  tid/page coordinates of a table the invoker may have no SELECT on
  (maybe)] — `verify_common.c:62-150` is the gate.
- **The post-IndexGetRelation race recheck** (`:126`) is correct but races
  with `DROP INDEX CONCURRENTLY`; if the second lookup also wins the race,
  the wrong-table case is missed. In practice the lock taken at `:86`
  prevents this.
- **No `RecoveryInProgress()` gate on the index lookup itself.** Only
  unlogged-on-standby is filtered (`:40-42`); a permanent index check during
  recovery proceeds. The comment at `:81` says "in hot standby mode this will
  raise an error when parentcheck is true" — this is the `ShareLock`-on-an-
  index path failing at `index_open` because hot standby refuses `ShareLock`.
  [from-comment]
- **No accumulation of issues.** The shared layer doesn't know about
  reporting; each callback fails closed via `ereport(ERROR)`. So at this
  layer there is no "stop on first" / "report all" distinction — only the
  heap-AM checker (`verify_heapam.c`) does that.

## Cross-references

- Backend: `commands/indexcmds.c` (`ReindexIndex` uses the same uid-switch
  pattern); `catalog/index.c` (`IndexGetRelation`); `utils/misc/guc.c`
  (`NewGUCNestLevel`, `AtEOXact_GUC`); `miscadmin.h`
  (`SECURITY_RESTRICTED_OPERATION`, `SetUserIdAndSecContext`).
- A11 sibling: `pg_amcheck` (the frontend CLI, A6) drives these SQL
  functions; per A6 it documents fail-open across databases. The backend
  here is fail-closed (`ereport(ERROR)`) — see Phase D commentary above.
- amcheck callbacks: `verify_nbtree.c:bt_index_check_callback` (line 312),
  `verify_gin.c:gin_check_parent_keys_consistency` (line 388).

## Issues spotted

- [ISSUE-audit-gap: REVOKE-FROM-PUBLIC is the only access gate; no
  `superuser()`/`has_privs_of_role()` check in C (likely)] —
  `verify_common.c:155-159` — comment is explicit ("intentionally not
  checking permissions"). A misconfigured `GRANT EXECUTE ... TO PUBLIC` (e.g.
  via a botched ALTER DEFAULT PRIVILEGES) fully exposes the checker. Defense
  is at the SQL install layer, not C, and it's silent if subverted.
- [ISSUE-security: amcheck error details leak tid/lp/page-LSN of tables the
  invoker may not be able to SELECT from (maybe)] —
  `verify_common.c:62-150` (gate) + `verify_nbtree.c:1322-1326,1397-1399`,
  `verify_heapam.c:report_corruption_internal` (consumers). Side-channel of
  physical layout if EXECUTE is granted to a low-priv user.
- [ISSUE-correctness: post-IndexGetRelation race recheck can be defeated by
  a fast drop-recreate-drop cycle (nit)] — `verify_common.c:126`. In
  practice impossible without acquiring the same OID twice with the lock
  held in between; documented as "barely possible".
- [ISSUE-documentation: behavior on hot-standby with `ShareLock` is implicit
  via `index_open` failing, not explicit in this file (nit)] —
  `verify_common.c:81`.
