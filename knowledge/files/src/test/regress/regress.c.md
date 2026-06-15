---
path: src/test/regress/regress.c
anchor_sha: e18b0cb7344
loc: 1491
depth: read
---

# src/test/regress/regress.c

## Purpose

The **contrib-style test extension** built into the regression suite —
a C module loaded as the dynamic library `regress` (registered via
`PG_MODULE_MAGIC_EXT(.name = "regress")` at `:91-94`) that exposes
SQL-callable functions used exclusively by regression tests. It is the
catch-all home for C-language helpers that exercise backend internals
that pure-SQL tests can't reach: atomic ops, pg_lzcompress round-trip,
multi-byte conversion helpers, indirect TOAST construction, the FDW
handler stub, support-function harness, opclass-options harness, and a
handful of legacy demo types (`widget`, `int44`, `complex`). Tests in
`src/test/regress/sql/*.sql` import these via `CREATE FUNCTION ...
LANGUAGE C` declarations in `create_function_*.sql`. `[verified-by-code]`

## Public symbols

35 `PG_FUNCTION_INFO_V1` entries. Grouped by concern:

| Group | Functions | Sites |
|---|---|---|
| Geometric demo | `interpt_pp`, `overpaid`, `widget_in`, `widget_out`, `pt_in_widget` | `:98, :150, :177-178, :226` |
| String demo | `reverse_name` | `:242` |
| Trigger demo | `trigger_return_old` (used as a trigger function returning OLD) | `:263` |
| Demo type `int44` | `int44in`, `int44out` | `:290, :314` |
| Path utility | `test_canonicalize_path` | `:331` |
| TOAST indirect | `make_tuple_indirect` (constructs an indirect-TOAST tuple to test detoasting) | `:341` |
| Environment | `get_environ`, `regress_setenv` (writes a setenv from SQL — TEST USE ONLY) | `:439, :464` |
| Process control | `wait_pid` (block until a PID exits — used in deadlock tests) | `:482` |
| Atomics smoke test | `test_atomic_ops` | `:708` |
| FDW stub | `test_fdw_handler`, `test_fdw_connection` | `:727, :735` |
| Catalog probe | `is_catalog_text_unique_index_oid` | `:742` |
| Planner support fn | `test_support_func`, `test_inline_in_from_support_func` | `:749, :822` |
| Opclass options | `test_opclass_options_func` | `:941` |
| Encoding | `test_enc_setup`, `test_enc_conversion`, `test_bytea_to_text`, `test_text_to_bytea`, `test_mblen_func`, `test_text_to_wchars`, `test_wchars_to_text`, `test_valid_server_encoding` | `:949, :1014, :1131-1262` |
| Misc | `binary_coercible`, `test_relpath`, `test_translation`, `test_instr_time` | `:1270, :1283, :1315, :1394` |
| pglz | `test_pglz_compress`, `test_pglz_decompress` (round-trip a buffer through LZ) | `:1436, :1467` |

## Internal landmarks

- `PG_MODULE_MAGIC_EXT(.name = "regress", .version = PG_VERSION)`
  at `:91-94` — the dynamic-loader magic block; without it the
  module would fail to load with "incompatible library".
- `EXPECT_TRUE`, `EXPECT_EQ_U32`, `EXPECT_EQ_U64` macros (`:57-83`)
  give test assertions inside C: failure raises `elog(ERROR, ...)`
  with file/line — `test_atomic_ops` (`:708`) is the heavy user.
- `regress_lseg_construct` (`:89`, definition near `interpt_pp`) is
  the only static helper; everything else is SQL-callable.
- `TEXTDOMAIN` redefined to `"postgresql-regress"` (`:54-55`) so
  translated messages from this module are isolated from the main
  PG message catalog.
- `regress_setenv` (`:464`) is intentionally a backdoor — tests that
  need to flip env vars (e.g. `TZ`) before exercising backend code
  use it. NOT safe for production extensions.
- `make_tuple_indirect` (`:341`) builds a heap tuple whose varlena
  fields are EXTERNAL_INDIRECT pointers — used to exercise
  detoast-from-indirect paths that no normal SQL can construct.
- `test_atomic_ops` (`:708`) probes `pg_atomic_uint32` /
  `pg_atomic_uint64` semantics: CAS, fetch-add, write/read fences.
  Catches platforms where the atomics shim is broken.

## Invariants & gotchas

- Built as a dynamic library `regress.{so,dll,dylib}`, NOT linked
  into the backend. Loaded on demand via `CREATE FUNCTION ... AS
  '$libdir/regress', 'symname'` in the regression SQL.
- `PG_MODULE_MAGIC_EXT` is the modern variant (PG ≥ 18). Older
  branches used `PG_MODULE_MAGIC`. If you cherry-pick this file to
  a back-branch, swap accordingly.
- Functions here are `PARALLEL UNSAFE` by default — most don't
  declare otherwise. `regress_setenv` and `wait_pid` MUST be
  parallel-unsafe because they touch process-global state.
- The dynamic library name is hard-coded as `"regress"` in the SQL
  `CREATE FUNCTION` calls; renaming the .c file alone won't
  rename the library — see `meson.build` / `Makefile`.
- The Datum-returning style is mixed: some functions use
  `PG_RETURN_*` macros, some build composite results with
  `BlessTupleDesc` + `HeapTupleGetDatum`. Keep that style consistent
  when adding new entries.

## Cross-refs

- `knowledge/idioms/fmgr-and-spi.md` — `PG_FUNCTION_INFO_V1` macro
  and the V1 calling convention used by every entry here.
- `knowledge/files/src/test/regress/pg_regress.c.md` — the driver
  that runs the SQL tests that load this extension.
- `knowledge/subsystems/access-toast.md` — context for the
  `make_tuple_indirect` indirect-TOAST exercise.
- `knowledge/idioms/atomics.md` — what `test_atomic_ops` probes.
