# `src/backend/utils/adt/pg_dependencies.c`

- **File:** `source/src/backend/utils/adt/pg_dependencies.c` (873 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

I/O support for the **`pg_dependencies`** pseudo-type — the on-disk
format for **functional-dependency extended statistics**
(`CREATE STATISTICS … (dependencies)`). The "in" path accepts a JSON
text representation; the "out" path emits JSON for human consumption
and `pg_dump`. The actual bytea-format serialization is delegated to
`statistics/dependencies.c` (`statext_dependencies_{serialize,
deserialize}`).

## Key functions

### Parser (JSON SAX callbacks)

The file defines a state machine `DependenciesSemanticState` (`:28-38`)
walked by `pg_parse_json` via these callbacks:

- `dependencies_object_start`/`_end` (`:63+`),
- `dependencies_array_start`/`_end`,
- `dependencies_array_element_start`,
- `dependencies_object_field_start`,
- `dependencies_scalar` —
- which together accept the schema
  `[{"attributes": [a1,a2,...], "dependency": k, "degree": d}, ...]`
  (`:741-744` [from-comment]).
- `build_mvdependencies(parse_state, str)` (~`:680+`) — after
  successful parse, builds an `MVDependency *` per item, checks no
  two items have duplicate attribute lists (`:706-723`), then calls
  `statext_dependencies_serialize` to produce the bytea
  (`:726`). [verified-by-code]

### fmgr entry points

- `pg_dependencies_in(PG_FUNCTION_ARGS)` (`:747-807`) — sets up
  semantic state with `escontext = fcinfo->context` for soft-error
  propagation, calls `pg_parse_json` then `build_mvdependencies`.
  Generic JSON parse failures emit "Input data must be valid JSON" if
  no specific soft error was already raised (`:800-804`).
  [verified-by-code]
- `pg_dependencies_out(PG_FUNCTION_ARGS)` (`:813-848`) — calls
  `statext_dependencies_deserialize(data)` then formats each dep as
  JSON. **Errors with `elog(ERROR, "invalid zero-length nattributes
  array in MVDependencies")` at `:830-831`** for malformed
  `nattributes < 1`. [verified-by-code]
- `pg_dependencies_recv(PG_FUNCTION_ARGS)` (`:853-861`) — explicitly
  rejects binary input with `ERRCODE_FEATURE_NOT_SUPPORTED`.
  [verified-by-code]
- `pg_dependencies_send(PG_FUNCTION_ARGS)` (`:869-873`) — delegates
  to `byteasend` since the on-disk form IS a bytea. [verified-by-code]

## Phase D notes

- **Trust boundary for forged storage**: `pg_dependencies_out` accepts
  bytea from `pg_statistic_ext_data` and passes it to
  `statext_dependencies_deserialize` (in `statistics/dependencies.c`,
  `:492-580`). That deserializer:
  - Validates `magic == STATS_DEPS_MAGIC` (`dependencies.c:520-522`).
  - Validates `type == STATS_DEPS_TYPE_BASIC` (`:524-526`).
  - Rejects `ndeps == 0` (`:528-529`).
  - Pre-checks `VARSIZE_ANY_EXHDR(data) >= MinSizeOfItems(ndeps)`
    (`:532-536`).
  - But per-item **`nattributes` (k)** is only `Assert((k >= 2) && (k
    <= STATS_MAX_DIMENSIONS))` (`:557`) — in a non-debug build a
    crafted bytea with `k = INT_MAX` would `palloc(offsetof(…) + k *
    sizeof(AttrNumber))`, which `palloc` itself caps at `MaxAllocSize`
    and ereports. So the worst-case is a clean error, not memory
    corruption. [verified-by-code]
- **Recv path safety**: `pg_dependencies_recv` is intentionally
  disabled, so attacker-controlled bytea cannot arrive via COPY BINARY
  or wire protocol — only via direct catalog write (extension or
  superuser). [verified-by-code]
- **JSON-in path**: `pg_parse_json` is a hardened parser; the state
  machine guards against duplicate keys and missing required fields.
  All errors flow through `errsave(escontext, …)` so they can be soft
  if caller is COPY-with-on-error. [verified-by-code]

## Potential issues

- [ISSUE-trust-boundary: `statext_dependencies_deserialize` validates
  header but per-item `k = nattributes` is only Assert-bounded; relies
  on `palloc`'s `MaxAllocSize` cap to convert a crafted bytea into a
  clean ereport rather than a heap-overflow (low — `palloc` does the
  cap, but the defense-in-depth would be to runtime-check `k` against
  `STATS_MAX_DIMENSIONS`) (maybe)]
- [ISSUE-undocumented-invariant: `MVDependency.attributes[]` last
  entry encodes the dependent attribute number; `nattributes` ≥ 2 is
  the implicit invariant (`pg_dependencies_out:830-831`
  ereports if not) (info)]
- [ISSUE-info-disclosure: out-format includes raw attribute numbers
  from the statistics object — these reveal column ordering, which
  is already visible via `\d` so not a real leak (info)]

## Cross-references

- `source/src/include/statistics/extended_stats_internal.h` —
  `MVDependencies`, `MVDependency`, function decls.
- `source/src/include/statistics/statistics_format.h` —
  `STATS_DEPS_MAGIC`, `STATS_DEPS_TYPE_BASIC`,
  `PG_DEPENDENCIES_KEY_ATTRIBUTES`, etc.
- `source/src/backend/statistics/dependencies.c` —
  `statext_dependencies_{serialize, deserialize}`,
  `dependency_degree` machinery.
- `source/src/common/jsonapi.c` — `pg_parse_json`.

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->

## Confidence tag tally
- `[verified-by-code]` × 7
- `[from-comment]` × 1
