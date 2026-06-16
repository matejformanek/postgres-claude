# pgstattuple.c

Covers `source/contrib/pgstattuple/pgstattuple.c` (604 lines): the
classic full-relation tuple-stats walker — counts live/dead tuples,
sums their lengths, sums per-page free space. Supports heap +
btree/hash/gist indexes (NOT gin/spgist/brin).

## One-line summary

`pgstattuple(text|regclass)` returns
`(table_len, tuple_count, tuple_len, tuple_percent, dead_tuple_count,
dead_tuple_len, dead_tuple_percent, free_space, free_percent)` after
a full sequential scan of every page in the relation — for heap
under `SnapshotAny` + `SnapshotDirty` visibility, for indexes
walking every page and counting `ItemIdIsDead` line pointers.

## Public API / entry points

- `pgstattuple(text relname)` —
  `source/contrib/pgstattuple/pgstattuple.c:169`. **Pre-1.5 entry:
  has hardcoded `superuser()` check** (`:175`).
- `pgstattuple_v1_5(text relname)` — `:195`. **v1.5+ entry, NO
  `superuser()` check.** Relies on
  `REVOKE EXECUTE … FROM PUBLIC; GRANT EXECUTE … TO
  pg_stat_scan_tables` from
  `pgstattuple--1.4--1.5.sql:19-20`.
- `pgstattuplebyid(regclass)` — `:210`. Same superuser check.
- `pgstattuplebyid_v1_5(regclass)` — `:228`. No check.
- Per-AM page handlers (static, called by `pgstat_index`):
  - `pgstat_btree_page` — `:411`.
  - `pgstat_hash_page` — `:455`.
  - `pgstat_gist_page` — `:503`.
- `pgstat_heap` — `:316`. The heap-specific scan.

## Key invariants

- INV-1: **Predefined-role gate, not superuser-only.** v1.5+
  functions have `REVOKE … FROM PUBLIC` + `GRANT TO
  pg_stat_scan_tables` in `pgstattuple--1.4--1.5.sql`
  [verified-by-code: `grep REVOKE` shows lines 19, 20, 36, 37, 44,
  45, 56, 57, 74, 75, 91, 92, 99, 100, 118, 119, 135, 136]. The C
  superuser check stays in the pre-1.5 entry points (`:175, :215`)
  because — comment at `:163-165` — "the library might be upgraded
  without the extension being upgraded, meaning that in pre-1.5
  installations these functions could be called by any user." Lock
  the C entry until the SQL is upgraded.
- INV-2: `pg_stat_scan_tables` is a predefined role; member of
  `pg_monitor` per
  `source/src/include/catalog/pg_auth_members.dat:18` [verified-by-code].
  So `pg_monitor` ⊃ `pg_stat_scan_tables` ⊃ EXECUTE on
  pgstattuple_v1_5 functions.
- INV-3: Non-local temp rejection in `pgstat_relation` (`:252`)
  [verified-by-code].
- INV-4: Heap-AM check at `:331-335`: rejects non-`HEAP_TABLE_AM_OID`
  unless `RELKIND_SEQUENCE` (sequences are heap-backed but don't
  show it in catalogs — `:329-330` comment).
- INV-5: `indisvalid` required for indexes (`:265-269`); a mid-CIC
  index errors with `ERRCODE_OBJECT_NOT_IN_PREREQUISITE_STATE`.
- INV-6: GIN/SPGIST/BRIN explicitly rejected (`:282-298`); the AM
  switch hits "not supported".

## Notable internals

**Heap scan uses `SnapshotAny` + per-tuple `SnapshotDirty` visibility.**
`:338`: `table_beginscan_strat(rel, SnapshotAny, …)` — scan sees
EVERY tuple including dead, recently dead, in-progress. Then for
each tuple, `:353`: `HeapTupleSatisfiesVisibility(tuple,
&SnapshotDirty, hscan->rs_cbuf)` — `SnapshotDirty` makes
in-progress count as live. The result: "live" = "would be visible
to a transaction that ignores in-progress xacts treating them as
committed" — a slightly different definition than the standard MVCC
snapshot. Comment doesn't explain this choice; it matches
historical pgstattuple semantics.

