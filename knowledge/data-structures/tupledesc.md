# TupleDesc — tuple shape descriptor

`TupleDesc` is the **schema** of a tuple — how many
attributes, their types, sizes, alignment, names, and
constraints. Every place that processes tuples (catalog
reads, query execution, function returns) consults a
TupleDesc to know what's in the bytes. Lives in
backend-local memory; ref-counted so that long-running
queries can share descriptors with the catalog cache.

Anchors:
- `source/src/include/access/tupdesc.h:148-163` — the
  struct [verified-by-code]
- `source/src/backend/access/common/tupdesc.c` —
  implementation
- `knowledge/data-structures/tupletableslot.md` — companion;
  slots carry a TupleDesc reference
- `knowledge/data-structures/heap-tuple-layout.md` — the
  on-disk format TupleDesc describes

## The struct

```c
typedef struct TupleDescData
{
    int          natts;                          /* # of attrs */
    Oid          tdtypeid;                       /* composite type OID */
    int32        tdtypmod;                       /* typmod for type */
    int          tdrefcount;                     /* ref count, -1 = uncounted */
    int          firstNonCachedOffsetAttr;       /* perf hint */
    int          firstNonGuaranteedAttr;         /* perf hint */
    TupleConstr *constr;                         /* constraints or NULL */
    CompactAttribute compact_attrs[FLEXIBLE_ARRAY_MEMBER];
} TupleDescData;

typedef struct TupleDescData *TupleDesc;
```

[verified-by-code `tupdesc.h:148-163`]

The flexible array tail holds **compact** attribute
metadata (cached offset, length, byval flag) — a slim
representation used in hot deformation paths. Full
`pg_attribute` records are stored AFTER the compact array
in the same allocation [verified-by-code `tupdesc.h:171-174`
via the `TupleDescAttrAddress` macro].

## Two views of attribute metadata

[verified-by-code `tupdesc.h:177-206`]

- **`TupleDescAttr(tupdesc, i)`** — returns
  `FormData_pg_attribute *` — the full attribute record:
  name, type OID, typmod, length, byval, alignment, storage
  strategy, etc. Used when full attribute info is needed
  (column lookup, type inference).
- **`TupleDescCompactAttr(tupdesc, i)`** — returns
  `CompactAttribute *` — a smaller slim record with just
  the hot-path fields (cached offset, length, alignment,
  byval flag, isnull flag).

Hot-path code (tuple deformation, slot getsomeattrs) uses
the compact form to avoid cache misses on
`FormData_pg_attribute`'s wider layout.

## The reference-count semantics

[verified-by-code `tupdesc.h:153`]

`tdrefcount` controls lifetime:

- **`-1`** — uncounted; caller manages lifetime (typical
  for short-lived ad-hoc descs).
- **`>= 0`** — reference-counted. Each
  `PinTupleDesc` increments; each `ReleaseTupleDesc`
  decrements; when count hits 0, the descriptor is freed.

