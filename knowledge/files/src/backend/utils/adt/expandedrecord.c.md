# `src/backend/utils/adt/expandedrecord.c`

- **File:** `source/src/backend/utils/adt/expandedrecord.c` (1633 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

The **expanded-object backend for composite values** — named composite
types, domains over named composites, registered RECORD types, and
anonymous RECORD types. Used heavily by PL/pgSQL composite variables
(`r RECORD`, `r foo_type`) and any C code that wants to mutate fields
without re-flattening the whole tuple. (`expandedrecord.c:1-17`
[from-comment])

## Type role

Generic expanded-Datum implementation; consumed by composite-typed
expressions in PL/pgSQL and by parts of the executor. Not directly wired
to a single fmgr type.

## Key functions

- `make_expanded_record_from_typeid(type_id, typmod, parentcontext)`
  (`:69`) — build an empty expanded record (logically a NULL composite,
  not ROW(NULL,...)). `type_id` may be `RECORDOID` if a valid `typmod`
  is supplied. Handles **domains over composite** transparently via
  `lookup_type_cache(TYPECACHE_DOMAIN_BASE_INFO)` and sets
  `ER_FLAG_IS_DOMAIN` (`:90-95`).
- `make_expanded_record_from_tupdesc` — variant that takes an explicit
  TupleDesc instead of pulling one from typcache.
- `make_expanded_record_from_exprecord` — clone constructor.
- `expanded_record_set_tuple` — install a HeapTuple as the current value;
  triggers domain validation for ER_FLAG_IS_DOMAIN records.
- `expanded_record_get_tuple` — get a flattened HeapTuple view.
- `expanded_record_set_field_internal` — set one field by ordinal
  position. Triggers per-field domain check via
  `check_domain_for_new_field` (`:48`).
- `expanded_record_fetch_field` — get one field by ordinal position;
  may need to deconstruct the tuple lazily.
- Methods registered in `ER_methods`: `ER_get_flat_size` (`:34`) and
  `ER_flatten_into` (`:35`).

## Internal state

- `ExpandedRecordHeader` (in the header file) — the live header. Holds:
  the tupdesc + tupdesc_id (for cache invalidation), the optional flat
  tuple representation, an optional deconstructed (Datum[], bool[]) view
  with hot/cold dirty flags, an optional short-term scratch context, and
  the domain check state if applicable.
- A typcache memory-context callback `ER_mc_callback` (`:45`) keeps a
  weak reference to the domain typcache entry so domain invalidation
  during a long-lived expanded record is detected.

## Phase D notes

- **Domain validation is on the WRITE path, not the READ path.** Setting a
  field on a domain-over-composite record runs
  `check_domain_for_new_field` (`:48`), which validates the new field
  value against the domain constraint expressions. Reads are not
  re-validated. [verified-by-code via signature]
- **Tupdesc lifecycle is the load-bearing concern.** The header holds a
  reference to a typcache TupleDesc; if the type is altered (ALTER TYPE
  … ADD ATTRIBUTE), the typcache invalidation path needs to either
  refresh or invalidate this expanded record. The `tupdesc_id` field
  serves as a generation counter for this; bugs here would surface as
  "attribute %d of type %s has wrong type" mid-statement.
- **Lazy deconstruction:** a record may exist in three states — flat
  tuple only, deconstructed only, or both. Mutations dirty the
  deconstructed view; reads of the flat tuple re-flatten as needed.
  This is where the perf win over plain HeapTuple operations comes from.
- **No untrusted input.** All callers are internal C. The wire-format
  composite types still go through `record_in` / `record_out` in
  `rowtypes.c`, not here.
- The 1633 lines are mostly mechanical per-field accessors + careful
  context bookkeeping; not a CVE-class file historically.

## Potential issues

- `[ISSUE-undocumented-invariant: long-lived expanded records must
  re-validate tupdesc_id against the typcache when used after a
  potential ALTER TYPE. (medium) — load-bearing for correctness]`
- `[ISSUE-correctness: ER_FLAG_IS_DOMAIN means writes validate but reads
  don't; if external code mutates the flat tuple directly, domain
  invariants can be silently violated. (low)]`
- `[ISSUE-undocumented-invariant: short-term scratch context lifetime is
  bounded by the next operation that resets it; holding a Datum derived
  from a deconstructed field across a reset is unsafe (medium).]`

## Cross-references

- `source/src/include/utils/expandedrecord.h` — `ExpandedRecordHeader`,
  the public accessors, `ER_FLAG_*` constants.
- `source/src/backend/utils/cache/typcache.c` — supplies the cached
  TupleDescs and the domain validation closures.
- `source/src/pl/plpgsql/src/pl_exec.c` — the heaviest consumer.
- `source/src/backend/utils/adt/expandeddatum.c` — the generic R/W vs R/O
  expanded-Datum infrastructure this builds on.

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->

## Confidence tag tally

- `[verified-by-code]` × 2
- `[from-comment]` × 3
- `[inferred]` × 3
