# `contrib/vacuumlo/vacuumlo.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~544
- **Source:** `source/contrib/vacuumlo/vacuumlo.c`

Client utility (libpq frontend) that removes **orphaned** large
objects from one or more databases. Algorithm: build a TEMP TABLE of
every LO oid in `pg_largeobject_metadata` (or `pg_largeobject` pre-9.0),
then DELETE rows whose OID is referenced by any user-table column of
type `oid` or `lo`; whatever remains in the temp table is unreferenced
and gets `lo_unlink`'d. Single-file program. [verified-by-code]
[from-comment]

## API / entry points

- `main` (vacuumlo.c:437-544) — getopt_long parse, then loops over
  remaining argv calling `vacuumlo(database, &param)` per DB.
  Exit code is the count of failed databases.
  [verified-by-code]
- `vacuumlo(database, param)` (vacuumlo.c:61-411) — the workhorse.
  Connects, opens transaction, builds the orphan set, deletes orphans
  in batches of `transaction_limit` LOs per transaction.
  [verified-by-code]
- `usage` (vacuumlo.c:413-433) — `-l/--limit`, `-n/--dry-run`,
  `-v/--verbose`, plus standard libpq connection flags.
  [verified-by-code]

## Notable invariants / details

- **Server version branch** at vacuumlo.c:154-157: ≥ 9.0 reads
  `pg_largeobject_metadata`, < 9.0 falls back to `SELECT DISTINCT
  loid FROM pg_largeobject`. Modern PG is always the first branch,
  but the fallback is still compiled in. [verified-by-code]
- **Race-with-concurrent-lo_create handling** is the central
  correctness story. The "find references" snapshot is built
  *before* the orphan DELETE loop, so any `lo_create` between
  snapshot and delete IS in danger of being unlinked even though a
  later transaction will reference it. Mitigation: vacuumlo runs in
  **READ COMMITTED** with the temp-table populated under one
  snapshot, but each user-table scan re-reads — so an LO created
  *after* `vacuum_l` is populated will not be in `vacuum_l` and
  hence won't be `lo_unlink`'d. The dangerous case is
  `lo_create + table-insert` happening between vacuum_l
  population and the per-column DELETE FROM vacuum_l: the new LO
  is in vacuum_l and the new reference is not yet visible.
  [verified-by-code] [ISSUE-correctness: TOCTOU on concurrent
  lo_create (likely)]
- **Filtering convention**: only schemas not matching `^pg_` are
  scanned (vacuumlo.c:202). This intentionally excludes the
  pg_largeobject table itself plus system catalogs and the temp
  table (which lives in `pg_temp_NN`). [verified-by-code]
  [from-comment]
- **transaction_limit default = 1000** (vacuumlo.c:471), tunable
  with `-l`. Comment at vacuumlo.c:267-272 explains why batching
  matters: since 9.0 the backend acquires one lock per deleted LO,
  so deleting too many per transaction risks the shmem lock-table
  full error. `0` disables periodic commits — and the FETCH still
  asks for 1000 at a time so it does NOT make the whole job one
  txn; the FETCH count fallback is `1000L` (line 298).
  [verified-by-code] [from-comment]
- Per-column SQL is `DELETE FROM vacuum_l WHERE lo IN (SELECT
  <field> FROM <schema>.<table>)` (vacuumlo.c:240-243). Identifiers
  are escaped via `PQescapeIdentifier`. [verified-by-code]
- Uses a `CURSOR WITH HOLD` (vacuumlo.c:285-286) so periodic COMMITs
  inside the FETCH loop don't invalidate the cursor.
  [verified-by-code]
- `password` is `static`, so a successful prompt-and-connect on DB-1
  carries the password forward into DB-2's connect attempt
  (vacuumlo.c:73-77). [verified-by-code] [from-comment]
- Calls `ALWAYS_SECURE_SEARCH_PATH_SQL` post-connect (vacuumlo.c:139)
  so subsequent queries that don't fully schema-qualify aren't
  hijacked. The orphan-finding query at lines 194-202 explicitly
  uses bare names — relying on the reset. [verified-by-code]

## Potential issues

- vacuumlo.c:184-202 + 240-262. **TOCTOU window between vacuum_l
  population and per-column DELETE** can incorrectly mark a
  newly-created LO as orphan. Concretely: T1 `lo_create + INSERT
  into mytable`; T0 (vacuumlo) populates `vacuum_l` between
  T1's `lo_create` commit and its INSERT commit; T0 scans
  `mytable` and does not see T1's row; T0 ends up unlinking T1's
  LO. The README acknowledges "run when no one is writing LOs";
  this is the central usage caveat. [ISSUE-correctness:
  documented TOCTOU on concurrent lo_create+INSERT (likely)]
- vacuumlo.c:269-272. **Per-column DELETE inside the wrapping
  transaction may run for hours** on large schemas. The first
  CREATE TEMP TABLE through the FETCH/lo_unlink loop is one logical
  unit that holds a WITH HOLD cursor across periodic commits but
  still pins resources. No idle-in-transaction timeout escape; a
  DBA running vacuumlo against a hot cluster can see autovacuum
  block on it. [ISSUE-style: long-running tx without progress
  reporting beyond `-v` (nit)]
- vacuumlo.c:333-342. On `lo_unlink` failure, if the txn is in
  PQTRANS_INERROR the loop breaks but the wrapping `commit` at
  line 383 will fail with the txn already aborted; the error
  message is generic. [ISSUE-correctness: post-failure cleanup
  emits cascading error message (nit)]
- vacuumlo.c:496-499. `strtol(optarg, NULL, 10)` for `-l` accepts
  trailing garbage without complaint; `"100abc"` is silently 100.
  Matches other libpq frontends but worth noting. [ISSUE-style:
  loose numeric parse (nit)]
- vacuumlo.c:505-507. Port parsing rejects only `port < 1 || port
  > 65535`. Trailing garbage like `"5432foo"` becomes 5432 with no
  warning. [ISSUE-style: loose port parse (nit)]
- vacuumlo.c:194-202. **Implicit assumption that every user-table
  column named OID-typed actually holds large-object references**.
  Tables that use `oid` columns for non-LO purposes (e.g.,
  pre-9.3 catalog-style usage in user schemas) will have their
  OIDs treated as LO references. Modern PG mostly removed this
  ambiguity but pre-9.3-restored schemas can hit it.
  [ISSUE-correctness: type-`oid` not necessarily LO (maybe)]
- vacuumlo.c:139-147. `ALWAYS_SECURE_SEARCH_PATH_SQL` is called
  AFTER `PQexec` already returned, and *its* result is checked,
  but the queries above (the transaction begin, the temp table
  creation) run with whatever search_path the server defaulted
  to. In practice, the temp-table query schema-qualifies via
  `pg_largeobject_metadata` (unqualified — relies on pg_catalog
  being in search_path), which is the standard default but not
  guaranteed if the user has tampered with `search_path`. Race
  is small. [ISSUE-security: ordering of secure-search-path call
  (nit)]

## Cross-references

- `knowledge/issues/vacuumlo.md` — per-extension issue register
  (create from template if absent).
- `contrib/lo/` — the `lo` data type vacuumlo also recognises.
- `source/src/backend/storage/large_object/inv_api.c` —
  `lo_unlink` semantics + locking.
- Companion utility: `oid2name` (same `struct _param` + connect-loop
  pattern).

<!-- issues:auto:begin -->
- [Issue register — `vacuumlo`](../../../issues/vacuumlo.md)
<!-- issues:auto:end -->
