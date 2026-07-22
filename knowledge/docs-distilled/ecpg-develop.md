---
source_url: https://www.postgresql.org/docs/current/ecpg-develop.html
fetched_at: 2026-07-21T18:50:00Z
anchor_sha: 0da71d90d623
title: "ECPG — Internals (§36 leaf): how the preprocessor rewrites EXEC SQL into ECPGdo() calls, the 10-arg-per-variable calling convention, ECPGt_* type codes"
maps_to_skill: wire-protocol
---

# ECPG — Internals (the preprocessor→ECPGdo runtime contract)

The load-bearing internals chapter of Chapter 36 (ECPG — Embedded SQL in C).
Describes how the `ecpg` preprocessor turns a `.pgc` file's `EXEC SQL …`
statements into ordinary C: it emits calls into the `libecpg` runtime, the
central one being `ECPGdo()`. This is the ECPG analogue of the libpq
`PQexecParams` path — but the argument-passing convention is entirely
ECPG-specific and code-generated.

## Non-obvious claims

- **Every generated file gets a fixed 2-include prologue.** ECPG prepends
  `#include <ecpgtype.h>` and `#include <ecpglib.h>` (plus two comment lines)
  to the top of every output `.c` file. Those two headers are the entire
  compile-time surface: `ecpgtype.h` carries the `ECPGt_*` type-code enum,
  `ecpglib.h` carries the runtime prototypes. [from-docs]

- **Host variables become `?` placeholders, resolved positionally at
  runtime.** A colon-prefixed symbol (`:index`) inside an `EXEC SQL` statement
  must have been declared in an `EXEC SQL BEGIN DECLARE SECTION` … `END DECLARE
  SECTION` block; the preprocessor strips it from the SQL text, substitutes a
  `?` placeholder, and passes the C variable as a separate argument block to
  `ECPGdo`. Input and output variables are bound by *position*, not by name.
  [from-docs]

- **`ECPGdo`'s real prototype is much wider than the docs' example shows.** The
  Internals chapter's worked example writes
  `ECPGdo(__LINE__, NULL, "SELECT res FROM mytable WHERE index = ?", …)`, but
  the actual emitted/declared signature is
  `bool ECPGdo(const int lineno, const int compat, const int force_indicator,
  const char *connection_name, const bool questionmarks, const int st,
  const char *query, ...)`
  (`source/src/interfaces/ecpg/include/ecpglib.h:30-32`, definition
  `source/src/interfaces/ecpg/ecpglib/execute.c:2295`). So before the query
  string the call actually carries: the source line, the **compatibility mode**
  (`compat` — ORACLE/INFORMIX vs native), a **force-indicator** flag, the
  **connection name**, a **questionmarks** bool (whether `?` placeholders are
  in use), and a **statement-type** int `st`. The docs' 2-arg prefix is a
  didactic simplification — treat the header as authoritative. [verified-by-code]

- **Each host variable is passed as a *fixed 10-argument block*.** Per the
  Internals chapter, for every bound variable ECPG emits, in order: (1) type as
  an `ECPGt_*` enum, (2) a pointer to the value (or pointer-to-pointer), (3)
  the size (for `char`/`varchar`), (4) number of array elements, (5) byte
  offset to the next array element, (6) the *indicator* variable's `ECPGt_*`
  type, (7) pointer to the indicator, (8) a `0` (unused), (9) indicator-array
  element count, (10) indicator-array element offset. That is why a two-column
  query generates ~20 stereotyped arguments. [from-docs]

- **Two sentinel type codes delimit the input vs output variable lists.**
  `ECPGt_EOIT` ("End Of Input Types") closes the input-variable blocks;
  `ECPGt_EORT` ("End Of Result Types") closes the output-variable blocks and
  ends the varargs. Both live in the same enum as the real types
  (`source/src/interfaces/ecpg/include/ecpgtype.h:62-63`), and a variable
  with no NULL indicator uses `ECPGt_NO_INDICATOR` (`:64`) in slot 6.
  [verified-by-code]

- **The `ECPGt_*` enum is `1`-based and ordered simple→complex.** `enum
  ECPGttype` runs `ECPGt_char = 1` upward through the C scalar types, then the
  pgtypes pseudo-types (`ECPGt_numeric`, `ECPGt_decimal`, `ECPGt_date`,
  `ECPGt_timestamp`, `ECPGt_interval`), then the aggregate/meta codes
  (`ECPGt_array`, `ECPGt_struct`, `ECPGt_descriptor`, `ECPGt_sqlda`,
  `ECPGt_bytea`) and the two EOIT/EORT sentinels
  (`ecpgtype.h:41-67`). The `IS_SIMPLE_TYPE()` macro (`:92`) treats
  `ECPGt_char … ECPGt_interval` plus `ECPGt_string`/`ECPGt_bytea` as "simple",
  which is what gates the marshaling fast path. [verified-by-code]

- **`OPEN cursor` is *not* copied to the output verbatim.** Instead the
  preprocessor substitutes the cursor's original `DECLARE … CURSOR FOR`
  statement at the `OPEN` site — because the actual SQL to send is the
  declared query, and `DECLARE` in embedded SQL is a preprocessor-only
  construct (it never reaches the server on its own). This is the one place the
  preprocessor moves a statement across the source. [from-docs]

## Links into corpus

- Sibling client interface, fully mined: `knowledge/docs-distilled/libpq-exec.md`,
  `knowledge/docs-distilled/libpq-async.md` — ECPGdo ultimately drives the same
  libpq `PQexecParams`/extended-query path underneath.
- Runtime library entry points: `knowledge/docs-distilled/ecpg-library.md`.
- The type-code marshaling table this convention feeds:
  `knowledge/docs-distilled/ecpg-variables.md`.
- Skill: `wire-protocol` (ECPG is a client interface over the v3 protocol);
  `parser-and-nodes` for the grammar-driven preprocessor lineage
  (`src/interfaces/ecpg/preproc/preproc.y`).
