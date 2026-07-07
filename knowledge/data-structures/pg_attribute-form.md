# Form_pg_attribute — column metadata catalog row

`FormData_pg_attribute` is the C struct mirror of a
`pg_attribute` catalog row — one row per column per
relation. Every tuple-processing path consults it: knowing
a column's type, length, alignment, byval flag, and
nullability is essential to reading the bytes correctly.
The struct is generated from the `.dat` file via the BKI
generator; TupleDesc carries an array of these.

Anchors:
- `source/src/include/catalog/pg_attribute.h:30-160` —
  the FormData_pg_attribute struct [verified-by-code]
- `knowledge/data-structures/tupledesc.md` — companion;
  TupleDesc holds an array of these
- `.claude/skills/catalog-conventions/SKILL.md` —
  catalog DAT conventions

## The struct fields (selected)

[verified-by-code `pg_attribute.h:30-160`]

```c
typedef struct FormData_pg_attribute
{
    Oid           attrelid;     /* relation OID */
    NameData      attname;      /* attribute name */
    Oid           atttypid;     /* type OID (pg_type.oid) */
    int16         attlen;       /* type length (copied from pg_type) */
    int16         attnum;       /* attribute number (1-based; system attrs negative) */
    int32         attndims;     /* array dimensions */
    int32         attcacheoff;  /* cached offset in tuple (init -1) */
    int32         atttypmod;    /* type-specific modifier */
    bool          attbyval;     /* pass by value? */
    char          attalign;     /* alignment requirement */
    char          attstorage;   /* TOAST storage strategy */
    char          attcompression; /* compression method */
    bool          attnotnull;   /* NOT NULL constraint */
    bool          atthasdef;    /* has DEFAULT */
    bool          atthasmissing; /* has "missing value" set on ADD COLUMN */
    char          attidentity;  /* GENERATED AS IDENTITY column type */
    char          attgenerated; /* GENERATED column type */
    bool          attisdropped; /* column was dropped (still in tuple) */
    bool          attislocal;
    int32         attinhcount;  /* inherits-count */
    Oid           attcollation; /* collation OID */
} FormData_pg_attribute;
```

About 20 fields total. Each one informs some processing
step.

## The pg_type-mirror fields

[from-comment `pg_attribute.h:46-100`]

> atttypid is the OID of the instance in Catalog Class
> pg_type that defines the data type of this attribute...
>
> attlen is a copy of the typlen field from pg_type...
> attbyval is a copy of the typbyval...

The fields `attlen`, `attbyval`, `attalign` are **denormalized
copies** of `pg_type` columns. Why?

> We rely on attlen, attbyval, and attalign to still tell us
> how large the values in the column actually are.

If a column references a pg_type entry that's later
modified or removed, the column's own copy of the layout
fields preserves correctness. This is critical: even if
pg_type entry is GONE, code can still read the bytes.

This split also avoids a per-tuple catalog lookup —
significant savings on hot scan paths.

## attstorage — TOAST strategy

[from `knowledge/idioms/toast-storage-strategies.md`]

```c
char attstorage;
```

- `'p'` PLAIN — never TOASTed.
- `'e'` EXTERNAL — TOASTed but not compressed.
- `'x'` EXTENDED — TOASTed and compressed.
- `'m'` MAIN — compressed in main; only TOASTed if necessary.

## attcompression — algorithm per column

```c
char attcompression;
```

- `\0` (zero) — use the global `default_toast_compression`.
- `'p'` — pglz.
- `'l'` — LZ4.

Per-column override of compression method. Useful when
some columns benefit from LZ4 but the default is pglz.

## attnum — the numbering

- **`attnum > 0`** — user attributes (1, 2, 3, ...).
- **`attnum < 0`** — system attributes (`ctid` = -1,
  `xmin` = -3, `xmax` = -4, `cmin` = -5, `cmax` = -6,
  `tableoid` = -7).
- **`attnum = 0`** — invalid.

Code that walks attributes typically uses positive numbers
only; system attribute access goes through dedicated
`SysCacheGetAttr` patterns.

## attisdropped — the "dropped column" mark

[verified-by-code `pg_attribute.h:140`]

```c
bool attisdropped;
```

