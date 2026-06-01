# `src/backend/utils/sort/sortsupport.c`

- **File:** `source/src/backend/utils/sort/sortsupport.c` (207 lines)
- **Header:** `source/src/include/utils/sortsupport.h`
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Setup helpers for the **SortSupport** API — PostgreSQL's
reduced-overhead alternative to the traditional FmgrInfo-based `cmp(x, y)`
comparator. An opclass that exposes a `BTSORTSUPPORT_PROC` (`pg_amproc`
support function entry) gets to provide a direct C function pointer
(`int (*comparator)(Datum, Datum, SortSupport)`), bypassing fmgr's
per-call overhead and optionally enabling **abbreviated keys**, **radix
sort** (via `ssup_datum_*_cmp` recognition in `tuplesort.c`), and other
acceleration mechanisms. (`sortsupport.h:1-43` [from-comment])

## What this file does

Three public setup entry points and one helper, all building a
`SortSupportData` for a sort key:

1. **`PrepareSortSupportFromOrderingOp(orderingOp, ssup)`** (`:133-150`)
   — caller has an ordering operator OID (e.g. `< (int4,int4)`); we
   `get_ordering_op_properties` to find the opfamily, opcintype, and
   compare type (LT vs GT, → `ssup_reverse`), then call
   `FinishSortSupportFunction`.

2. **`PrepareSortSupportFromIndexRel(indexRel, reverse, ssup)`**
   (`:160-174`) — caller has an opened btree index Relation and an
   attribute number already stamped into `ssup_attno`. We pull
   `rd_opfamily[]` and `rd_opcintype[]` from the relcache entry, set
   `ssup_reverse = reverse`, then call `FinishSortSupportFunction`.
   Asserts `indexRel->rd_indam->amcanorder`.

3. **`PrepareSortSupportFromGistIndexRel(indexRel, ssup)`** (`:184-207`)
   — GiST-specific path: looks up `GIST_SORTSUPPORT_PROC` (NOT
   `BTSORTSUPPORT_PROC`), errors if missing, and calls it directly.
   "Simpler than for B-tree indexes because we don't support the
   old-style btree comparators." (`:198-199` [from-comment]).
   `ssup_reverse` is hard-coded to `false` because GiST sortbuild only
   uses ascending sort.

4. **`PrepareSortSupportComparisonShim(cmpFunc, ssup)`** (`:67-86`) — when
   no sortsupport function exists or it declined, this builds an
   FmgrInfo-backed shim that wraps the old-style `BTORDER_PROC` (the
   per-pair cmp function) into the SortSupport-shaped
   `(Datum, Datum, SortSupport) → int` signature. The shim allocates a
   `SortShimExtra` (`:27-31` — `FmgrInfo` + reusable
   `FunctionCallInfoBaseData`) in `ssup->ssup_cxt` so allocation cost is
   one-time per sort, not per comparison.

## The selection logic — `FinishSortSupportFunction` (`:93-124`)

This is the load-bearing piece:

1. Look for a `BTSORTSUPPORT_PROC` in the opfamily for
   `(opcintype, opcintype)` via `get_opfamily_proc`.
2. If found, call it via `OidFunctionCall1(…, PointerGetDatum(ssup))`.
   The opclass's BTSORTSUPPORT function fills in `comparator` (and
   optionally `abbrev_*` fields). **The opclass may decline** —
   e.g. based on the selected `ssup_collation`, it may return without
   setting `comparator`. (`:103-107` [from-comment])
3. If `comparator` is still NULL afterward, fall back: look up the
   old-style `BTORDER_PROC` and shim it via
   `PrepareSortSupportComparisonShim`.
4. If the BTORDER_PROC is also missing, that's an internal-error
   condition (`elog(ERROR, "missing support function …")` at `:118`).

## The shim — `comparison_shim` (`:42-61`)

> "Essentially an inlined version of `FunctionCall2Coll()`, except we
> assume that the `FunctionCallInfoBaseData` was already mostly set up by
> `PrepareSortSupportComparisonShim`." (`:36-40` [from-comment])