Counted descriptors live in `CacheMemoryContext` so they
survive across transactions. Used by:
- The relcache (each relation's TupleDesc).
- Plan caches (cached query plans pin their result
  TupleDescs).
- Cursors (held open across transactions).

## TupleConstr — column-level constraints

[verified-by-code `tupdesc.h:38-48`]

```c
typedef struct TupleConstr
{
    AttrDefault   *defval;        /* DEFAULT expressions */
    ConstrCheck   *check;         /* CHECK constraints */
    AttrMissing   *missing;       /* missing-value markers */
    uint16         num_defval;
    uint16         num_check;
    bool           has_not_null;
    bool           has_generated_stored;
    bool           has_generated_virtual;
} TupleConstr;
```

Only present when the relation HAS constraints — most
ephemeral / function-result TupleDescs have `constr =
NULL`.

## The creation entry points

```c
extern TupleDesc CreateTemplateTupleDesc(int natts);
extern TupleDesc CreateTupleDesc(int natts, Form_pg_attribute *attrs);
extern TupleDesc CreateTupleDescCopy(TupleDesc tupdesc);
extern TupleDesc CreateTupleDescTruncatedCopy(TupleDesc tupdesc, int natts);
extern TupleDesc CreateTupleDescCopyConstr(TupleDesc tupdesc);
```

[verified-by-code `tupdesc.h:208-216`]

- **`CreateTemplateTupleDesc(N)`** — allocate space for N
  attributes; caller populates via `TupleDescInitEntry`.
- **`CreateTupleDesc(N, attrs)`** — populate from existing
  `Form_pg_attribute` array.
- **`CreateTupleDescCopy`** — duplicate; drops constraints.
- **`CreateTupleDescTruncatedCopy`** — duplicate first N
  attributes only.
- **`CreateTupleDescCopyConstr`** — duplicate including
  constraints.

After populating attributes, `TupleDescInitEntryCollation`
or similar sets per-attribute collation; finally
`TupleDescFinalize` validates the descriptor + populates
the compact arrays.

## firstNonCachedOffsetAttr / firstNonGuaranteedAttr

[verified-by-code `tupdesc.h:154-158`]

Two cached indices used to short-circuit common operations:

- **`firstNonCachedOffsetAttr`** — index of the first
  attribute whose offset can't be statically computed.
  Attributes before this index can use their
  `attcacheoff`; attributes at-or-after must compute on
  the fly.
- **`firstNonGuaranteedAttr`** — index of the first
  attribute that might be NULL, missing, dropped, or
  pass-by-reference. Attributes before this are guaranteed
  to exist + fit in their slot.

These let `slot_getsomeattrs` (the hot deformation path)
skip the per-attribute null-check / type-check for the
guaranteed prefix.

## tdtypeid + tdtypmod — the composite-type tagging

Every TupleDesc tags its tuples with a composite type:

- **`tdtypeid`** — OID of the composite type (a row in
  `pg_type` of `typtype = 'c'`).
- **`tdtypmod`** — modifier (mostly used for anonymous
  RECORDs).

For real tables, `tdtypeid = pg_class.reltype` (the auto-
created composite type for the row shape).

For function results, anonymous JOINs, etc., a synthesized
record-type OID is used.

This tagging matters for **runtime type checking** — code
that receives a HeapTuple can verify it matches an
expected shape by comparing tdtypeid.

## The TupleDescInitEntry helpers

```c
TupleDescInitEntry(desc, attnum, name, atttypeid, atttypmod, attndims);
TupleDescInitEntryCollation(desc, attnum, collation);
```

Common patterns:

```c
TupleDesc desc = CreateTemplateTupleDesc(3);
TupleDescInitEntry(desc, 1, "id",    INT4OID,  -1, 0);
TupleDescInitEntry(desc, 2, "name",  TEXTOID,  -1, 0);
TupleDescInitEntry(desc, 3, "value", FLOAT8OID, -1, 0);
TupleDescFinalize(desc);
```

Used by SQL function definitions that build their result
shape programmatically (SRFs returning RECORD).

## Common review-time concerns

- **Always use `TupleDescAttr(desc, i)`** to access
  attributes. Don't index `compact_attrs` directly with the
  wide form.
- **Refcounted descriptors must be pinned across
  transaction boundaries.** Cursors / plan caches do this.
- **`TupleDescFinalize` is required** after population.
- **`compact_attrs` is populated by Finalize.** Initial
  state is undefined.
- **Cloning drops refcount** — `CreateTupleDescCopy`
  returns `tdrefcount = -1`.

## Invariants

- **[INV-1]** `natts` matches the actual count of
  `compact_attrs` entries.
- **[INV-2]** `TupleDescFinalize` populates compact_attrs;
  must be called before use.
- **[INV-3]** Refcounted descriptors (tdrefcount >= 0)
  must be released; uncounted (tdrefcount = -1) freed by
  context.
- **[INV-4]** `tdtypeid` tags the tuple's composite type
  for runtime checks.
- **[INV-5]** `firstNonCachedOffsetAttr` / `firstNonGuaranteedAttr`
  are perf hints; safe to ignore but lose hot-path speed.

## Useful greps

- All TupleDesc allocation patterns:
  `grep -RIn 'CreateTemplateTupleDesc\|CreateTupleDesc' source/src/backend | head -20`
- Refcount manipulation:
  `grep -RIn 'PinTupleDesc\|ReleaseTupleDesc' source/src/backend | head -10`
- The compact attribute optimization:
  `grep -n 'CompactAttribute\|compact_attrs' source/src/backend/access/common/tupdesc.c | head -10`

## Cross-references

- `knowledge/data-structures/tupletableslot.md` — slot
  carries a TupleDesc reference; deformation reads it.
- `knowledge/data-structures/heap-tuple-layout.md` — the
  on-disk format TupleDesc describes.
- `knowledge/idioms/cache-invalidation-registration.md` —
  relcache TupleDescs are invalidated via sinval.
- `.claude/skills/fmgr-and-spi/SKILL.md` — SRFs build a
  TupleDesc for their result shape.
- `.claude/skills/catalog-conventions/SKILL.md` — pg_class
  / pg_attribute drive TupleDescs.
- `source/src/include/access/tupdesc.h` — full type +
  inline accessors.
- `source/src/backend/access/common/tupdesc.c` —
  implementation.