**Per-tuple buffer share-lock dance.** `:351, :364`:
`LockBuffer(rs_cbuf, BUFFER_LOCK_SHARE)` then unlock around the
visibility call. Required because `HeapTupleSatisfiesVisibility`
inspects hint bits that may be set under share lock by other
backends.

**Sequential-scan + parallel free-space sweep.** `:374-384`: as
`heap_getnext` advances through tuples, the code separately reads
every page in lockstep to call `PageGetExactFreeSpace`. This means
each page is touched once for the tuple scan AND once for the
free-space scan — but the buffer access uses a `BAS_BULKREAD`
strategy (set up by `table_beginscan_strat` with `is_bulkread=true`
implicitly) so the buffer is already cached. The `block <= tupblock`
loop guarantees no page is missed when `heap_getnext` skips empty
pages.

**Index scan uses `BAS_BULKREAD` strategy.** `:546`:
`GetAccessStrategy(BAS_BULKREAD)` — prevents the scan from
displacing useful buffers in shared_buffers. Same idiom as VACUUM.

**Index extension lock.** `:552-554`:
`LockRelationForExtension(rel, ExclusiveLock); … UnlockRelationForExtension`.
This is taken *just to get `RelationGetNumberOfBlocks`* — why? To
prevent racing with concurrent extension while the SRF runs. Heavy
hammer but consistent with how concurrent index reads stabilize.

**Per-AM page filtering.** `pgstat_btree_page` (`:411-449`) checks
`P_IGNORE` (deleted or half-dead → count as fully free), `P_ISLEAF`
(walks items), else internal (ignored — internal pages are
"administrative"). `pgstat_hash_page` (`:455-497`) similarly classifies
by `LH_PAGE_TYPE`. `pgstat_gist_page` (`:503-531`) walks leaf items
only.

## Trust boundary / Phase D surface

**This is THE predefined-role canonical example.** Unlike
pageinspect (hardcoded `superuser()` everywhere), pgstattuple is
the model for "expose a privileged debug surface via a predefined
role." `pg_stat_scan_tables` is meant for *monitoring tooling* —
backups, monitoring dashboards, pgwatch2. Membership grants:

- pgstattuple, pgstattuplebyid (full scans).
- pgstatindex (btree), pgstathashindex, pgstatginindex.
- pg_relpages (cheap; just a stat call).
- pgstattuple_approx (VM-skipping fast path).

The role intentionally does NOT grant `get_raw_page` (pageinspect
is superuser-only) — i.e. you can get aggregate stats without
getting raw bytes.

**RLS bypass via tuple count.** Members of `pg_stat_scan_tables`
can run `pgstattuple` on a table protected by RLS and get the EXACT
count of live tuples — even if `SELECT COUNT(*) FROM t` returns 0
for them under RLS. They cannot get the tuple *contents*, but the
count itself is a leak. **[ISSUE-security: pgstattuple gives
`pg_stat_scan_tables` members the true row count of RLS-protected
tables; `SELECT COUNT(*)` would return RLS-filtered count
(confirmed)]** —
`source/contrib/pgstattuple/pgstattuple.c:346-362`.

**Cost-amplification / DoS.** `pgstattuple` on a 10 TB table reads
every page sequentially under `BUFFER_LOCK_SHARE`. This is a
**full sequential scan with per-page buffer share-lock churn**. On
a busy system, calling `pgstattuple('hot_huge_table')` from a
monitoring role amplifies I/O and may starve other backends of
buffer-mapping-table slots. There's no `statement_timeout`-style
mitigation built in beyond what the GUC provides.
**[ISSUE-security: pgstattuple full-scan is a cost-amplification
vector for `pg_stat_scan_tables` members; no LIMIT or sample-mode;
admins should pair with statement_timeout (likely)]** — `:316-405`.
The `_approx` variant in `pgstatapprox.c` exists explicitly to
mitigate this.

