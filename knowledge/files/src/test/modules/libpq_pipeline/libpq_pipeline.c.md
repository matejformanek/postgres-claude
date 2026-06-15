---
path: src/test/modules/libpq_pipeline/libpq_pipeline.c
anchor_sha: e18b0cb7344
loc: 2263
depth: read
---

# src/test/modules/libpq_pipeline/libpq_pipeline.c

## Purpose

Standalone test program (client-side, `postgres_fe.h`) that exercises the
libpq pipeline-mode API end-to-end. Pipeline mode lets a client send many
`PQsendQueryParams` / `PQsendPrepare` / `PQsendQueryPrepared` requests in
flight and pick up `PGresult`s asynchronously via `PQgetResult`, instead of
the strict request-reply round-trip. The test program drives one named
test-case per invocation (e.g. `simple_pipeline`, `pipelined_insert`,
`transaction`, `multi_pipelines`, `pipeline_abort`, `pipeline_idle`,
`disallowed_in_pipeline`, `singlerow`, `nosync`, `prepared`, …) so the
companion TAP wrapper can sweep them all. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `main` | `libpq_pipeline.c` near EOF | argv parser; dispatches to one named test |
| `pg_fatal_impl` | `:74` | `pg_noreturn` printf-style fatal that reports the caller's `__LINE__` via a `pg_fatal(...)` macro |
| `confirm_result_status_impl` | `:95` | Reads next `PGresult`, asserts `ExecStatusType`, returns it for further checks |
| `consume_result_status_impl` | `:117` | Same plus `PQclear` |
| `process_result` (static, declared `:29`) | farther down | Used by some sub-tests to walk a result stream |

Each named test (`test_simple_pipeline`, `test_pipelined_insert`,
`test_transaction`, `test_multi_pipelines`, `test_pipeline_abort`,
`test_pipeline_idle`, `test_singlerow`, `test_nosync`, `test_prepared`, …)
is a static function with the same `(PGconn *)` signature, dispatched from
`main` on `argv[optind]`.

## Internal landmarks

- The whole file uses `pg_fatal(...)` macro (line `:73`) that expands to
  `pg_fatal_impl(__LINE__, ...)` so error messages always point at the
  invocation site, not at the helper.
- `confirm_result_status` / `consume_result_status` are the workhorses —
  every test step is "send N requests, then assert PGRES_COMMAND_OK ×N,
  then assert PGRES_PIPELINE_SYNC".
- The "demo" table is `pq_pipeline_demo(id serial PK, itemno int,
  int8filler int8)` (`:47`); two insert statements (`insert_sql`,
  `insert_sql2`) are prepared/parameterised against it.
- `PQtrace()` is plumbed in via an optional `-t tracefile` argv that, when
  set, dumps the wire protocol for later regression-diffing.
- The `pipeline_abort` test deliberately injects a SQL error mid-pipeline
  and verifies that subsequent results all come back as
  `PGRES_PIPELINE_ABORTED` until a `PQpipelineSync`.

## Invariants & gotchas

- **Client-side program** — uses `postgres_fe.h`, not `postgres.h`. It
  links against installed libpq, not the backend.
- The `Assert(fmt[strlen(fmt) - 1] != '\n')` in `pg_fatal_impl` (`:85`) is
  a coding-style enforcement: fatal messages must not have a trailing
  newline, the helper adds it.
- Pipeline mode requires the connection to be in non-blocking mode (the
  tests call `PQsetnonblocking(conn, 1)` early). Forgetting that is the
  #1 bug for users adopting pipeline mode.
- A `PQpipelineSync` must terminate every pipeline batch; tests that
  intentionally skip it (`test_nosync`) verify the "lazy sync" behavior
  introduced in PG 17.
- `disallowed_in_pipeline` confirms that operations like
  `PQsendDescribePortal` of an undeclared portal, or `COPY`, are properly
  rejected with a useful error inside pipeline mode rather than corrupting
  the protocol stream.

## Cross-refs

- `source/src/interfaces/libpq/fe-exec.c` — `PQenterPipelineMode`,
  `PQpipelineSync`, `PQexitPipelineMode`, `PQsendQueryParams`.
- `source/src/interfaces/libpq/fe-protocol3.c` — server-side protocol
  state machine; the source of `PGRES_PIPELINE_SYNC` / `PGRES_PIPELINE_ABORTED`.
- `source/doc/src/sgml/libpq.sgml` — the user-facing pipeline-mode docs.
- `source/src/test/modules/libpq_pipeline/t/001_libpq_pipeline.pl` — the
  TAP wrapper that invokes this binary with each test name and
  `diff`s captured PQtrace output against the `traces/*.trace` reference.
