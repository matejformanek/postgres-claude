# contrib-pgstattuple (physical heap + index statistics)

- **Source path:** `source/contrib/pgstattuple/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.5` (per `pgstattuple.control`)
- **Trusted:** no (per-function REVOKE FROM PUBLIC; v1.5
  removed the superuser gate, replaced with role grants)

## 1. Purpose

Compute **actual** disk-level statistics — live tuple bytes,
dead tuple bytes, free space, average tuple length, fillfactor
realization — on heap tables and on btree/hash/gin index
files. Two variants per probe: an exact scanner and an
approximate sampler. Used for storage-bloat audits, vacuum
scheduling, and index-rebuild decisions.

Critically: this is the **disk truth**, not the planner's
estimate. Where `pg_stat_user_tables` shows what the cumulative
stats subsystem says, pgstattuple shows what's actually on the
pages.

## 2. The three files

| File | LOC | Coverage |
|---|---|---|
| `pgstattuple.c` | 603 | Heap-table exact scan |
| `pgstatindex.c` | 810 | btree / hash / gin / spgist / gist index introspection |
| `pgstatapprox.c` | 371 | Heap sampling-based estimator |

[verified-by-code via `wc -l source/contrib/pgstattuple/*.c`]

## 3. SQL surface

### Heap functions

| Function | Behavior |
|---|---|
| `pgstattuple(regclass)` | Exact scan: every page read; tuple counts + sizes + free space |
| `pgstattuple_approx(regclass)` | Sample-based estimate; uses VM all-visible / all-frozen bits to skip whole pages |
| `pg_relpages(regclass)` | Number of pages in main fork |

[verified-by-code `pgstattuple.c:53-58` + `pgstatapprox.c:28-29`]

### Index functions

| Function | Behavior |
|---|---|
| `pgstatindex(regclass)` | btree-specific page-type tally + leaf density |
| `pgstathashindex(regclass)` | hash index bucket + overflow + bitmap stats |
| `pgstatginindex(regclass)` | GIN pending list + posting tree |
| `pgstatindexbyid(oid)` | OID-passed variants (bypass schema lookup) |

[verified-by-code `pgstatindex.c:53-62`]

## 4. Exact heap scan — what it returns

```sql
SELECT * FROM pgstattuple('mytable');

 table_len     | 8192000   -- bytes
 tuple_count   | 1000
 tuple_len     | 6000000   -- bytes
 tuple_percent | 73.24
 dead_tuple_count | 5
 dead_tuple_len   | 32000
 dead_tuple_percent | 0.39
 free_space     | 2000000  -- bytes
 free_percent   | 24.41
```

The differential `100 - tuple_percent - dead_tuple_percent -
free_percent` is the **page-header overhead** (~3-5% for a
typical heap). Numbers don't sum to 100 because of headers.

## 5. The approximate-sample heap path

`pgstattuple_approx` (`pgstatapprox.c:307`) is the production-
safe variant:

1. Walk the VM fork. For pages marked all-visible/all-frozen,
   credit the live-tuple bytes from VM accounting; skip the
   actual page read.
2. For un-VM-bit pages, read the page and count tuples.
3. Sample a fraction of un-VM-bit pages rather than reading all.

The result has a documented error bound — typically within 1%
of exact for well-vacuumed tables, larger for tables with
heavy update churn.

**Use `pgstattuple_approx` on production tables.**
`pgstattuple` (exact) reads every page, which is fine on
small tables but turns into a multi-hour I/O storm on
multi-TB tables.

## 6. v1.5: the superuser → role-grant transition

[from-comment `pgstatapprox.c:292-297`]

> As of pgstattuple version 1.5, we no longer need to check
> if the user is a superuser because we REVOKE EXECUTE on the
> function from PUBLIC.

Before 1.5, the C code checked `superuser()` and ERRORed if
not. After 1.5, the SQL grant model handles it — DBAs grant
`EXECUTE` on specific functions to specific roles. Cleaner;
matches how every other contrib extension handles
permission control.

