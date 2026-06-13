---
path: src/interfaces/ecpg/ecpglib/execute.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 2316
depth: deep
---

# `execute.c` — the ecpg runtime statement-execution engine

## Purpose

This file is the heart of the ecpglib runtime. It implements `ECPGdo()` — the
single entry point that every preprocessor-generated `EXEC SQL` statement
expands into — and the full pipeline behind it: build a `struct statement`,
walk the variadic host-variable list, convert each input host variable into a
server-ready text/binary parameter, splice or bind it into the command,
send the command to the server via libpq (`PQexec` / `PQexecParams` /
`PQexecPrepared`), then dispatch the result tuples back into the output host
variables (or into a descriptor / SQLDA). [verified-by-code execute.c:2295,2261]

The design intent (per the file header) is to "hide all the tedious messing
around with tuples" behind one function. [from-comment execute.c:4-7] Errors are
not returned as rich objects; they are raised into the thread's `sqlca`
structure via `ecpg_raise` / `ecpg_raise_backend` and signalled to the caller
as a `false` return. [verified-by-code execute.c:1672,1911]

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `bool ECPGdo(int lineno, int compat, int force_indicator, const char *connection_name, bool questionmarks, int st, const char *query, ...)` | execute.c:2295 | Public ABI entry; wraps `va_start`/`ecpg_do`/`va_end`. The symbol the preprocessor emits. |
| `bool ECPGdo_descriptor(int line, const char *connection, const char *descriptor, const char *query)` | execute.c:2309 | Legacy "old descriptor interface"; builds a fixed va-list and delegates to `ECPGdo`. |
| `bool ecpg_do(int lineno, ..., va_list args)` | execute.c:2261 | va_list form so other TUs can reuse the pipeline. Orchestrates prologue → build_params → autostart_transaction → execute → process_output → epilogue, with a single `fail:` epilogue path. |
| `bool ecpg_do_prologue(...)` | execute.c:1945 | Allocs the `statement`, sets C numeric locale, parses the va-list into `inlist`/`outlist`, resolves EXECUTE/PREPARE names. |
| `void ecpg_do_epilogue(struct statement *stmt)` | execute.c:2233 | Restores locale, `free_statement()`. NULL-safe. |
| `bool ecpg_build_params(struct statement *stmt)` | execute.c:1214 | Per-input-variable loop: store_input → find placeholder → splice or push into param arrays. |
| `bool ecpg_autostart_transaction(struct statement *stmt)` | execute.c:1582 | Emits `begin transaction` when non-autocommit and txn is idle. |
| `bool ecpg_execute(struct statement *stmt)` | execute.c:1603 | Sends the command; frees param arrays; checks the PGresult. |
| `bool ecpg_process_output(struct statement *stmt, bool clear_result)` | execute.c:1672 | Dispatch on `PQresultStatus`; fills out-vars / descriptor / SQLDA; drains async NOTIFY. |
| `bool ecpg_store_input(int lineno, bool force_indicator, const struct variable *var, char **tobeinserted_p, bool quote)` | execute.c:509 | Host-var → server text/binary literal. The big per-type `switch`. |
| `bool ecpg_store_result(const PGresult *results, int act_field, const struct statement *stmt, struct variable *var)` | execute.c:306 | One result column → one output host var (handles arrays + `char**foo=0` mode). |
| `void ecpg_free_params(struct statement *stmt, bool print)` | execute.c:1109 | Frees `paramvalues[]`/lengths/formats, nulls them, zeroes `nparams`. |

## Internal landmarks

The pipeline (driven by `ecpg_do`, execute.c:2261):

1. **`ecpg_do_prologue`** (execute.c:1945) — `ecpg_alloc`s the `struct statement`;
   switches to a thread-safe C numeric locale via `uselocale(ecpg_clocale)`
   (or `setlocale`+`_configthreadlocale` fallback, execute.c:1984-2014); resolves
   `ECPGst_prepnormal` → auto-prepare (execute.c:2020), `ECPGst_execute` → look up
   the prepared name with `ecpg_prepared` (execute.c:2047-2068); then the
   **va-list walk** (execute.c:2104-2204) builds `inlist` (until `ECPGt_EOIT`) and
   `outlist` (until `ECPGt_EORT`), reading 10 va_args per variable. NULL
   `var->pointer` ⇒ "statement not prepared" raise (execute.c:2175).

