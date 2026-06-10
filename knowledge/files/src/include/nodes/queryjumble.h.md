# src/include/nodes/queryjumble.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 116 [verified-by-code]

## Role

Query normalization + fingerprinting infrastructure. Walks a `Query`
tree, appends bytes for each significant node into a `jumble[]`
buffer, records the locations of `Const` nodes so they can be elided
from the normalized query text, and returns a `JumbleState`. The
final 64-bit hash of `jumble[]` is the `query_id` exposed via
`pg_stat_activity` / `pg_stat_statements`.

## Public API

- `LocationLen` — `location`, `length`, `squashed`, `extern_param`
  (`:22-32`). A "squashed list" means an `ARRAY[1,2,3,...]` form
  collapsed to a single representative.
- `JumbleState` — main accumulator: `jumble[]` buffer, `clocations[]`
  array, `highest_extern_param_id`, `has_squashed_lists`,
  `pending_nulls`, optional `total_jumble_len` (assert-only)
  (`:38-78`).
- `ComputeQueryIdType` enum: OFF / ON / AUTO / REGRESS (`:81-87`).
- `compute_query_id` GUC, `query_id_enabled` runtime flag,
  `EnableQueryId()` (`:90, 98, 100`).
- `JumbleQuery(Query *) -> JumbleState*` — entry point (`:97`).
- `CleanQuerytext(query, *location, *len) -> const char *` — strips
  comment-leading whitespace (`:93`).
- `ComputeConstantLengths(jstate, query, query_loc) -> LocationLen*`
  (`:94-96`).
- `IsQueryIdEnabled()` inline (`:106-114`).

## Invariants

- INV-JUMBLE-EXTERN-PARAM: comment `:55-61` [from-comment] —
  query-supplied PARAM_EXTERN numbers are normally preserved, but
  presence of a squashed list forces full renumbering to avoid gaps.
- INV-JUMBLE-NULL-FLUSH: `pending_nulls` accumulates and is flushed
  before any value append AND before final hash (`:67-72`
  [from-comment]). Failing to flush would let NULL streaks alias
  with shorter streaks of the same hash.
- INV-JUMBLE-LOC-SIGNED: `location` is signed int byte-offset; -1
  for "no location" follows parser convention.
- `length == -1` in LocationLen means "ignore" (`:25`); used for
  Constants whose location was unreliable.

## Notable internals

- The jumble buffer is fixed-size at start (`JUMBLE_SIZE` = 1024 in
  `queryjumble.c`); overflow truncates — collisions get more likely
  on very long queries.
- Hash is XX64 (or SHA, depending on PG version); 64 bits = query_id.

## Trust boundary / Phase D surface

- **A11 anchor — pg_stat_statements cleartext capture.** The
  jumble normalization runs in `analyze.c` / `pg_analyze_and_rewrite_*`
  hook chain. Crucially: `pg_stat_statements` stores the
  **normalized query text** (constants replaced with `$1`, `$2`,
  …), NOT the raw text. **BUT:**
  - Utility statements (`track_utility=on`, default) are stored
    verbatim. `CREATE USER alice PASSWORD 'secret'` → password
    visible in `pg_stat_statements.query` until rotated out.
    Constants are NOT redacted in utility paths.
  - `CleanQuerytext` strips leading comments but does NOT redact
    other secrets.
  - Constants inside `EXECUTE 'sql with literal'` are inside a
    string and not jumbled — also retained.
- **A11 echo — query_id is a side-channel.** Knowing a victim's
  query plan-shape lets an attacker on `pg_stat_activity` infer
  what they're running by query_id. Mitigation: query_id alone
  doesn't reveal parameters, but combined with timing it's an
  oracle.
- **Squashed-list normalization (PG18 feature).** Collapsing
  `IN (1,2,3,...1000)` to a single representative reduces
  pg_stat_statements bloat but also LOSES the cardinality signal
  for an attacker doing query-shape inference.

## Cross-references

- `contrib/pg_stat_statements/pg_stat_statements.c` — primary
  consumer; calls `JumbleQuery` via hook chain.
- `backend/nodes/queryjumblefuncs.c` — jumble walker
  implementation (auto-generated dispatch on NodeTag).
- `tcop/postgres.c` — sets `MyProc->queryid` after jumble.
- A11 corpus / phase-D notes on password cleartext exposure.

## Issues / drift

- `[ISSUE-TRUST: A11 — utility statements like CREATE USER ... PASSWORD '...' are NOT redacted; jumble path stores verbatim text (high)] — source/src/include/nodes/queryjumble.h:93-97`
- `[ISSUE-TRUST: query_id 64-bit + global visibility via pg_stat_activity enables cross-role plan-shape inference (medium)] — source/src/include/nodes/queryjumble.h:80-100`
- `[ISSUE-DOC: header doesn't note that EXECUTE-string literals bypass normalization (medium)] — source/src/include/nodes/queryjumble.h:19-32`
- `[ISSUE-CODE: JUMBLE_SIZE buffer cap (in .c) silently truncates; collision behaviour on truncated jumbles not documented in header (low)] — source/src/include/nodes/queryjumble.h:40-44`
