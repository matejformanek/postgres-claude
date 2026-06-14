# RelFileLocator — physical-file identity

`RelFileLocator` is the 3-field identifier used everywhere
the storage layer needs to address a relation's on-disk file —
distinct from `pg_class.oid` (the logical identity) so that
file rewrites (REINDEX, CLUSTER, VACUUM FULL) can replace the
file without breaking outstanding references. The companion
`RelFileLocatorBackend` adds a backend identifier for
temp-relation files. Both are pure value types — comparable,
hashable, no padding bytes.

Anchors:
- `source/src/include/storage/relfilelocator.h:58-77` — the
  structs [verified-by-code]
- `knowledge/data-structures/buffertag.md` — partner;
  `BufferTag` embeds the same 3 fields plus fork + block
- `knowledge/subsystems/access-heap.md` — heap storage
- `.claude/skills/wal-and-xlog/SKILL.md` — WAL records carry
  RelFileLocator + block

## Definition

```c
typedef struct RelFileLocator
{
    Oid           spcOid;       /* tablespace */
    Oid           dbOid;        /* database */
    RelFileNumber relNumber;    /* relation */
} RelFileLocator;
```

[verified-by-code `relfilelocator.h:58-63`]

Three fields that together address a relation's on-disk file:

- **`spcOid`** — `pg_tablespace.oid` of the tablespace. The
  symlink at `pg_tblspc/<spcOid>` resolves to the actual file
  system path.
- **`dbOid`** — `pg_database.oid` of the database. Zero for
  **shared relations** (cross-database catalogs like
  `pg_database`, `pg_authid`); when zero, `spcOid` MUST be
  `GLOBALTABLESPACE_OID`.
- **`relNumber`** — `pg_class.relfilenode`. **NOT
  `pg_class.oid`** — these can differ after a file rewrite.

## relNumber vs pg_class.oid

[from-comment `relfilelocator.h:35-39`]

> relNumber identifies the specific relation. relNumber
> corresponds to pg_class.relfilenode (NOT pg_class.oid,
> because we need to be able to assign new physical files to
> relations in some situations). Notice that relNumber is
> only unique within a database in a particular tablespace.

The split exists so that:
- REINDEX, CLUSTER, VACUUM FULL can write a new file (new
  `relfilenode`) while the logical relation (`pg_class.oid`)
  is unchanged.
- The old file remains usable by backends with open
  references; cleanup happens when no one holds the old
  `relNumber` anymore.

A backend that needs the file (storage manager, buffer
flush, WAL replay) uses `RelFileLocator`. A backend that
needs the relation (SQL execution, catalog access) uses
`pg_class.oid` plus a relcache lookup.

## The "mapped relations" exception

[from-comment `relfilelocator.h:50-53`]

> in pg_class, relfilenode can be zero to denote that the
> relation is a "mapped" relation, whose current true
> filenode number is available from relmapper.c. Again, this
> case is NOT allowed in RelFileLocators.

Mapped relations (`pg_class`, `pg_attribute`, etc.) have a
catalog-internal indirection: their `pg_class.relfilenode = 0`
and the actual file number lives in the relmap files. By the
time a `RelFileLocator` is constructed, the indirection has
been resolved.

So callers building a RelFileLocator from a relcache entry
must use `RelationGetSmgr(rel)->smgr_rlocator.locator`, NOT
the raw `pg_class.relfilenode`.

## The padding-bytes invariant

[from-comment `relfilelocator.h:54-57`]

> various places use RelFileLocator in hashtable keys.
> Therefore, there *must not* be any unused padding bytes in
> this struct.

Same constraint as `BufferTag`. Hash-key correctness requires
that two logically-equal structs are byte-equal too. The
current layout (Oid + Oid + Oid where RelFileNumber is `Oid`
underneath) has no padding on common architectures, but
adding a field would require padding analysis.

## The backend variant

