# `src/backend/utils/sort/tuplesortvariants.c`

- **File:** `source/src/backend/utils/sort/tuplesortvariants.c` (2089 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

The per-variant glue layer over the generic engine in `tuplesort.c`. For
each kind of object you can sort (`HeapTuple/MinimalTuple`, full
HeapTuple with all visibility info for CLUSTER, IndexTuple for B-tree,
hash-coded IndexTuple, GiST IndexTuple, BrinTuple, GinTuple, bare
Datum), this file supplies the seven `TuplesortPublic` callback
functions — `removeabbrev`, `comparetup`, `comparetup_tiebreak`,
`writetup`, `readtup`, `freestate` — plus a `tuplesort_begin_<variant>`
constructor and `tuplesort_put<variant>` / `tuplesort_get<variant>`
accessors. (`tuplesortvariants.c:1-9` [from-comment])

> "Support for other kinds of sortable objects could be easily added here,
> another module, or even an extension." (`:7-9` [from-comment])

## The eight variants and their constructors

| Variant | `tuplesort_begin_*` | tuple type stored | sort-key source |
|---|---|---|---|
| heap | `tuplesort_begin_heap` (`:180`) | `MinimalTuple` | `attNums[]` + `sortOperators[]` |
| cluster | `tuplesort_begin_cluster` (`:253`) | full `HeapTuple` | b-tree index reference |
| index_btree | `tuplesort_begin_index_btree` (`:359`) | `IndexTuple` | b-tree index |
| index_hash | `tuplesort_begin_index_hash` (`:441`) | `IndexTuple` (one key — the hash code) | `high_mask`/`low_mask`/`max_buckets` |
| index_gist | `tuplesort_begin_index_gist` (`:492`) | `IndexTuple` | GiST sortsupport |
| index_brin | `tuplesort_begin_index_brin` (`:555`) | `BrinSortTuple` (BrinTuple + length prefix) | block number |
| index_gin | `tuplesort_begin_index_gin` (`:582`) | `GinTuple` | per-attribute GIN compare proc |
| datum | `tuplesort_begin_datum` (`:668`) | datum or NULL if pass-by-value | single `sortOperator` |

Each constructor: calls `tuplesort_begin_common`, switches to
`maincontext`, sets `base->{removeabbrev,comparetup,comparetup_tiebreak,
writetup,readtup,haveDatum1,arg,nKeys,sortKeys}`, then builds a
`SortSupportData[]` by calling `PrepareSortSupportFromOrderingOp` /
`PrepareSortSupportFromIndexRel` / `…GistIndexRel` /
`PrepareSortSupportComparisonShim`. (`:211-217, 287-292, 394-399, 472-478,
656-662, 698-704` [verified-by-code])

## Per-variant private data (the `arg` field)

- **heap**: `arg = TupleDesc` directly (no wrapper struct, `:217`).
- **cluster**: `TuplesortClusterArg { TupleDesc, IndexInfo*, EState* }`
  (`:112-118`). `freestate_cluster` releases the EState when present.
- **index_btree**: `TuplesortIndexBTreeArg { TuplesortIndexArg index;
  bool enforceUnique; bool uniqueNullsNotDistinct; }` (`:133-139`) —
  the unique-check fields drive `ereport(ERROR, …)` in
  `comparetup_index_btree_tiebreak` on duplicate.
- **index_hash**: `TuplesortIndexHashArg { TuplesortIndexArg index;
  uint32 high_mask, low_mask, max_buckets; }` (`:144-151`).
- **datum**: `TuplesortDatumArg { Oid datumType; int datumTypeLen; }`
  (`:157-163`). `base->tuples = !typbyval` (`:711`) — for pass-by-value
  Datums, `SortTuple.tuple == NULL` and the value lives entirely in
  `datum1`.

## The abbreviated-key wiring (per variant)

Each constructor sets `sortKey->abbreviate = (i == 0 && base->haveDatum1)`
(`:234, 343, 425`) — only the first column, and only when datum1 is
maintained. `PrepareSortSupport*` then asks the opclass for an
abbreviation provider; if accepted, the opclass fills in
`abbrev_converter`, `abbrev_full_comparator`, and `abbrev_abort`.

**`onlyKey` optimization** (single-key sort fast path):
`base->onlyKey = base->sortKeys` is set only when `nkeys == 1 &&
!sortKeys->abbrev_converter` (`:245-246, 738-739`) — abbreviation
disqualifies because tiebreak comparisons might still be needed.

## Special exceptions

- **`index_gin`** sets `base->haveDatum1 = false` (`:660`) — multi-column
  GIN indexes expand each row into per-attribute entries written into the
  tuplesort, so there's no single "first column" Datum to cache. As a
  consequence: no radix sort, no `onlyKey` fast path, no abbreviation.
  (`:605-609` [from-comment])
- **`index_brin`** uses a `BrinSortTuple { Size tuplen; BrinTuple tuple; }`
  wrapper (`:170-174`) — "Computing BrinTuple size with only the tuple is
  difficult, so we want to track the length referenced by the SortTuple"
  (`:166-169` [from-comment]).
- **`datum` + pass-by-value**: `tuple` is NULL, `datum1` is authoritative.
  Abbreviation is disabled for pass-by-value because "a datum sort only
  stores a single copy of the datum" so we can't fall back to the
  original on abbreviation tiebreak (`:720-728` [from-comment]).
- **`cluster` haveDatum1**: gated on `arg->indexInfo->ii_IndexAttrNumbers[0]
  != 0` (`:301-304`) — for an expression-based leading index column we
  don't cache datum1.

## Put / Get accessors

`tuplesort_put*` (`:752-985`):
- All switch to `base->tuplecontext` before copying the tuple so the
  copy lives in the reset-on-dump tuple memory.
- Each computes `tuplen` differently depending on `TupleSortUseBumpTupleCxt
  (sortopt)`: with bump it's `MAXALIGN(t_len)` because bump contexts
  don't support `GetMemoryChunkSpace`; with aset it's
  `GetMemoryChunkSpace(tuple)` (`:773-777`, `:822-826`, etc.). This is
  the "bump vs aset" payoff for memory accounting.
- Then calls back into `tuplesort_puttuple_common(state, &stup, useAbbrev,
  tuplen)`.

`tuplesort_get*` (`:1004-1192`):
- `tuplesort_gettupleslot` (`:1004`) — for `begin_heap`. Decodes the
  MinimalTuple pointer in `stup.tuple` into a TupleTableSlot.
- `tuplesort_getheaptuple` (`:1042`), `tuplesort_getindextuple` (`:1063`),
  `tuplesort_getbrintuple` (`:1080`), `tuplesort_getgintuple` (`:1106`),
  `tuplesort_getdatum` (`:1153`) — each calls
  `tuplesort_gettuple_common` and unpacks `stup.tuple`.
- `tuplesort_getdatum` is the unusual one: pass-by-ref Datums are
  returned **palloc'd in the caller's context** (independent of
  tuplesort lifetime), optionally a copy when `copy == true`. (`:1133-1151`
  [from-comment])

## Comparison anatomy (the canonical example: `comparetup_heap`)

`comparetup_heap` (`:1220-1237`):
1. `ApplySortComparator(a->datum1, a->isnull1, b->datum1, b->isnull1, sortKey)`
   — single-instruction inlined leading-key compare using the cached
   `datum1` (or abbreviated key).
2. If equal → `comparetup_heap_tiebreak`.

`comparetup_heap_tiebreak` (`:1239-…`):
1. Decode `MinimalTuple → HeapTupleData` (note the `MINIMAL_TUPLE_OFFSET`
   trick: a MinimalTuple is a HeapTupleHeader minus the front fields, so
   the pointer must be biased back by `MINIMAL_TUPLE_OFFSET` to get a
   valid `HeapTupleHeader *`, `:1255-1258`).
2. If `abbrev_converter` is set, call `ApplySortAbbrevFullComparator` on
   the leading column using the **original** value pulled from the
   tuple (`heap_getattr`). This is required because abbreviation
   collapsed full values into a uint64 proxy — equal proxies can be
   distinct values.
3. Loop over `sortKey[1..nKeys]`, `heap_getattr` each, compare.

The same pattern repeats with variant-specific tuple decoding for cluster,
index_btree, index_hash, index_brin, index_gin, datum.

## Write / Read on-tape representation

Each `writetup_*` / `readtup_*` pair owns the on-tape format. Common
structure:
1. `writetup`: write `unsigned int tuplen` (the length word the engine
   demands), write the raw tuple bytes, optionally write the trailing
   length word if `TUPLESORT_RANDOMACCESS`, call `FREEMEM(state,
   GetMemoryChunkSpace(stup->tuple))` and `pfree(stup->tuple)`.
2. `readtup`: `tuplesort_readtup_alloc(state, len)` to get a slab or
   palloc'd buffer, `LogicalTapeReadExact` into it, fix up internal
   pointers, then advance past the trailing length word if present.

The Datum variant is the simplest: `writetup_datum` writes either just
the Datum (pass-by-value) or the palloc'd buffer pointed to by `tuple`
(pass-by-ref). HeapTuple-based variants must reconstitute
`HeapTupleHeader` pointers via the `MINIMAL_TUPLE_OFFSET` bias.

## Functions of note

1. **`tuplesort_begin_heap` (`:180-251`)** — the canonical constructor;
   most-used variant.
2. **`tuplesort_begin_datum` (`:668-744`)** — the pass-by-value
   special case; sets `base->tuples = !typbyval`.
3. **`removeabbrev_heap` (`:1199-1218`)** — re-extracts the leading
   column from the tuple to undo the abbreviated representation across
   all heaped SortTuples. Called from `consider_abort_common` when
   abbreviation aborts.
4. **`tuplesort_puttupleslot` (`:752-…`)** — `ExecCopySlotMinimalTuple`
   into `tuplecontext`, build `SortTuple { tuple, datum1, isnull1 }`,
   forward to `tuplesort_puttuple_common`.

## Cross-references

- `tuplesort.c` — engine, the `TuplesortPublic` consumer.
- `tuplesort.h` — declares all `tuplesort_begin_*` and `tuplesort_put*` /
  `tuplesort_get*` signatures.
- `sortsupport.h` / `sortsupport.c` — the `SortSupportData` machinery and
  `PrepareSortSupportFromOrderingOp` / `…IndexRel` / `…GistIndexRel`.
- `access/nbtree.h` (`_bt_mkscankey`), `access/brin_tuple.h`,
  `access/gin_tuple.h`, `access/hash.h`.

## Open questions

- The exact ordering rules used by `comparetup_index_hash` (it must
  cluster IndexTuples by the hash bucket they'll land in, not by the
  lexicographic hash code) — only skimmed.
- `tuplesort_begin_index_gist` GiST-specific sortsupport flow (which
  uses `PrepareSortSupportFromGistIndexRel`) — not verified.
- `comparetup_index_btree_tiebreak`'s exact `ERRCODE_UNIQUE_VIOLATION`
  path when `enforceUnique` is set — believed present but not chased.

## Confidence tag tally

- `[verified-by-code]` × ~12
- `[from-comment]` × ~6
- `[unverified]` × 3

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