**Lock posture.** `AccessShareLock` on the relation (`:182, :203,
:221, :234`). Does NOT conflict with autovacuum's
`ShareUpdateExclusiveLock`. VACUUM can run concurrently and prune
tuples; the count is approximate even without `_approx` because
of this. Lock IS sufficient to prevent ALTER TABLE / DROP / TRUNCATE
racing with the scan.

**No `ShareUpdateExclusiveLock`** — the task brief asked about this.
Confirmed: just `AccessShareLock`. So a concurrent autovacuum will
run uninterrupted and the counts may shift mid-scan.

**Heap-AM-only enforcement** at `:331-335`. The function correctly
errors for `RELKIND_FOREIGN_TABLE`, custom table AMs other than
heap, etc.

**SnapshotDirty semantic surprise.** `:341, :353`: tuples
INSERT_IN_PROGRESS count as "live" (the function uses
SnapshotDirty). This is different from VACUUM's
`HeapTupleSatisfiesVacuum` semantics. Users reading pgstattuple
output to size autovacuum thresholds may get a slightly inflated
live-count.
**[ISSUE-correctness: SnapshotDirty makes INSERT_IN_PROGRESS count
as live; doesn't match VACUUM's HEAPTUPLE_LIVE definition. Affects
bloat-estimation calculations (nit, historical behavior)]** — `:353`.

**Sequence support.** Sequences pass through `pgstat_heap` (`:331`).
Result is meaningful (1 row, BLCKSZ blocks) but mostly noise. Not a
security issue.

## Cross-references

- `source/src/include/catalog/pg_authid.dat:60` —
  `pg_stat_scan_tables` predefined role definition.
- `source/src/include/catalog/pg_auth_members.dat:18` —
  `pg_stat_scan_tables` member of `pg_monitor`.
- `source/contrib/pgstattuple/pgstattuple--1.4--1.5.sql` — the
  `REVOKE`/`GRANT` discipline this file's v1.5 functions rely on.
- `source/src/backend/access/heap/heapam_visibility.c` —
  `HeapTupleSatisfiesVisibility`, the visibility check.
- `source/src/backend/utils/time/snapmgr.c` — `InitDirtySnapshot`.
- `knowledge/files/contrib/pgstattuple/pgstatapprox.c.md` — the
  approximate (VM-skip) sibling.
- `knowledge/files/contrib/pgstattuple/pgstatindex.c.md` — the
  index-specific stats.
- `knowledge/files/contrib/pageinspect/pageinspect.md` — the
  RAW-bytes contrast (superuser-only).

<!-- issues:auto:begin -->
- [Issue register — `pgstattuple`](../../../issues/pgstattuple.md)
<!-- issues:auto:end -->

## Issues spotted

- **[ISSUE-security: pgstattuple reveals true RLS-bypassed row
  count to `pg_stat_scan_tables` members (confirmed)]** —
  `source/contrib/pgstattuple/pgstattuple.c:346-362`.
- **[ISSUE-security: full-scan + per-page buffer-lock churn is a
  cost-amplification DoS vector when delegated to monitoring
  (likely)]** — `:316-405`.
- **[ISSUE-correctness: SnapshotDirty visibility counts
  INSERT_IN_PROGRESS as live; differs from VACUUM definition (nit,
  historical)]** — `:341, :353`.
- **[ISSUE-correctness: only AccessShareLock; counts are
  approximate when autovacuum runs concurrently (nit, documented
  trade-off)]**.
- **[ISSUE-defense-in-depth: GIN/SPGIST/BRIN explicitly unsupported;
  monitoring tools must special-case them or fall back to
  `_approx` (nit; expected behavior)]** — `:282-298`.
- **[ISSUE-api-shape: heap-AM-only — a custom table AM cannot use
  pgstattuple at all; `pgstattuple_approx` has the same limitation
  (nit, documented)]** — `:331-335`.
- **[ISSUE-concurrency: `LockRelationForExtension(ExclusiveLock)`
  acquired just to call `RelationGetNumberOfBlocks` in
  `pgstat_index`; heavy for a stat read (nit; intentional but
  worth noting)]** — `:552-554`.
