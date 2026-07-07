# TOAST chunk write — toast_save_datum and the 2000-byte rule

When a tuple grows past `TOAST_TUPLE_THRESHOLD` (~2 KB on default
8 KB pages), the toaster compresses the largest EXTENDED columns
in place; if the tuple is still too big, it walks down to EXTERNAL
storage. `toast_save_datum` is the worker that performs the
out-of-line write: it splits the datum into `TOAST_MAX_CHUNK_SIZE`
byte chunks, inserts one heap tuple per chunk into the
relation's TOAST table (keyed by `(va_valueid, chunk_seq)`),
indexes each chunk, and returns a `varatt_external` pointer
encoding the value's OID and total size. Changing
`TOAST_MAX_CHUNK_SIZE` requires initdb because every existing
TOAST table was sized around the old constant.

Anchors:
- `source/src/backend/access/common/toast_internals.c:119` —
  toast_save_datum [verified-by-code]
- `source/src/backend/access/common/toast_internals.c:283-349` —
  chunk-write loop [verified-by-code]
- `source/src/include/access/heaptoast.h:80-89` —
  EXTERN_TUPLES_PER_PAGE + TOAST_MAX_CHUNK_SIZE derivation
  [verified-by-code]
- `source/src/include/access/heaptoast.h:46-50` —
  TOAST_TUPLE_THRESHOLD / TARGET [verified-by-code]
- `source/src/backend/access/common/toast_internals.c:376` —
  toast_delete_datum [verified-by-code]
- `knowledge/data-structures/varatt-varlena.md` — companion
- `knowledge/idioms/detoast-stream-consumption.md` — companion
- `.claude/skills/wal-and-xlog/SKILL.md` — companion

## Why 2000-ish bytes

[verified-by-code `heaptoast.h:38-50`]

> Currently we choose both values to match the largest tuple
> size for which TOAST_TUPLES_PER_PAGE tuples can fit on a heap
> page.

`TOAST_TUPLES_PER_PAGE = 4` means the threshold is roughly
`8192 / 4 ≈ 2048` bytes minus page/tuple overhead. A tuple bigger
than that triggers the toaster, which has four levers in order:

1. **Compress EXTENDED columns in place** (PGLZ / LZ4).
2. **Move biggest EXTENDED column out-of-line** (this calls
   `toast_save_datum`).
3. **Compress + move EXTENDED columns until under the target.**
4. **As last resort, move MAIN-storage columns.** Uses
   `TOAST_TUPLE_TARGET_MAIN` (= largest-tuple-on-page) instead of
   the smaller TARGET.

Per-column `pg_attribute.attstorage` selects which columns the
toaster may touch (`PLAIN` = never, `EXTERNAL` = no compression
but may be out-of-line, `EXTENDED` = both, `MAIN` = only as
last resort).

## EXTERN_TUPLES_PER_PAGE and TOAST_MAX_CHUNK_SIZE

[verified-by-code `heaptoast.h:78-89`]

```c
#define EXTERN_TUPLES_PER_PAGE  4    /* tweak only this */
#define EXTERN_TUPLE_MAX_SIZE   MaximumBytesPerTuple(EXTERN_TUPLES_PER_PAGE)
#define TOAST_MAX_CHUNK_SIZE    \
    (EXTERN_TUPLE_MAX_SIZE -                            \
     MAXALIGN(SizeofHeapTupleHeader) -                  \
     sizeof(Oid) -                                      \
     sizeof(int32) -                                    \
     VARHDRSZ)
```

Each TOAST table tuple holds `(chunk_id Oid, chunk_seq int32,
chunk_data bytea)` — derivation subtracts header / Oid / seq /
varlena-header from the per-tuple budget. The result is about
1996 bytes today.

`NB: Changing TOAST_MAX_CHUNK_SIZE requires an initdb.`
[verified-by-code `heaptoast.h:78`]

## toast_save_datum entry

[verified-by-code `toast_internals.c:118-200`]

```c
Datum
toast_save_datum(Relation rel, Datum value,
                 varlena *oldexternal, uint32 options)
```

Three input shapes, three filled-out `varatt_external` patterns
[verified-by-code lines 161-187]:

