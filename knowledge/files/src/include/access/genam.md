# `access/genam.h` — generic index AM wrappers + system-catalog scan

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/access/genam.h`)

## Role
Generic AM-dispatching wrappers (`index_insert`, `index_beginscan`,
`index_getnext_*`, `index_bulk_delete`, etc.) that call into the
`IndexAmRoutine` function pointers, plus the `systable_*` family used for
heap-or-index scans of pg_catalog (the most common backend pattern for
catalog access).

## Public API
- `IndexBuildResult` (`genam.h:38`) — heap_tuples + index_tuples counters
  returned by `ambuild`.
- `IndexVacuumInfo` (`genam.h:52`) — input to ambulkdelete and
  amvacuumcleanup; carries `analyze_only`, `estimated_count`, `message_level`,
  `num_heap_tuples`, `strategy` (BufferAccessStrategy).
- `IndexBulkDeleteResult` (`genam.h:83`) — output: pages_newly_deleted,
  pages_deleted, pages_free, num_index_tuples, tuples_removed.
- `IndexBulkDeleteCallback` typedef (`genam.h:95`).
- `IndexUniqueCheck` enum (`genam.h:123`) — `UNIQUE_CHECK_NO`,
  `UNIQUE_CHECK_YES` (blocking), `UNIQUE_CHECK_PARTIAL` (deferrable),
  `UNIQUE_CHECK_EXISTING` (recheck).
- `IndexOrderByDistance` (`genam.h:133`) — value + isnull pair.
- Generic AM funcs (`genam.h:143`-`208`): `index_open`, `try_index_open`,
  `index_close`, `index_insert`, `index_insert_cleanup`, `index_beginscan`,
  `index_beginscan_bitmap`, `index_rescan`, `index_endscan`, `index_markpos`,
  `index_restrpos`, `index_parallelscan_*`, `index_beginscan_parallel`,
  `index_getnext_tid`, `index_fetch_heap`, `index_getnext_slot`,
  `index_getbitmap`, `index_bulk_delete`, `index_vacuum_cleanup`,
  `index_can_return`, `index_getprocid`, `index_getprocinfo`,
  `index_store_float8_orderby_distances`, `index_opclass_options`.
- Indexam support routines (`genam.h:214`-`223`): `RelationGetIndexScan`,
  `IndexScanEnd`, `BuildIndexValueDescription`,
  `index_compute_xid_horizon_for_tuples`.
- `systable_*` family (`genam.h:228`-`251`): `systable_beginscan`,
  `systable_getnext`, `systable_recheck_tuple`, `systable_endscan`,
  `systable_beginscan_ordered`, `systable_getnext_ordered`,
  `systable_endscan_ordered`, `systable_inplace_update_begin/finish/cancel`.

## Invariants
- `UNIQUE_CHECK_YES` may block waiting for a conflicting transaction;
  `UNIQUE_CHECK_PARTIAL` must not block and must not throw. `[from-comment]`
  (`genam.h:106`-`117`).
- `BuildIndexValueDescription` returns a string for error messages —
  must respect ACLs (it's the source of the "Key (col)=(val)" hint).
  See heap relation's permission check inside `BuildIndexValueDescription`
  itself for the row-level redaction. `[inferred]`.
- `systable_beginscan` chooses heap vs. index automatically based on
  `indexOK` and whether the system catalog has a fitting index.
  `[from-comment]` (`genam.h:228`).
- `systable_inplace_update_begin` is the "update without MVCC" backdoor
  used for pg_class.relfrozenxid and similar single-field hot-path updates.
  `[from-comment]` (`genam.h:243`-`251`).

## Notable internals
- `IndexBulkDeleteResult` may be extended by the AM (returned struct can be
  larger; this is the prefix). `[from-comment]` (`genam.h:71`-`73`).
- `num_heap_tuples` may be `-1` when estimated_count is true. `[from-comment]`
  (`genam.h:50`).
- `IndexScanDesc` and `SysScanDesc` are forward-declared here; the actual
  struct lives in `relscan.h`.

## Trust-boundary / Phase D surface

`systable_*` is the dominant pattern for backend catalog access. It's used
by ACL checks, dependency walks, name resolution — anything that reads
pg_catalog. A bug in systable visibility semantics (e.g., snapshot wrongly
chosen) becomes a system-wide trust failure.

**[ISSUE-audit-gap: BuildIndexValueDescription must self-redact (informational)]** —
The function is responsible for not leaking key values to users who lack
SELECT on the underlying columns. Enforcement is inside the C function, not
visible at the header. The hazard is well-known (the "leakproof" debate).
`genam.h:217`-`218`. Cross-reference: A14 amcheck's permission story.

**[ISSUE-correctness: `systable_inplace_update_*` bypasses MVCC (informational)]** —
This is documented and intentional, used only for hot updates of pg_class
counters where transactional update would be too expensive. Misuse can
break catalog invariants. `genam.h:243`-`251`.

**[ISSUE-api-shape: `IndexBulkDeleteResult` is "first field" of an extensible
struct (low)]** — AMs may return a longer struct. Callers must not assume
sizeof. Mistakenly memcpy'ing or freeing as `IndexBulkDeleteResult` could
miss AM-private trailing fields. `genam.h:71`-`73`.

## Cross-refs
- `knowledge/files/src/include/access/amapi.h` — function-pointer table
  these wrappers dispatch through.
- `knowledge/files/src/include/access/relscan.h` — `IndexScanDescData`,
  `SysScanDescData`.
- `knowledge/files/src/include/access/table.h` — for `table_open` flavor.
- A14 amcheck Phase D: BuildIndexValueDescription redaction parallels
  amcheck's RLS bypass concerns.

<!-- issues:auto:begin -->
- [Issue register — `include-access`](../../../../issues/include-access.md)
<!-- issues:auto:end -->

## Issues
1. **[ISSUE-audit-gap: BuildIndexValueDescription column redaction is inside-C-only (informational)]**
   — `genam.h:217`-`218`.
2. **[ISSUE-correctness: systable_inplace_update bypasses MVCC by design (informational)]**
   — `genam.h:243`-`251`.
3. **[ISSUE-api-shape: IndexBulkDeleteResult is an extensible-struct prefix (low)]**
   — `genam.h:71`-`73`.
