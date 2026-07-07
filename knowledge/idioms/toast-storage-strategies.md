# TOAST storage strategies — per-column compression + out-of-line

Every varlena column in PG has a `STORAGE` attribute
controlling whether it can be compressed in-place and/or moved
out-of-line to a TOAST table. The 4 strategies (PLAIN /
EXTERNAL / EXTENDED / MAIN) reflect the matrix of {compress yes/no}
× {can-be-out-of-line yes/no}. Picking the wrong one wastes
disk and hurts query speed.

Anchors:
- `source/src/include/catalog/pg_attribute.h:105-117` —
  `attstorage` field [verified-by-code]
- `source/src/include/access/heaptoast.h:30-50` —
  TOAST_TUPLE_THRESHOLD definitions [verified-by-code]
- `source/src/backend/access/heap/heaptoast.c` — the toast
  decision engine
- `knowledge/idioms/heap-tuple-decompression-pattern.md` —
  the read-back side

## The 4 strategies

| `attstorage` | Compress in-place? | Move out-of-line? | Use case |
|---|---|---|---|
| `'p'` PLAIN | No | No | Fixed-size types (int, oid, char(N) up to threshold) |
| `'e'` EXTERNAL | No | Yes | Large blobs where compression isn't worth it (compressed images, video) |
| `'x'` EXTENDED | Yes | Yes | Default for varlenas; tries both |
| `'m'` MAIN | Yes | Yes (only if necessary) | Compress preferred; out-of-line only as last resort |

[from-comment `pg_attribute.h:105-117`]

Strategy choice is per-column, set at CREATE TABLE / ALTER
TABLE time. The default for varlena columns is EXTENDED
unless explicitly overridden.

## The TOAST tuple threshold

[verified-by-code `heaptoast.h:48-50`]

```c
#define TOAST_TUPLE_THRESHOLD    MaximumBytesPerTuple(TOAST_TUPLES_PER_PAGE)
#define TOAST_TUPLE_TARGET       TOAST_TUPLE_THRESHOLD
```

`TOAST_TUPLE_THRESHOLD` (~2KB for default 8KB pages) is the
"tuple is too big" boundary. When a tuple exceeds it:

1. The toaster runs.
2. Each varlena column is considered for TOAST treatment
   based on its `attstorage`.
3. Columns are processed in **largest-first** order — try to
   shrink the tuple to below `TOAST_TUPLE_TARGET`.
4. PLAIN columns are skipped.
5. EXTENDED / EXTERNAL columns are moved out-of-line; the
   tuple stores a pointer.
6. EXTENDED / MAIN columns may also be compressed in-place
   before moving.

## The decision tree per column

```
attstorage = 'p' PLAIN:
    leave alone. ERROR if tuple still too big.

attstorage = 'e' EXTERNAL:
    move to TOAST table without compression.

attstorage = 'x' EXTENDED:
    1. compress in-place (if savings ≥ 25%).
    2. if still too big, move to TOAST (still compressed).

attstorage = 'm' MAIN:
    1. compress in-place.
    2. only move to TOAST if tuple is STILL too big after
       compressing all 'x' columns.
```

[abstracted from `heaptoast.c`]

The order matters: 'x' columns are toasted before 'm', so
'm' fields stay inline when possible.

## The compression algorithms

PG supports per-column compression methods via
`COMPRESSION` attribute (PG 14+):

```sql
ALTER TABLE t ALTER COLUMN c SET COMPRESSION lz4;
```

Options: `pglz` (legacy default), `lz4` (PG 14+ default when
built with `--with-lz4`). The compression method is recorded
in 2 bits of the compressed varlena's header — backend can
mix methods within one column on different rows.

## The out-of-line layout

When a column moves to the TOAST table:

1. A row is inserted into `pg_toast.pg_toast_<table_oid>`
   with the value's bytes (possibly compressed).