2. **`ecpg_build_params`** (execute.c:1214) — reads `standard_conforming_strings`
   off the connection (execute.c:1224), then walks `inlist`. Three input shapes:
   a plain variable (→ `ecpg_store_input`, execute.c:1397), an `ECPGt_descriptor`
   (expand via `ecpg_find_desc` + `store_input_from_desc`, execute.c:1250-1281), and
   an `ECPGt_sqlda` (compat or native, execute.c:1282-1394). The converted
   `tobeinserted` is then placed at the next placeholder found by `next_insert`
   (execute.c:1411). Placeholder dispatch: `char_variable` dynamic-cursor splice
   (execute.c:1430), `$0` client-side splice (execute.c:1447), `exec_with_exprlist`
   bytea→string splice (execute.c:1474), else **append to the param arrays** by
   reallocating all three arrays in lockstep (execute.c:1498-1556). Old-style `?`
   placeholders get rewritten to `$N` in place (execute.c:1535-1555).

3. **`ecpg_store_input`** (execute.c:509) — the conversion switch. NULL detection
   from the indicator (execute.c:530-561); then per `var->type`: integers/floats
   formatted with fixed-multiplier buffers (`asize * 20`, `* 25`, `* 30`); arrays
   wrapped in `{...}`; char/varchar copied then `quote_postgres`'d; bytea/`const`/
   `char_variable` raw; numeric/interval/date/timestamp grown incrementally with
   `ecpg_realloc`. Each early-error path frees its own `mallocedval`/`newcopy`.

4. **`ecpg_execute`** (execute.c:1603) — three send paths: `PQexecPrepared`
   (ECPGst_execute), `PQexec` (nparams==0), `PQexecParams` (nparams>0). For
   `ECPGst_prepare` it registers the prepared stmt (execute.c:1637). Always
   `ecpg_free_params(stmt, true)` (execute.c:1647), then `ecpg_check_PQresult`.

5. **`ecpg_process_output`** (execute.c:1672) — switch on `PQresultStatus`:
   - `PGRES_TUPLES_OK`: zero tuples ⇒ `ECPG_NOT_FOUND` (execute.c:1701); descriptor
     ⇒ hand the PGresult to the descriptor and suppress clear (execute.c:1711-1726);
     SQLDA ⇒ free old chain, build a new chain newest-first (execute.c:1727-1843);
     else per-field `ecpg_store_result` walking `outlist` (execute.c:1845-1857),
     with too-few / too-many target checks (execute.c:1852,1859).
   - `PGRES_COMMAND_OK`: set `sqlca->sqlerrd[1]=PQoidValue`, `sqlerrd[2]=PQcmdTuples`;
     zero-row UPDATE/INSERT/DELETE ⇒ `ECPG_NOT_FOUND` (execute.c:1866-1877).
   - `PGRES_COPY_OUT`: pull rows with `PQgetCopyData` and **`printf` to stdout**
     (execute.c:1879-1902).
   - default ⇒ `ecpg_raise_backend` (should be unreachable, execute.c:1903-1913).
   Tail: conditional `PQclear` (execute.c:1916), then drain async `PQnotifies`
   (execute.c:1922-1930).

Static helpers (not all individually cited): `quote_postgres` (execute.c:42),
`free_variable` (execute.c:85), `free_statement` (execute.c:98), `next_insert`
(execute.c:113), `ecpg_type_infocache_push` (execute.c:150), `ecpg_is_type_an_array`
(execute.c:166, caches `pg_type` lookups per connection), `sprintf_double_value`
(execute.c:459), `sprintf_float_value` (execute.c:475), `convert_bytea_to_string`
(execute.c:491), `print_param_value` (execute.c:1079), `insert_tobeinserted`
(execute.c:1130, rebuilds `stmt->command` around a placeholder), and
`store_input_from_desc` (execute.c:1160).

The `struct statement` (allocated execute.c:1973) is the unit of ownership:
`command`, `name`, `inlist`/`outlist`, the three param arrays, `results`,
`oldlocale`. `free_statement` (execute.c:98) frees the lists/command/name but
**not** `results`.

## Invariants & gotchas

