# src/backend/utils/cache/relfilenumbermap.c

## Purpose

Backend-local cache mapping `(reltablespace, relfilenumber)` → `pg_class.oid`,
i.e. the reverse of the more common OID→relfilenode lookup. Primary consumer:
logical decoding / `ReorderBuffer`, which sees physical relfilenumbers in WAL
and needs to resolve them to logical relation OIDs. [from-comment, inferred]
(`relfilenumbermap.c:3-4`)

## Role in PG

- Backed by an `HTAB` in `CacheMemoryContext` keyed by `RelfilenumberMapKey`
  (`reltablespace`, `relfilenumber`) — value is the resolved relid (or
  `InvalidOid` cached as a negative entry).
- Registers a relcache invalidation callback
  (`RelfilenumberMapInvalidateCallback`, `relfilenumbermap.c:51`) that flushes
  matching entries on `pg_class` changes; also flushes all negative entries on
  *any* invalidation so subsequent lookups re-probe.

## Key functions

- `RelidByRelfilenumber(reltablespace, relfilenumber)` —
  (`relfilenumbermap.c:141`) the only public entry point. Normalises
  `MyDatabaseTableSpace` → 0 to match `pg_class.reltablespace` storage
  convention (`relfilenumbermap.c:155-156`). Cache hit returns
  immediately; miss does:
  - if `GLOBALTABLESPACE_OID`: call `RelationMapFilenumberToOid(filenumber,
    /*shared=*/true)` (`relfilenumbermap.c:179-185`).
  - else: `systable_beginscan` on `pg_class` via
    `ClassTblspcRelfilenodeIndexId`, skipping `RELPERSISTENCE_TEMP` rows,
    erroring if a duplicate non-temp row is seen
    (`relfilenumbermap.c:196-228`).
  - falls back to mapped-but-not-shared via
    `RelationMapFilenumberToOid(filenumber, /*shared=*/false)` if no
    pg_class row matches (`relfilenumbermap.c:234-235`).
  - Re-checks for concurrent inserts after the index scan before
    HASH_ENTER, erroring on the "corrupted hashtable" path
    (`relfilenumbermap.c:243-245`).
- `InitializeRelfilenumberMap()` — lazily builds the HTAB and the
  shared `relfilenumber_skey[2]` index scan keys
  (`relfilenumbermap.c:86-127`). Importantly creates the hash *after*
  `fmgr_info_cxt` to avoid leaving a partially-initialised global on
  OOM (`relfilenumbermap.c:111-115`).
- `RelfilenumberMapInvalidateCallback(Datum, Oid)` — sync flush;
  walks the entire HTAB and removes matching plus all negative entries
  (`relfilenumbermap.c:52-79`).

## State / globals

- `RelfilenumberMapHash` — backend-local HTAB.
- `relfilenumber_skey[2]` — pre-built `ScanKey` for the two-column
  index scan, allocated in `CacheMemoryContext` (`relfilenumbermap.c:33`).

## Phase D notes

- Caveat on temp relations (`relfilenumbermap.c:132-138`): temp rels can
  share relfilenumbers across backends, and the cache can't see other
  backends' proc numbers, so it deliberately skips temp rows. Callers
  who need a temp resolution must do it themselves.
- Negative caching of `InvalidOid` means a malicious/buggy caller probing
  many bogus filenumbers grows the hash unboundedly until the next
  invalidation. Bounded in practice because filenumbers come from WAL
  decoding, not user input. [inferred]

## Potential issues

- [ISSUE-correctness: the `Assert` on
  `classform->reltablespace == reltablespace` (`relfilenumbermap.c:225-226`)
  uses the post-normalisation value (0 for MyDatabaseTableSpace) — fine
  in production where Asserts are off, but worth checking the assert
  semantics if reltablespace=0 is passed for a non-MyDatabaseTableSpace
  lookup (low)]
- [ISSUE-undocumented-invariant: caller must hold no relation locks
  that would deadlock with `AccessShareLock` on `pg_class`; not
  documented (low)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils`](../../../../../issues/utils.md)
<!-- issues:auto:end -->
