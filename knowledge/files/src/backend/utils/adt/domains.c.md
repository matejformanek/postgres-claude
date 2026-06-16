# src/backend/utils/adt/domains.c

## Purpose

I/O routines for SQL domain types: `domain_in` (text input) and `domain_recv`
(binary input) call the underlying base type's input function and then apply
every CHECK / NOT NULL constraint attached to the domain. The output side of a
domain is just the base type's output (no work needed here). [from-comment]
(`domains.c:5-10`)

## Role in PG

- Every domain type's `typinput`/`typreceive` in pg_type.dat points to
  `domain_in` / `domain_recv`. Those functions take `(value, typioparam,
  typmod)` like normal but additionally use a per-`FmgrInfo` `fn_extra`
  cache (`DomainIOData`) to skip catalog work on repeated calls.
- Also provides `domain_check()` / `domain_check_safe()` (`:345-361`) —
  C-callable hook used wherever the executor needs to coerce-to-domain
  outside the type-input path (e.g. assignment via casts, JSON path
  coercion).

## Key functions

- `domain_state_setup(domainType, binary, mcxt) → DomainIOData *`
  (`:75-124`). Uses `lookup_type_cache(TYPECACHE_DOMAIN_BASE_INFO)` so a
  bad OID gives a clean user-facing error. Resolves base type's
  `typinput`/`typreceive` via `getTypeInputInfo`/`getTypeBinaryInputInfo`,
  caches `FmgrInfo`, attaches a `DomainConstraintRef` so typcache
  invalidations propagate.
- `domain_check_input(value, isnull, my_extra, escontext)` (`:137-220`).
  Loop over `my_extra->constraint_ref.constraints` after calling
  `UpdateDomainConstraintRef` (catches concurrent
  `ALTER DOMAIN`). Switch on `DOM_CONSTRAINT_NOTNULL` and
  `DOM_CONSTRAINT_CHECK`. Lazily creates a `StandaloneExprContext`
  (`:166-175`) only when a CHECK constraint actually appears. Each
  failure goes through `errsave(escontext, …)` so soft-error contexts
  can capture without `longjmp` (`:156-160`, `:194-201`).
  - For CHECK, `MakeExpandedObjectReadOnly` (`:188-189`) protects the
    input value from in-place mutation by called functions — important
    for `domain_check()` callers that might pass R/W expanded objects.
- `domain_in(string, typioparam, domainType)` (`:226-281`). Non-strict
  (so it can handle NULLs explicitly). Cache key is `(my_extra,
  domain_type)`; rebuilds if domain changes mid-query (the comment
  says "really shouldn't happen", `:250-252`).
- `domain_recv(buf, typioparam, domainType)` (`:286-337`). Same shape
  as `domain_in` but binary.
- `domain_check`/`domain_check_safe`/`domain_check_internal`
  (`:345-400`). Workhorse path. Soft variant returns `false` if
  `SOFT_ERROR_OCCURRED(escontext)`.
- `errdatatype(oid)` / `errdomainconstraint(oid, conname)` (`:406-437`) —
  attach `PG_DIAG_SCHEMA_NAME` / `PG_DIAG_DATATYPE_NAME` /
  `PG_DIAG_CONSTRAINT_NAME` to current errordata for richer client
  diagnostics.

## State / globals

None global. All state lives in caller's `fn_extra` (`DomainIOData *`).

## Phase D notes

- Uses **typcache invariants**: `DomainConstraintRef` is the formal
  hookup so `ALTER DOMAIN ADD CONSTRAINT` immediately invalidates the
  cached constraint list on next `UpdateDomainConstraintRef`.
- `domain_state_setup` comment notes (`:71-73`) the cache cannot be
  re-used for a different domain type — there's no provision for
  releasing the `DomainConstraintRef`. So a function called over
  many domain types leaks `DomainIOData` per type until end of query.
  Documented, bounded.
- **Soft error handling**: `domain_in`/`domain_recv` propagate
  `escontext` into the base-type input *and* into constraint checking,
  so a `COPY FROM ON_ERROR ignore` against a domain captures the
  constraint failure rather than aborting the row.

## Potential issues

- [ISSUE-correctness: comment at `:135` "we do not attempt to do soft
  reporting of errors raised during execution of CHECK constraints"
  but the code below uses `errsave(escontext, …)` on
  `DOM_CONSTRAINT_CHECK` failures (`:194-201`), which IS soft when
  escontext is an ErrorSaveContext. The comment understates the
  current behaviour — CHECK failures ARE captured softly; what's NOT
  captured is errors thrown *by* the CHECK expression's user code
  (e.g. a function called from the CHECK that does
  `ereport(ERROR, …)`). Worth a comment cleanup (low)]
- [ISSUE-undocumented-invariant: the per-type leak when called over
  many domain types (`:70-74`) is bounded by the query lifetime, but
  a SQL function looping over many domain casts could grow `fn_extra`
  consumption (low)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