```c
typedef struct RelFileLocatorBackend
{
    RelFileLocator locator;
    ProcNumber    backend;
} RelFileLocatorBackend;

#define RelFileLocatorBackendIsTemp(rlocator) \
    ((rlocator).backend != INVALID_PROC_NUMBER)
```

[verified-by-code `relfilelocator.h:73-80`]

For temp relations — backend-local objects that don't
persist across crash. The `backend` field is the owning
process's `ProcNumber`. `RelFileLocatorBackendIsTemp` is the
predicate.

Non-temp relations always have `backend = INVALID_PROC_NUMBER`.
Code that handles both consults the helper rather than
checking `backend` directly.

## Equality

```c
#define RelFileLocatorEquals(l1, l2) \
    ((l1).relNumber == (l2).relNumber && \
     (l1).dbOid     == (l2).dbOid     && \
     (l1).spcOid    == (l2).spcOid)
```

[verified-by-code `relfilelocator.h:89-92`]

Compares `relNumber` first because it's the most likely to
differ between two distinct relations
[from-comment `relfilelocator.h:83-87`]. Sequential elimination
on the field most likely to mismatch is the standard fast-path.

## Where it shows up

- **smgr layer** — every storage-manager call takes a
  `RelFileLocatorBackend` (with the backend tag for temp).
- **buffer manager** — `BufferTag` carries the three
  RelFileLocator fields + fork + block. `BufTagGetRelFileLocator`
  reconstructs.
- **WAL records** — every record that touches a page
  serializes the RelFileLocator. Recovery reads it to redo.
- **pg_class observers** — backends that need the relfilenode
  call `RelationGetRelid(rel)` for the logical id +
  `rel->rd_locator` for the physical one.

## Common review-time concerns

- **Don't use `pg_class.oid` to address files.** The file may
  have been replaced. Use `RelFileLocator`.
- **`dbOid = 0` requires `spcOid = GLOBALTABLESPACE_OID`** —
  the invariant is asserted; violating it crashes in dev.
- **Mapped relations** — never construct a RelFileLocator
  with `relfilenode = 0`. Go through the smgr layer.
- **Padding bytes** — adding a field requires `_Static_assert`
  to verify no padding.
- **Temp tables** — use `RelFileLocatorBackend`; bare
  RelFileLocator would lose the per-backend distinguishability.

## Invariants

- **[INV-1]** `dbOid = 0` iff `spcOid = GLOBALTABLESPACE_OID`
  (shared-relation rule).
- **[INV-2]** `relNumber` is `pg_class.relfilenode`, NOT
  `pg_class.oid`.
- **[INV-3]** Struct must have NO padding bytes (hash-key
  correctness).
- **[INV-4]** Temp relations require `RelFileLocatorBackend`
  with a non-`INVALID_PROC_NUMBER` backend tag.
- **[INV-5]** Mapped relations resolve through relmap; the
  `RelFileLocator` carries the resolved value.

## Useful greps

- All RelFileLocator readers/writers:
  `grep -RIn 'RelFileLocator\b' source/src/backend | head -30`
- The mapped-relation resolution:
  `grep -RIn 'RelationMapOidToFilenumber\|relmapper' source/src/backend/utils/cache`
- Equality usage:
  `grep -RIn 'RelFileLocatorEquals' source/src/backend | head -20`

## Cross-references

- `knowledge/data-structures/buffertag.md` — embeds the same
  3 fields + fork + block.
- `knowledge/subsystems/access-heap.md` — heap storage that
  consumes RelFileLocator.
- `knowledge/subsystems/storage-buffer.md` — buffer manager
  that takes RelFileLocator-derived tags.
- `.claude/skills/wal-and-xlog/SKILL.md` — WAL records carry
  RelFileLocator + block + fork.
- `.claude/skills/catalog-conventions/SKILL.md` — pg_class
  vs RelFileLocator distinction.
- `source/src/include/storage/relfilelocator.h` — definition
  + helpers.
- `source/src/backend/storage/smgr/smgr.c` — smgr layer
  that uses RelFileLocatorBackend.