Per call: stamps `args[0].value = x`, `args[1].value = y`, resets
`isnull`, dispatches via `FunctionCallInvoke`, and ereports if the cmp
proc returns NULL. The reuse of one `FunctionCallInfoBaseData` across
comparisons is the entire shim optimization — argument setup goes from
O(N²) over a sort down to two scalar writes per call.

## SortSupportData struct (in `sortsupport.h:60-192`)

The contract that opclass authors implement against:
- **Caller-set inputs**: `ssup_cxt`, `ssup_collation`, `ssup_reverse`,
  `ssup_nulls_first`, `ssup_attno`, and `abbreviate` (the boolean hint
  that abbreviation might pay off — typically true only for the leading
  sort column).
- **Opclass-set outputs**: `comparator` (required), and the abbreviated-
  key quartet `abbrev_converter`, `abbrev_abort`, `abbrev_full_comparator`
  (all-or-nothing — if abbreviation is offered, all four must be set).
- **Opclass scratch space**: `ssup_extra` (typed `void *`), allocated by
  the opclass in `ssup_cxt`.

The `comparator` signature is the same as the legacy btree comparator
(`return <0 / 0 / >0`), but `x` and `y` are guaranteed non-null —
NULL handling is done by `ApplySortComparator` at the call site
(`sortsupport.h:199-…`), not the opclass.

## Abbreviation contract (the subtle parts)

From `sortsupport.h:109-192` [from-comment]:
- The `comparator` slot can hold **either** the authoritative or the
  abbreviated comparator. When abbreviation is in play, `comparator`
  is the cheap abbreviation comparator and `abbrev_full_comparator` is
  the authoritative one. **Returning 0 from the abbreviated comparator
  does NOT mean equal** — it means "I couldn't tell", so the caller
  must run `abbrev_full_comparator` on a tiebreak.
- Core code (`tuplesort.c` / `tuplesortvariants.c`) decides whether to
  enable abbreviation by **testing `abbrev_converter != NULL`** after
  setup. It may swap `comparator <- abbrev_full_comparator` to disable
  abbreviation later (e.g. when `consider_abort_common` decides
  abbreviation isn't paying off, or when starting a multi-pass merge).
- For platform/collation-specific reasons, an opclass may decline to
  set up abbreviation by *not* setting `abbrev_converter` — that's the
  signal to core code.

## Cross-references

- `tuplesort.c` — primary consumer; calls these `Prepare*` from
  `tuplesortvariants.c` constructors.
- `ApplySortComparator` / `ApplySortAbbrevFullComparator` inline helpers
  in `sortsupport.h:199-…` — handle nulls + reverse, then dispatch to
  `comparator`. These are what `comparetup_*` functions actually call.
- Type-specific BTSORTSUPPORT implementations live with their
  datatypes:
  - `numeric_sortsupport` — `source/src/backend/utils/adt/numeric.c`.
  - `bttextsortsupport` / `varstrfastcmp_*` — `source/src/backend/utils/adt/varlena.c`
    (with the abbreviated-key implementation using poor-man's
    normalized keys, signed-byte cmp, etc.).
  - `btint{2,4,8}sortsupport`, `btoidsortsupport` — `int.c`, `oid.c`,
    `int8.c`.
  - `date_sortsupport`, `timestamp_sortsupport` — `date.c`, `timestamp.c`.
- `pg_amproc` — the support-function entries: `BTSORTSUPPORT_PROC = 2`
  for btree (in `access/nbtree.h`), `GIST_SORTSUPPORT_PROC = 11` for GiST.

## Open questions

- Cross-type BTSORTSUPPORT: comment at `:39-42` notes "it is possible to
  associate a BTSORTSUPPORT function with a cross-type comparison" —
  whether any in-tree opclass actually does this for sorting is
  [unverified].
- Whether GiST's `PrepareSortSupportFromGistIndexRel` ever falls back to
  a comparison shim (looks like no — it errors out if no
  `GIST_SORTSUPPORT_PROC`, `:203-205`).

## Confidence tag tally

- `[verified-by-code]` × ~10
- `[from-comment]` × ~6
- `[unverified]` × 2
