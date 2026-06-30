# `src/include/storage/relfilelocator.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 100

## Role

**The (tablespace, database, relfilenode) triple** that uniquely
identifies a physical relation on disk. Used as a hashtable key
throughout the buffer manager and smgr. Renamed from
`RelFileNode` to `RelFileLocator` in PG16 to free up `RelFileNode`
for `relfilenode` field semantics.

## Triple semantics

[verified-by-code] `source/src/include/storage/relfilelocator.h:58-63`

```
RelFileLocator {
    Oid spcOid;         // pg_tablespace.oid
    Oid dbOid;          // pg_database.oid, or 0 for shared
    RelFileNumber relNumber;  // pg_class.relfilenode
}
```

- `spcOid == GLOBALTABLESPACE_OID ⟺ dbOid == 0` (shared
  relations only in global tablespace). [from-comment] lines
  41-42.
- `relNumber` is unique only within (spcOid, dbOid) — same
  relfilenode can exist across databases.
- `pg_class.reltablespace == 0` shorthand for "database default
  tablespace" is **NOT allowed** in a `RelFileLocator`; the
  real spcOid must be filled in. [from-comment] lines 44-48.
- `pg_class.relfilenode == 0` shorthand for "mapped relation"
  (relmapper.c) is **NOT allowed** here either. [from-comment]
  lines 50-52.

`RelFileLocatorBackend { locator, ProcNumber backend }` (lines
73-77) — adds the owning backend's `ProcNumber` for backend-local
(temp) relations. `INVALID_PROC_NUMBER` for regular rels.

## Invariants

- INV-1: **No padding bytes** — the struct is used as a hashtable
  key (`memcmp` semantics). All-`Oid` types ensure this naturally;
  any future field must respect alignment. [from-comment] lines
  53-56.
- INV-2: `RelFileLocatorEquals` compares `relNumber` first
  (most discriminating field). [from-comment] lines 83-87.
- INV-3: `RelFileLocatorBackendIsTemp(rl)` = backend !=
  `INVALID_PROC_NUMBER` (line 79-80).

## Trust boundary (Phase D)

- **External SQL functions that take a (spc, db, relnumber)
  tuple** (e.g. `pg_filenode_relation`, `pg_relation_filepath`)
  validate via catalog lookup before treating the inputs as a
  filesystem path. Any extension that constructs a
  `RelFileLocator` from user input without catalog cross-check
  could be tricked into reading/writing arbitrary file paths
  under `$PGDATA/base/`.
- Hashtable-key invariant (INV-1) is on-disk-format-adjacent —
  changing the struct breaks RelCache, BufferTag, SmgrRel.

## Cross-refs

- `knowledge/files/src/include/storage/buf_internals.h.md`
  (existing) — `BufferTag` embeds `RelFileLocator`
- `knowledge/files/src/include/storage/smgr.h.md` (existing)
- `knowledge/files/src/include/storage/procnumber.h.md` —
  `ProcNumber` companion

## Issues

None.

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/relfilelocator.md](../../../../data-structures/relfilelocator.md)
- [idioms/relfilenumber-rewrite.md](../../../../idioms/relfilenumber-rewrite.md)
