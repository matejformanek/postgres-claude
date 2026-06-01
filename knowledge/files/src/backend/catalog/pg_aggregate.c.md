# pg_aggregate.c

- **Source path:** `source/src/backend/catalog/pg_aggregate.c`
- **Lines:** ~895
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Routines to support manipulation of the pg_aggregate relation." CREATE AGGREGATE backend. Aggregates are pg_proc rows with `prokind='a'` *plus* a pg_aggregate row describing the state type, transition/finalize/inverse/serialize/deserialize functions, ordered-set semantics, parallel safety, and movable-aggregate support.

## Public surface

- `AggregateCreate` (46) — **the entry.** Massive parameter list. Verifies that all required transition functions exist with compatible signatures (state→state, state×args→state, state→result), records dependencies on them, inserts both pg_proc (via ProcedureCreate) and pg_aggregate rows, handles MOVING AGGREGATE (inverse transition for window framing).
- `lookup_agg_function` (827) — resolve the named transition/final/inverse/etc. function and check signature.

## Confidence tag tally

`[verified-by-code]=2`