When a column is dropped, the pg_attribute row stays —
because the on-disk tuples may still contain bytes for it.
The dropped flag tells tuple deformation to skip the
column (treat as NULL).

A later VACUUM FULL can rewrite tuples to omit the dropped
column's bytes; the row remains for historical context.

## atthasmissing — for "ADD COLUMN with default"

`ALTER TABLE t ADD COLUMN c text DEFAULT 'foo';`

Without `atthasmissing`, this would rewrite every row
to include the new column. With it: the catalog records
that `c` has a "missing value" of 'foo'; rows written
before the ALTER are returned as 'foo' for column c
without rewriting the heap.

A subsequent UPDATE writes the actual value; subsequent
inserts include it. The missing-value optimization is the
"ADD COLUMN doesn't rewrite the table" feature.

## attcacheoff — the offset cache

```c
int32 attcacheoff;
```

After the first deformation that hits this attribute,
`attcacheoff` is set to the offset within the tuple. Used
on subsequent rows to skip the per-tuple offset
computation.

Reset to `-1` (invalid) when a previous attribute is
variable-length / has nulls / different alignment — the
offset isn't stable.

## attgenerated + attidentity — modern columns

```c
char attgenerated;   /* '' or 's' (stored) or 'v' (virtual) */
char attidentity;    /* '' or 'a' (always) or 'd' (default) */
```

- **Generated**: `GENERATED ALWAYS AS (...)` columns
  computed from other columns at insert/update.
- **Identity**: `GENERATED ALWAYS / DEFAULT AS IDENTITY`
  columns backed by a sequence.

PG 12+. Earlier code uses serial/sequences only.

## The Form_pg_attribute vs CompactAttribute

[from `tupledesc.md` companion]

`Form_pg_attribute` is the wide form (~50 bytes per
attribute). `CompactAttribute` is the slim hot-path form
(~16 bytes) with just the offset, length, alignment, byval
flag, and isnull flag.

`TupleDesc` carries the compact form in `compact_attrs[]`;
the full form lives after the compact array in the same
allocation. Hot paths use compact; less-hot paths use
full.

## Common review-time concerns

- **Adding a new attribute field** is invasive — every
  TupleDesc-using code path needs update.
- **`attisdropped` must be honored** by every deformation
  path; ignoring it = wrong data.
- **`attlen` matches pg_type at column-create time**;
  changes to pg_type later don't auto-propagate.
- **`attcacheoff` is per-TupleDesc**, not per-tuple. Reset
  carefully.
- **`attcompression` defaults to global GUC** when zero;
  the typmod path checks both.

## Invariants

- **[INV-1]** `attlen`, `attbyval`, `attalign` are
  denormalized from pg_type; preserved even if pg_type
  changes.
- **[INV-2]** `attisdropped` rows persist; deformation
  treats as NULL.
- **[INV-3]** `attnum < 0` is system attribute; > 0 user;
  0 invalid.
- **[INV-4]** `attstorage` controls TOAST behavior;
  `attcompression` overrides algorithm.
- **[INV-5]** `atthasmissing` enables ADD COLUMN without
  table rewrite.

## Useful greps

- The full struct definition:
  `grep -B5 -A50 'FormData_pg_attribute' source/src/include/catalog/pg_attribute.h | head -60`
- All field accessors:
  `grep -n 'attisdropped\|attbyval\|attlen' source/src/backend | head -20`
- The compact form generation:
  `grep -n 'populate_compact_attribute' source/src/backend/access/common/tupdesc.c`


## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/include/catalog/pg_attribute.h`](../files/src/include/catalog/pg_attribute.h.md) | 30 | the FormData_pg_attribute struct |
| [`src/include/catalog/pg_attribute.h`](../files/src/include/catalog/pg_attribute.h.md) | — | full struct + comments |

<!-- /callsites:auto -->

## Cross-references

- `knowledge/data-structures/tupledesc.md` — TupleDesc
  carries arrays of these.
- `knowledge/data-structures/heap-tuple-layout.md` —
  tuple deformation uses attlen + attbyval + attalign.
- `knowledge/idioms/toast-storage-strategies.md` —
  attstorage drives TOAST behavior.
- `.claude/skills/catalog-conventions/SKILL.md` — DAT
  file conventions for catalog rows.
- `source/src/include/catalog/pg_attribute.h` — full
  struct + comments.