| Input | Path |
|---|---|
| `VARATT_IS_SHORT(dval)` | Treat data as if it had VARHDRSZ; va_rawsize = data + VARHDRSZ; va_extinfo = data size |
| `VARATT_IS_COMPRESSED(dval)` | Preserve compression method; va_rawsize = decompressed size + VARHDRSZ; va_extinfo encodes external size + compression |
| 4-byte uncompressed | va_rawsize = VARSIZE; va_extinfo = data size |

The toaster is assert-protected against feeding it already-external
datums (`Assert(!VARATT_IS_EXTERNAL(dval))`) — the caller is
responsible for inlining first if needed.

## CLUSTER / VACUUM FULL preservation

[verified-by-code `toast_internals.c:189-200, 214-278`]

During table rewrite (`CLUSTER`, `VACUUM FULL`), the new heap
relation has its `rd_toastoid` set to the destination TOAST
table's OID. In that mode, `toast_save_datum`:
- Reuses the **TOAST value OID** from the source pointer
  (`oldexternal`) when possible.
- Skips re-writing chunks if a value with that OID already exists
  in the new TOAST table (detected by `toastrel_valueid_exists`).
- Picks a non-conflicting OID otherwise.

This avoids duplicating TOAST data when the same OID survives the
rewrite (and explicitly handles the corner case where two heap
versions reference the same TOAST value).

## The chunk-write loop

[verified-by-code `toast_internals.c:283-349`]

```c
while (data_todo > 0)
{
    union {
        alignas(int32) varlena hdr;
        char data[TOAST_MAX_CHUNK_SIZE + VARHDRSZ];
    } chunk_data;
    int32 chunk_size;

    CHECK_FOR_INTERRUPTS();

    chunk_size = Min(TOAST_MAX_CHUNK_SIZE, data_todo);

    /* Build tuple: (valueid, chunk_seq, chunk_data) */
    t_values[0] = ObjectIdGetDatum(toast_pointer.va_valueid);
    t_values[1] = Int32GetDatum(chunk_seq++);
    SET_VARSIZE(&chunk_data, chunk_size + VARHDRSZ);
    memcpy(VARDATA(&chunk_data), data_p, chunk_size);
    t_values[2] = PointerGetDatum(&chunk_data);

    toasttup = heap_form_tuple(toasttupDesc, t_values, t_isnull);
    heap_insert(toastrel, toasttup, mycid, options, NULL);

    for (int i = 0; i < num_indexes; i++) {
        if (toastidxs[i]->rd_index->indisready)
            index_insert(toastidxs[i], ...);
    }

    heap_freetuple(toasttup);
    data_todo -= chunk_size;
    data_p += chunk_size;
}
```

Notable:
- **CHECK_FOR_INTERRUPTS** in the loop — TOASTing a 1 GB datum
  is interruptable.
- **`indisready` only** — invalid / not-yet-ready indexes (mid-
  REINDEX CONCURRENTLY) are skipped.
- **No FormIndexDatum** — uses the knowledge that TOAST indexes
  have the same column layout as the table.

## The returned TOAST pointer

[verified-by-code `toast_internals.c:362-366`]

```c
result = (varlena *) palloc(TOAST_POINTER_SIZE);
SET_VARTAG_EXTERNAL(result, VARTAG_ONDISK);
memcpy(VARDATA_EXTERNAL(result), &toast_pointer, sizeof(toast_pointer));
return PointerGetDatum(result);
```

The caller (heap_toast_insert_or_update) substitutes this pointer
into the new heap tuple in place of the original column value.

## toast_delete_datum — the symmetric path

[verified-by-code `toast_internals.c:376-470`]

When a heap tuple is updated to a non-EXTERNAL value or deleted,
its old TOAST pointer's underlying chunks must be removed. The
caller iterates EXTERNAL columns and calls `toast_delete_datum`
on each, which:
1. Memcpy's the `varatt_external` out of the heap tuple.
2. Opens the TOAST table named in `va_toastrelid`.
3. Scans for `chunk_id = va_valueid` via the TOAST table's PK
   index.
4. Calls `heap_delete` on each chunk tuple.

`is_speculative = true` is passed during INSERT ... ON CONFLICT
rollback paths to use speculative deletes.

## Locking discipline

[verified-by-code `toast_internals.c:142-149, 354-358`]

- `RowExclusiveLock` on the TOAST table and indexes during
  write — same lock as the main relation's writer.