2. The original column in the main table stores an 18-byte
   pointer: `(valueid, length, rawsize, va_extinfo)`.
3. Reads navigate the pointer + reassemble.

Chunked storage: the TOAST table breaks the value into
~2KB chunks (one per row in the TOAST table). For very-large
values, this can be 100+ rows of pg_toast.

## SET STORAGE — change it after the fact

```sql
ALTER TABLE t ALTER COLUMN c SET STORAGE EXTERNAL;
```

Existing rows are NOT re-toasted. The new strategy applies
only to subsequent UPDATEs / INSERTs of that column.

To force re-TOAST on existing data, `UPDATE t SET c = c;` —
the no-op update re-writes every row with the new storage
strategy.

## When to pick what

- **PLAIN**: fixed-size types (default for `int`, `bigint`, etc.).
  Never explicitly set on a varlena.
- **EXTERNAL**: column holds already-compressed data
  (JPEG/PNG/MP4/Parquet/zstd files). Skipping compression
  saves CPU on each read/write.
- **EXTENDED**: text / jsonb / general varlena. Default. Tries
  both compression and out-of-line.
- **MAIN**: small-ish varlenas that benefit from
  compression but you want kept inline if possible (e.g.,
  CHECK-constraint-only audit columns). Less common.

## Common review-time concerns

- **Don't set STORAGE EXTERNAL on text columns** unless you've
  measured. Compression on text is usually a big win.
- **Don't expect `SET STORAGE` to retroactively toast.**
  Existing rows need an UPDATE.
- **`PG_DETOAST_DATUM_PACKED` is the canonical read pattern.**
  Don't manually unwrap; let the macros handle the strategy.
- **TOAST tables grow with the main table.** Plan disk
  accordingly.

## Invariants

- **[INV-1]** `attstorage` is per-column; 4 strategies.
- **[INV-2]** TOAST_TUPLE_THRESHOLD is the toaster-fires
  boundary.
- **[INV-3]** Largest-first processing tries to shrink tuple
  to TOAST_TUPLE_TARGET.
- **[INV-4]** SET STORAGE applies to future writes only;
  existing rows unchanged.
- **[INV-5]** Compression algorithm is per-row, encoded in
  varlena header bits.

## Useful greps

- The 4 storage codes:
  `grep -n 'TYPSTORAGE_' source/src/include/access/heaptoast.h`
- The toast entry point:
  `grep -n 'heap_toast_insert_or_update' source/src/backend/access/heap/heaptoast.c | head -5`
- attstorage handling:
  `grep -RIn 'attstorage' source/src/backend | head -20`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/heap/heaptoast.c`](../files/src/backend/access/heap/heaptoast.c.md) | — | toast decision engine |
| [`src/include/access/heaptoast.h`](../files/src/include/access/heaptoast.md) | 30 | TOAST_TUPLE_THRESHOLD definitions |
| [`src/include/access/heaptoast.h`](../files/src/include/access/heaptoast.md) | — | thresholds + macros |
| [`src/include/catalog/pg_attribute.h`](../files/src/include/catalog/pg_attribute.h.md) | 105 | attstorage field |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-system-catalog-column`](../scenarios/add-new-system-catalog-column.md)

<!-- /scenarios:auto -->

## Cross-references

- `knowledge/idioms/heap-tuple-decompression-pattern.md` —
  the read-back side; how detoast works.
- `knowledge/data-structures/heap-tuple-layout.md` — the
  varlena formats produced by toasting.
- `knowledge/subsystems/access-heap.md` — heap layout +
  TOAST table organization.
- `.claude/skills/extension-development/SKILL.md` —
  `--with-lz4` build-time gate.
- `knowledge/subsystems/contrib-pgstattuple.md` — bloat
  audit; TOAST tables are part of the storage picture.
- `source/src/include/access/heaptoast.h` — thresholds +
  macros.
- `source/src/backend/access/heap/heaptoast.c` —
  implementation.