- **Param-array lockstep + late ownership transfer.** `paramvalues`,
  `paramlengths`, `paramformats` are grown together (execute.c:1506-1519). The
  comment at execute.c:1528 is load-bearing: `tobeinserted` ownership is handed
  to `stmt` only after all three reallocs succeed, so the early-fail paths free
  `tobeinserted` themselves and call `ecpg_free_params` (execute.c:1521-1526).
  Break this order and you double-free or leak.
- **`ecpg_free_params` is idempotent-safe.** It nulls the three pointers and
  zeroes `nparams` (execute.c:1124-1127) so a later epilogue `free_statement`
  won't touch freed arrays.
- **sqlca is the error channel.** Every failure raises into `sqlca` and returns
  `false`; callers never inspect a return value other than the boolean. The
  `sqlca == NULL` guard at execute.c:1684 is the one place that can't raise.
- **Locale must be restored.** `ecpg_do_prologue` switches numeric locale; only
  `ecpg_do_epilogue` (execute.c:2233) restores it. Every prologue failure path
  routes through `ecpg_do_epilogue` (execute.c:1994,2010,2024,2040,...) — keep that
  invariant or a failed statement leaves the thread in `LC_NUMERIC=C`.
- **`quote_postgres` consumes its argument.** It `ecpg_free(arg)` on the quote
  path (execute.c:80) and returns `arg` unchanged when `!quote` (execute.c:55) —
  so callers must not free the input after calling it, but must free the result.
- **PQclear discipline in process_output.** The `clear_result` flag is the
  switch (execute.c:1916). The descriptor path deliberately sets
  `clear_result = false` (execute.c:1721) after stealing `stmt->results` into
  `desc->result` — so the result's lifetime moves to the descriptor.
- **Result ownership on the execute error path is NOT cleared** — see Potential
  issues; `free_statement` never PQclears `stmt->results`.

## Cross-refs

- [[data.c]], [[prepare.c]], [[descriptor.c]], [[connect.c]], [[error.c]]

## Potential issues

- **[ISSUE-leak: PGresult leaked on `ecpg_execute` failure]** `execute.c:1649` —
  When `ecpg_check_PQresult` fails, `ecpg_execute` returns `false` **without**
  `PQclear(stmt->results)` and without nulling it. The `ecpg_do` `fail:` path
  (execute.c:2285) calls `ecpg_do_epilogue` → `free_statement` (execute.c:98),
  which frees lists/command/name but never the PGresult. Same on the
  `ecpg_register_prepared_stmt` failure at execute.c:1639-1643. Severity: low —
  one PGresult per failed statement, bounded by error frequency, and the process
  often exits soon after a hard error; but it is a genuine per-error libpq leak.
  [inferred from free_statement at execute.c:98-111 not touching stmt->results]
- **[ISSUE-overflow: `ECPGt_bool` array buffer undersized]** `execute.c:761` —
  Allocation is `ecpg_alloc(var->arrsize + sizeof("{}"))` = `arrsize + 3` bytes,
  but the array branch (execute.c:764-771) writes `"{"` plus `"%c,"` (2 bytes)
  per element plus the closing `"}"`, i.e. roughly `2*asize + 2` bytes. For
  `arrsize > 1` (e.g. an indicator-less `bool[10]` host array) the written length
  exceeds the allocation, a heap buffer overflow. All the *other* numeric array
  cases allocate `asize * 20` (or `*25`/`*30`) and are safe; only the bool case
  uses the `arrsize + sizeof("{}")` formula. Severity: medium — requires a
  multi-element boolean host array being sent as input; data-dependent but a
  real out-of-bounds write. [inferred from arithmetic at execute.c:761 vs
  loop at execute.c:768-771]
- **[ISSUE-robustness: unchecked `printf` of COPY OUT to stdout]**
  `execute.c:1888` — `PGRES_COPY_OUT` data is written with `printf("%s", buffer)`
  to the application's stdout, unconditionally and with no return-value check.
  This is long-standing intended behavior (ecpg COPY ... TO STDOUT goes to
  stdout) but is surprising and untestable for embedded apps that have closed or
  redirected stdout. Severity: low — by-design quirk, noted for completeness.
  [from-comment/verified-by-code execute.c:1879-1902]