- `NoLock` on close — the lock is held until xact end. This is
  important: a concurrent `REINDEX` on the TOAST table will wait
  for the writer's xact to commit.

## Common review-time concerns

- **Per-column attstorage drives toaster decisions** — changing
  it requires ALTER TABLE.
- **Value OID is unique within a TOAST table** — not globally.
  Two different main tables can have value OID 12345.
- **Indexes are TOAST-table-local** — every TOAST table has a
  unique index on (chunk_id, chunk_seq).
- **CLUSTER reuses value OIDs** — implies you can't tell apart
  before/after CLUSTER by TOAST pointer comparison.
- **Compression decision is at write-time** — once external,
  changing compression method requires re-writing (UPDATE forces
  a rewrite).
- **Don't bypass toast_save_datum** — the chunked layout +
  unique-index discipline is on-disk-committed.

## Invariants

- **[INV-1]** TOAST table layout: `(chunk_id Oid, chunk_seq
  int32, chunk_data bytea)` with PK on (chunk_id, chunk_seq).
- **[INV-2]** Each chunk holds at most `TOAST_MAX_CHUNK_SIZE`
  data bytes; sized for 4 max-size tuples per page.
- **[INV-3]** `varatt_external.va_valueid` is unique within the
  containing TOAST table; not globally.
- **[INV-4]** Compression method is fixed at write time; encoded
  in top 2 bits of `va_extinfo`.
- **[INV-5]** CLUSTER preserves value OIDs when possible to skip
  re-writing; corner-case re-use is detected via
  `toastrel_valueid_exists`.

## Useful greps

- The writer:
  `grep -n 'toast_save_datum\|toast_delete_datum' source/src/backend/access/common/toast_internals.c | head -10`
- Size constants:
  `grep -n 'TOAST_TUPLE_THRESHOLD\|TOAST_MAX_CHUNK_SIZE\|EXTERN_TUPLES_PER_PAGE' source/src/include/access/heaptoast.h | head -10`
- The driver (compress + externalize):
  `grep -n '^heap_toast_insert_or_update\|toast_tuple_externalize' source/src/backend/access/heap/heaptoast.c source/src/backend/access/table/toast_helper.c | head -10`
- attstorage classes:
  `grep -n 'TYPSTORAGE_PLAIN\|TYPSTORAGE_EXTERNAL\|TYPSTORAGE_EXTENDED\|TYPSTORAGE_MAIN' source/src/include/catalog/pg_type.h | head -10`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/common/toast_internals.c`](../files/src/backend/access/common/toast_internals.c.md) | 119 | toast_save_datum |
| [`src/backend/access/common/toast_internals.c`](../files/src/backend/access/common/toast_internals.c.md) | 283 | chunk-write loop |
| [`src/backend/access/common/toast_internals.c`](../files/src/backend/access/common/toast_internals.c.md) | 376 | toast_delete_datum |
| [`src/backend/access/common/toast_internals.c`](../files/src/backend/access/common/toast_internals.c.md) | — | full writer |
| [`src/backend/access/table/toast_helper.c`](../files/src/backend/access/table/toast_helper.c.md) | — | compress / inline / externalize driver loop |
| [`src/include/access/heaptoast.h`](../files/src/include/access/heaptoast.md) | 46 | TOAST_TUPLE_THRESHOLD / TARGET |
| [`src/include/access/heaptoast.h`](../files/src/include/access/heaptoast.md) | 80 | EXTERN_TUPLES_PER_PAGE + TOAST_MAX_CHUNK_SIZE derivation |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/data-structures/varatt-varlena.md` — the
  `varatt_external` struct + bit layout.
- `knowledge/idioms/detoast-stream-consumption.md` — the read
  side.
- `knowledge/idioms/heap-insert-update.md` —
  `heap_toast_insert_or_update` caller.
- `knowledge/idioms/cluster-table-rewrite.md` — why
  rd_toastoid preservation matters.
- `knowledge/subsystems/access-common.md` — TOAST module
  overview.
- `.claude/skills/wal-and-xlog/SKILL.md` — each chunk
  heap_insert generates WAL.
- `source/src/backend/access/common/toast_internals.c` —
  full writer.
- `source/src/backend/access/table/toast_helper.c` — the
  compress / inline / externalize driver loop.
