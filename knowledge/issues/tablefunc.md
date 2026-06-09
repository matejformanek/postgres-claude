# Issues — `contrib/tablefunc`

Per-subsystem issue register for **tablefunc**, the `crosstab()` /
`connectby()` SRF extension. 1 source file / 1 575 LOC. **Contains
the most concrete SQL-injection sink in A13.**

**Parent doc:** `knowledge/files/contrib/tablefunc/tablefunc.md`.

**Source:** 10 entries surfaced 2026-06-09 by A13-4.

## Headlines

1. **🚨 `connectby_text` interpolates 5 of 6 identifier-shaped
   arguments RAW into SQL** (`tablefunc.c:1227-1247`). Builds:
   `appendStringInfo("SELECT %s, %s FROM %s WHERE %s = %s AND ...",
   key_fld, parent_key_fld, relname, parent_key_fld,
   quote_literal_cstr(start_with), key_fld, ...)`. **Only
   `start_with` is `quote_literal_cstr`'d.** Any application exposing
   `relname`/`key_fld`/`parent_key_fld`/`orderby_fld`/`branch_delim`
   to user input gets straight-line SQL injection — gated only by
   SPI `read_only=true` (still permits `pg_authid` reads,
   `pg_read_server_files()`, etc., at caller's privileges).

2. **`build_tuplestore_recursively` has NO `check_stack_depth()`**
   — only `max_depth` (user-supplied; 0=unlimited) and a fragile
   `strstr`-based cycle check guard the recursion. Deep non-cyclic
   trees crash the backend.

3. **`strstr`-based cycle detection breaks down when `branch_delim`
   substring appears inside a key.**

4. **`crosstab(text)` + `crosstab_hash(text,text)`** are unguarded
   SQL-injection sinks via SPI (more widely known/documented than
   connectby, but same class).

5. **`crosstab_hash` pivot state is O(rows × cols) palloc** with
   no `work_mem` enforcement; caller-controlled column count
   amplifies.

## Cross-sweep references

- **A9 plpgsql `exec_stmt_dynexecute`** + **A10 plperl/plpython/
  pltcl spi_exec / plpy.execute(text)** + **A11 postgres_fdw deparse
  pushdown** — `tablefunc.connectby_text` is the **5th in-tree
  text-to-SPI sink** but with the worst identifier-hygiene
  posture.
- **A12 file_fdw program option** — both are "user-supplied text
  goes to privileged execution" patterns; file_fdw at least gated
  by `pg_execute_server_program` role.

## Entries (10)

- [ISSUE-security: connectby_text interpolates relname/key_fld/
  parent_key_fld/orderby_fld RAW via appendStringInfo("...%s...");
  only start_with is quote_literal_cstr'd (likely — actively
  dangerous if any of those is user-controlled)] —
  `source/contrib/tablefunc/tablefunc.c:1227-1247`.
- [ISSUE-security: crosstab(text) / crosstab_hash(text,text)
  execute caller-supplied SQL via SPI; standard SQL-injection sink
  (likely — by design)].
- [ISSUE-security: build_tuplestore_recursively has NO
  check_stack_depth(); relies on max_depth (0=unlimited) and
  strstr cycle check; deep non-cyclic trees crash backend (likely)].
- [ISSUE-correctness: connectby cycle detection via strstr over
  branch_delim-wrapped strings breaks down when branch_delim
  substring appears inside a key (likely)].
- [ISSUE-defense-in-depth: crosstab_hash allocates O(rows × cols)
  pivot state with no work_mem enforcement; caller-controlled
  column count amplifies (nit)].
- [ISSUE-correctness: category names silently truncated to
  NAMEDATALEN-1 (63 bytes) in hash macros; equal-prefix categories
  merge or trigger DUPLICATE_OBJECT depending on order (nit)].
- [ISSUE-defense-in-depth: caller-supplied composite return type
  checked only column-wise; no width cap, names ignored (nit)].
- [ISSUE-documentation: SPI_execute(..., true, ...) doesn't prevent
  sensitive catalog reads / pg_read_server_files (nit — by design)].
- [ISSUE-correctness: connectby_text_serial int serial wraps at
  INT_MAX (nit)].
- [ISSUE-defense-in-depth: normal_rand uses pg_global_prng_state;
  not crypto-safe (nit)].
