---
source_url: https://www.postgresql.org/docs/current/xfunc-internal.html
chapter: "38 Internal Functions (xfunc-internal)"
fetched_at: 2026-06-16
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
---

# `LANGUAGE internal` functions — xfunc-internal

The neglected sibling of `LANGUAGE C` ([[knowledge/docs-distilled/xfunc-c.md]]):
"internal" functions are C functions **statically linked into the postgres
binary**, exposed to SQL by name. This is the mechanism behind every builtin.

## Non-obvious claims

- **Internal = statically linked, not dynamically loaded.** An internal
  function is compiled into the server binary; `LANGUAGE C` functions are
  loaded from a `.so`/`.dll` at runtime. Same fmgr ABI, different linkage.
  [from-docs xfunc-internal]
- **The `CREATE FUNCTION` body is the *C symbol name*, not source code, and
  it may differ from the SQL name.** Example:

  ```sql
  CREATE FUNCTION square_root(double precision) RETURNS double precision
      AS 'dsqrt'        -- C link symbol, NOT the SQL name
      LANGUAGE internal
      STRICT;
  ```

  Here `square_root` is the SQL name and `dsqrt` is the actual linked C
  symbol. [from-docs xfunc-internal]
- **An empty `AS` body means "C symbol == SQL name"** — kept for backward
  compatibility. So `AS ''` (or omitting it) only works when the SQL name
  literally matches an exported symbol. [from-docs xfunc-internal]
- **All internal functions are declared during cluster initialization**
  (`initdb` / bootstrap, §18.2). A user `CREATE FUNCTION ... LANGUAGE
  internal` doesn't *add* C code — it can only create a **new SQL-level
  alias** for a symbol that is *already* linked into the running binary.
  [from-docs xfunc-internal]
- **You cannot introduce a brand-new internal function at SQL level.** If the
  named symbol isn't already compiled in, the `CREATE FUNCTION` fails — there
  is no dynamic-link fallback the way `LANGUAGE C` has. (To add a genuinely
  new builtin you edit `pg_proc.dat` + add the C function + rebuild.)
  [inferred from "must already be present in the server"]
- **Most internal functions expect to be declared `STRICT`** (return NULL on
  any NULL input) — not enforced, but the convention to match the C code's
  assumption that it never sees a SQL NULL. [from-docs xfunc-internal]
- The catalog/dispatch glue is `fmgrtab` (the generated `fmgr_builtins`
  table mapping OID → C function pointer), built from `pg_proc.dat` at
  compile time — that's the table this whole mechanism rides on, even though
  this docs page doesn't name it. [inferred — see corpus link]

## Links into corpus

- The dynamically-loaded counterpart:
  [[knowledge/docs-distilled/xfunc-c.md]] +
  [[knowledge/files/src/backend/utils/fmgr/fmgr.c.md]].
- The generated builtin dispatch table:
  [[knowledge/files/src/include/utils/fmgrtab.md]] (`fmgr_builtins`).
- Where new builtins are actually declared:
  [[knowledge/docs-distilled/system-catalog-initial-data.md]]
  (`pg_proc.dat`) — the `catalog-conventions` skill governs adding one.
- Volatility marking a function still needs:
  [[knowledge/docs-distilled/xfunc-volatility.md]].

## Caveats / verification

- All claims `[from-docs xfunc-internal]` except where tagged `[inferred]`.
  The "symbol must already be linked" behavior and the `fmgr_builtins`
  lookup are verifiable in `source/src/backend/utils/fmgr/fmgr.c`
  (`fmgr_internal_function`) and the generated `fmgroids.h`/`fmgrtab.c` at
  anchor `b78cd2bda5b1a306e2877059011933de1d0fb735`.
