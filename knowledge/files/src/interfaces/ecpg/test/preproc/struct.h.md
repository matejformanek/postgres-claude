---
path: src/interfaces/ecpg/test/preproc/struct.h
anchor_sha: e18b0cb7344
loc: 19
depth: read
---

# src/interfaces/ecpg/test/preproc/struct.h

## Purpose

**Fixture header for the ecpg preprocessor's struct-handling tests.** A
`.pgc` test source under `test/preproc/` includes this header, then uses
`EXEC SQL` host-variable references like `MYTYPE *row` or `:row.id`. The
test exists to verify that **ecpg correctly parses external C struct
declarations brought in via `#include`** and binds their fields as host
variables — i.e. that ecpg's lexer/parser tracks typedefs and members
across include boundaries, not just inside the `.pgc` file.
`[verified-by-code]` (`struct.h:1-19`)

Declares two parallel structs: a **payload** struct and a **null-flag**
struct (one `int` per payload field), the conventional ecpg pattern for
fetching a row plus its null indicators in a single
`EXEC SQL FETCH … INTO :row :ind`.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `struct mytype` / `MYTYPE` | `struct.h:1-9` | payload: `int id; char t[64]; double d1; double d2; char c[30];` |
| `struct mynulltype` / `MYNULLTYPE` | `struct.h:11-19` | five `int` flags — one indicator per payload field |

## Internal landmarks

- **Payload fields chosen to cover the type-mapping spectrum** — `int`
  (integer), `char[64]` (varchar), `double` (with a `/* dec_t */`
  comment hinting at the historical `dec_t` decimal type), `char[30]`
  (short varchar). The comment on `d1` documents that this field was
  once a `dec_t` and is now exercised as a plain `double` — a regression
  marker. `[from-comment]` (`struct.h:5`)
- **Indicator struct** mirrors the payload field-for-field but uses `int`
  for every slot — ecpg writes 0 / -1 (not-null / null) into each.

## Invariants & gotchas

- **Not a public API.** This file exists only to be consumed by `.pgc`
  files in the same directory; nothing outside `test/preproc/` should
  include it.
- **Field order must match the indicator struct.** If a test issues
  `INTO :row :ind`, ecpg maps field N of `MYTYPE` to field N of
  `MYNULLTYPE`. Reordering one without the other silently breaks the
  test.
- **Both struct tag and typedef are exposed** (`struct mytype` plus
  `MYTYPE`) on purpose: different ecpg tests use different spellings, so
  the preprocessor must accept both.

## Cross-refs

- `knowledge/files/src/interfaces/ecpg/preproc/` — the preprocessor under
  test, which must resolve `MYTYPE` to its member list when seen inside
  an `EXEC SQL` host-variable reference.
- `knowledge/files/src/interfaces/ecpg/test/pg_regress_ecpg.c.md` — the
  driver that compiles the `.pgc` consumer and diffs its emitted `.c`
  against `expected/`.
- `knowledge/files/src/interfaces/ecpg/test/preproc/strings.h.md` —
  sibling fixture for string-variable handling.