Note that the `_v1_5` suffix on every function name in the C
code [verified-by-code `pgstatindex.c:60-62, pgstatapprox.c:29`]
is the version-bridge mechanism — the old `pgstattuple()` C
function keeps the legacy permission check; `pgstattuple_v1_5`
trusts the SQL grants.

## 7. Index introspection details

### `pgstatindex` (btree)

Returns: version, tree level, index size in bytes, root block,
internal pages, leaf pages, empty pages, deleted pages, avg
leaf density (%), leaf fragmentation (%).

A heavily-updated btree shows declining leaf density and
rising leaf fragmentation — the classic "REINDEX me" signal.
A 30% drop from a freshly-loaded baseline is a typical
reindex trigger.

### `pgstathashindex` (hash)

Returns: version, bucket-count, primary buckets used, overflow
pages, bitmap pages, dead pages, free percentage in primary
buckets, free percentage in overflow pages.

Overflow page accumulation indicates the hash function isn't
distributing well for the actual data; consider `REINDEX`.

### `pgstatginindex` (gin)

Returns: version, pending list page count, pending tuple count,
pending list fragmentation. A long pending list means the
deferred-merge has fallen behind; `VACUUM` (which merges the
pending list) is overdue.

## 8. Production-use guidance

- **Exact heap = `pgstattuple` = lots of I/O.** Sized-down
  tables (<100K rows) are fine; multi-GB tables should use
  `pgstattuple_approx`.
- **All functions hold `AccessShareLock`** — safe to run
  alongside DML. They share-pin every page they read.
- **Output is point-in-time** — not transactional. A
  concurrent VACUUM can move bytes between dead → free
  between two columns of one row.
- **Compare against `pg_class.relpages` + `reltuples`** —
  pgstattuple is the ground truth; if planner estimates
  diverge by > 10%, run ANALYZE (or check
  default_statistics_target).
- **`pg_relpages` is the cheap probe** — single catalog
  lookup + smgr nblocks query. Use it before deciding whether
  to run the full pgstattuple.

## 9. Invariants

- **[INV-1]** Exact-scan functions read every page in the
  main fork; cost is O(relation_size).
- **[INV-2]** Sample functions use VM bits to skip
  all-visible / all-frozen pages.
- **[INV-3]** v1.5+ functions trust SQL grants; pre-1.5
  functions enforce superuser in C code.
- **[INV-4]** All functions acquire `AccessShareLock`; no
  blocking of writers.
- **[INV-5]** Index functions are AM-specific —
  `pgstatindex` on a GIN index ERRORs, etc.

## 10. Useful greps

- All entry points:
  `grep -n 'PG_FUNCTION_INFO_V1' source/contrib/pgstattuple/*.c`
- The VM-aware sample logic:
  `grep -n 'visibilitymap\|VISIBILITYMAP_ALL' source/contrib/pgstattuple/pgstatapprox.c`
- v1.5 permission transition:
  `grep -n '_v1_5\|superuser' source/contrib/pgstattuple/*.c`

## 11. Cross-references

- `.claude/skills/debugging/SKILL.md` — pgstattuple is the
  storage-bloat ground truth.
- `knowledge/subsystems/access-heap.md` — heap layout this
  function decodes.
- `knowledge/subsystems/access-nbtree.md` — btree page
  structure exposed by `pgstatindex`.
- `knowledge/subsystems/storage-buffer.md` — every page read
  goes through the buffer manager.
- `knowledge/idioms/visibility-map-update.md` — VM bits the
  sample-based heap scanner uses.
- `source/contrib/pgstattuple/pgstattuple.c` — exact-heap.
- `source/contrib/pgstattuple/pgstatapprox.c` — VM-aware sample.
- `source/contrib/pgstattuple/pgstatindex.c` — index-specific.
