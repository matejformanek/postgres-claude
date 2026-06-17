---
path: src/tutorial/complex.c
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
loc: 209
depth: deep
---

# `src/tutorial/complex.c` — canonical "add a user-defined base type" example

## Purpose

The reference C module for the SQL tutorial's *user-defined type* chapter. It
implements a minimal `complex` base type (a pass-by-reference struct of two
`double`s) end to end: text I/O, binary I/O, an addition operator, and a full
B-tree operator-class support set. It is loaded by `complex.sql` (the tutorial
SQL script) via `CREATE FUNCTION ... LANGUAGE C` against the compiled `.so`.
This is the smallest complete worked example of the type-extension contract, so
it doubles as a living checklist for the `add-new-data-type` scenario.
`[from-comment]` complex.c:5-7 (the calling convention is "dictated by Postgres
architecture").

## Public symbols (all `Datum f(PG_FUNCTION_ARGS)` + `PG_FUNCTION_INFO_V1`)

| Function | Lines | Role |
|---|---|---|
| `complex_in` | 30-48 | Text input: `sscanf(" ( %lf , %lf )")`; raises `ERRCODE_INVALID_TEXT_REPRESENTATION` on parse failure. |
| `complex_out` | 52-60 | Text output: `psprintf("(%g,%g)")`. |
| `complex_recv` | 70-80 | Binary input via `pq_getmsgfloat8`. |
| `complex_send` | 84-94 | Binary output via `pq_begintypsend`/`pq_sendfloat8`/`pq_endtypsend`. |
| `complex_add` | 104-115 | The `+` operator implementation. |
| `complex_abs_lt/le/eq/ge/gt` | 147-198 | The five B-tree comparison operators. |
| `complex_abs_cmp` | 202-209 | The B-tree support-function-1 three-way comparator. |

`PG_MODULE_MAGIC;` at complex.c:15 is mandatory for any loadable module.

## Internal landmarks

- `typedef struct Complex { double x, y; }` (complex.c:17-21) — the in-memory
  representation. Pass-by-reference (16 bytes > `Datum`), so every entry point
  uses `PG_GETARG_POINTER` / `PG_RETURN_POINTER` and `palloc_object` for
  results.
- `Mag(c)` macro (complex.c:129) — squared magnitude; the ordering key.
- `complex_abs_cmp_internal` (complex.c:131-142) — the single source of truth
  for ordering. All six SQL-visible comparators are thin wrappers around it.

## Invariants & gotchas

- **Opclass consistency is load-bearing.** The header comment at
  complex.c:118-127 spells out the rule the corpus repeats elsewhere: a B-tree
  opclass's comparison operators and its support function *must* agree on the
  ordering of every pair of values. The example deliberately funnels all six
  comparators through one `_internal` routine precisely because "it's
  depressingly easy to write unintentionally inconsistent functions." This is
  the same INV that real opclasses (e.g. `btint4cmp`) must honour.
  `[from-comment]`
- **Ordering is by magnitude, not lexicographic.** `complex` sorts on
  `x²+y²`, so distinct complex values compare *equal* under this opclass
  (e.g. `(1,0)` and `(0,1)`). That is fine for a B-tree opclass (equality here
  means "same sort position"), but it means the opclass is **not** a basis for
  a uniqueness/identity equality — an intentional teaching simplification.
- `palloc_object(Complex)` (complex.c:44, used throughout) is the typed
  `palloc` wrapper; results live in the current (per-call/per-query) memory
  context, never `pfree`d by the function — the fmgr/expression machinery
  reclaims them. See [[idioms/memory-contexts]].
- Binary I/O (`recv`/`send`) is optional (complex.c:62-66 says so) but shown
  here because it is required for binary COPY and the extended-protocol binary
  format.

## Cross-refs

- [[scenarios/add-new-data-type]] — this file is the minimal instance of that
  checklist (type struct + in/out + recv/send + operators + opclass).
- [[idioms/fmgr-and-spi]] — `PG_FUNCTION_ARGS`, `PG_GETARG_*`, `PG_RETURN_*`.
- [[knowledge/files/src/tutorial/funcs.c]] — sibling tutorial module (functions
  rather than a type).
- [[idioms/error-handling]] — the `ereport(ERROR, (errcode(...), errmsg(...)))`
  shape in `complex_in`.

## Potential issues

(none — this is intentionally minimal teaching code; the magnitude-equality
behaviour is a documented design choice, not a defect.)
