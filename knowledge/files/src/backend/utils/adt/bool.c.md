# `src/backend/utils/adt/bool.c`

- **File:** `source/src/backend/utils/adt/bool.c` (410 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

Functions for the built-in `boolean` type — I/O, comparison, hash, and the
`bool_and`/`bool_or` (a.k.a. SQL `EVERY`/`ANY`) aggregate state machinery.
Also exports `parse_bool` / `parse_bool_with_len`, used by GUC parsing and
many backend callers. (`bool.c:1-14` [from-comment])

## Type role

- **Input** via `parse_bool_with_len` (`:37`) — accepts `true/false/yes/no/on/off/1/0`
  and unique case-insensitive prefixes (`tr`, `fa`, etc.). `'o'` is explicitly
  ambiguous so it requires `on` or `off` minimum (`:78-93` [verified-by-code]).
- **I/O fmgr:** `boolin` (`:127`), `boolout` (`:158`), `boolrecv` (`:175`),
  `boolsend` (`:188`). `boolrecv` accepts **any nonzero byte** as true
  (`:172` [from-comment]) — wire-format polymorphism by design.
- **Cast:** `booltext` (`:205`) — emits lowercase `"true"/"false"`, deliberately
  different from `boolout` (`"t"/"f"`) to match the SQL spec (`:198-203` [from-comment]).
- **Comparison:** `booleq`/`boolne`/`boollt`/`boolgt`/`boolle`/`boolge`.
  Order: false (0) < true (1).
- **Hash:** `hashbool` / `hashboolextended` via `hash_uint32`.

## Aggregate state

`BoolAggState` (`:317`) holds `aggcount` (non-null inputs) and `aggtrue`
(non-null true inputs). State data lives in the aggregate's memory context
(via `AggCheckCallContext` + `MemoryContextAlloc`, `:329-333`).

- `booland_statefunc` / `boolor_statefunc` (`:300`, `:312`) — used in plain
  aggregate mode (not moving-aggregate).
- `bool_accum` / `bool_accum_inv` (`:341`, `:362`) — accumulate / inverse for
  windowed `bool_and`/`bool_or`.
- `bool_alltrue` / `bool_anytrue` (`:383`, `:398`) — final functions returning
  NULL if no non-null inputs were seen.

## Phase D notes

- `boolrecv` "any nonzero byte = true" means the wire format is **not
  canonical**. Two distinct on-wire byte values both decode to true, so
  binary protocol roundtrips after a `boolsend` will normalize to 0x01,
  but extension-emitted nonzero bytes pass through. Hash and comparison
  use the post-decode `bool` value so this is correctness-safe, but
  *external* binary consumers should not assume byte-identity. [inferred]
- `boolin` skips ASCII whitespace via `isspace`; not multibyte-aware but
  not exploitable because the parser also wants ASCII tokens. [verified-by-code]
- The aggregate state callers must respect the documented "plain mode only"
  contract for `booland/boolor_statefunc`. If invoked in moving-aggregate
  mode by mistake, they would still work but `bool_accum_inv` would not.

## Potential issues

- `[ISSUE-undocumented-invariant: boolrecv accepts any nonzero byte as true; wire
  protocol is not canonical. (low)]` — documented in the comment but worth
  surfacing for client implementors. `:171-172`
- `[ISSUE-info-disclosure: error message echoes raw input via "%s" in errmsg
  (:150). (info)]` — standard PG idiom; input string is already in this session.

## Cross-references

- `source/src/include/utils/builtins.h` — declarations.
- `source/src/backend/utils/misc/guc.c` — uses `parse_bool` for bool GUCs.

## Confidence tag tally

- `[verified-by-code]` × 3
- `[from-comment]` × 3
- `[inferred]` × 1
