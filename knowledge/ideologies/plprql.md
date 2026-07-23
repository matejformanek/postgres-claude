# plprql — a procedural language whose source language is not SQL but PRQL, transpiled to SQL at every call

- **Repo:** kaspermarstal/plprql, branch `main`, license **Apache-2.0** (`plprql/Cargo.toml:12`; README.md:266). Author **Kasper Marstal** (`Cargo.toml:6`). Built on the **pgrx** Rust extension framework (`lib.rs:1` `use pgrx::prelude::*`; README.md:122 "built on top of the pgrx framework"). Crate version tracks PG major: `18.0.0`, default feature `pg18`, supports pg13–pg18 (`Cargo.toml:3,22-28`).
- **Fetched:** README.md (266 lines), `plprql/src/lib.rs` (24), `plprql/src/fun.rs` (88), `plprql/src/plprql.rs` (91), `plprql/plprql.control` (5), `plprql/src/spi.rs` (117), `plprql/src/srf.rs` (163), `plprql/src/err.rs` (27), `plprql/src/anydatum.rs` (292), `plprql/Cargo.toml` (37).

## Domain & purpose

plprql adds a PL handler that lets you write PostgreSQL functions in **PRQL** (Pipelined Relational Query Language) instead of PL/pgSQL. PRQL is a modern pipelined query language — Unix-pipe-style line-by-line transforms — that *compiles to SQL* rather than executing directly [from-README, README.md:9]. A `LANGUAGE plprql` function's body is a PRQL pipeline (`prosrc`); at call time plprql invokes the **`prqlc`** Rust compiler crate (v0.13.12, `postgres` feature) to produce SQL, then runs that SQL through SPI (`Cargo.toml:33`; `plprql.rs:6` `use prqlc::{...compile, sql::Dialect}`). The extension also exposes helpers `prql_to_sql(text)` (compile-only, for debugging) and `prql(text[, cursor])` (ad-hoc PRQL from ORMs) [README.md:43-44,78-80].

## How it hooks into PG

- **Language-handler trio, declared as SQL via pgrx `extension_sql!`.** The `CREATE LANGUAGE plprql` statement names `plprql_call_handler` and `plprql_call_validator` (`plprql.rs:23-30`). The call handler is a bare `extern "C-unwind"` fn wrapped in `#[pg_guard]`, with a hand-written `pg_finfo_plprql_call_handler` V1 record (`plprql.rs:40-48`) and a bootstrap `CREATE FUNCTION ... LANGUAGE C ... 'MODULE_PATHNAME','plprql_call_handler'` (`plprql.rs:32-38`). The validator is a `#[pg_extern]` that is currently a **no-op TODO** — no compile-time body validation (`plprql.rs:63-66`). No dedicated **inline handler** (`DO $$ ... $$ LANGUAGE plprql`) is registered — the `CREATE LANGUAGE` names only handler + validator (`plprql.rs:24-26`), so anonymous PRQL blocks are unsupported [inferred].
- **`.control` file.** `module_pathname = '$libdir/plprql'`, `relocatable = false`, `superuser = true`; `default_version` is templated from the Cargo version `@CARGO_VERSION@` (`plprql.control:1-5`).
- **Routing.** `CREATE FUNCTION ... LANGUAGE plprql` stores the PRQL text in `pg_proc.prosrc`; every invocation enters `plprql_call_handler(fcinfo)` (`plprql.rs:48`), which builds a `Function` from the fcinfo (`fun.rs:17-33`) and dispatches on return mode.
- **Two call paths keyed on the catalog `pg_proc` shape** (`fun.rs:78-87`, `plprql.rs:54-60`):
  - `RETURNS TABLE(...)` → `proretset && proargmodes contains Table` → `Return::Table` → `table_srf_next` over `fetch_table` (multi-column rows).
  - `RETURNS SETOF x` → `proretset && !Table` → `Return::SetOf` → `setof_srf_next` over `fetch_setof` (single-column set).
  - scalar (`!proretset`) → `Return::Scalar` → `fetch_row` (one datum).
  - The `prql()` SQL wrappers add a third surface: a `RETURNS SETOF record` and a `RETURNS refcursor` PL/pgSQL function that `execute prql_to_sql(str)` at runtime (`plprql.rs:70-91`).

## Where it diverges from core idioms

**The load-bearing divergence: the function body is written in a foreign query language, compiled to SQL *on every call* by an embedded Rust compiler, and then executed via SPI — plprql itself never plans or executes anything.**

1. **`prqlc::compile` in the hot path.** Each of the three fetch functions begins `let sql = prql_to_sql(&function.body()).unwrap_or_report();` (`spi.rs:45,77,104`), where `function.body()` is `pg_proc.prosrc()` (`fun.rs:74-76`) and `prql_to_sql` calls `prqlc::compile(prql, options)` targeting `Target::Sql(Some(Dialect::Postgres))` (`plprql.rs:10-20`). There is **no compiled-plan cache**: the PRQL→SQL compile runs afresh for every function call (`spi.rs:45,77,104` all recompile) [verified-by-code]. This is a per-call CPU cost core PLs avoid — PL/pgSQL caches parsed/planned statements in the function's `plpgsql_HashTable`; see `[[knowledge/idioms/plan-cache]]`.

2. **Arguments are bound as real SPI parameters, not string-interpolated.** PRQL bodies reference positional args as `$1`, which `prqlc` passes straight through into the generated SQL as `$1` placeholders (README.md:22 `filter match_id == $1` → README.md:54 `WHERE match_id = $1`). `Function::arguments()` reconstructs a `Vec<DatumWithOid>` from `pg_proc.proargtypes()` + the raw `fcinfo.args` slice (`fun.rs:35-72`), and each fetch passes them to `client.select(&sql, None, arguments)` (`spi.rs:50,82,109`) as bound SPI parameters. **The user's argument *values* never enter the SQL string**, so there is no SQL-injection surface from arguments [verified-by-code]. (The `prql()` text wrappers are a different story: they `execute` a string the *caller* supplies as PRQL, so injection risk there is the caller's PRQL text, not bound params — `plprql.rs:73,86`.)

3. **Return-mode handling is SRF plumbing over SPI results.** `fetch_table` collects every SPI heap tuple into `Vec<Row>` of `AnyDatum` columns (`spi.rs:43-73`); `fetch_setof` collects ordinal-1 of each tuple (`spi.rs:75-101`); `fetch_row` takes `.first().get_one()` (`spi.rs:103-116`). The set-returning cases are then driven through classic ValuePerCall SRF machinery in `srf.rs`: `per_MultiFuncCall`, `init_multi_func_call`, `get_call_result_type` + `BlessTupleDesc` (`srf.rs:33-49`), `SFRM_ValuePerCall` (`srf.rs:125`), state boxed into `user_fctx` and dropped on `srf_return_done` (`srf.rs:77-95,142-146`). Notably the **entire result set is materialized in the first SRF call** (`fetch_rows()` runs once, buffering all rows into a `Box<Table>`), not streamed (`srf.rs:77-83`) [verified-by-code].

4. **No planning of its own — full delegation to core SQL via SPI.** Unlike PL/pgSQL, which owns an expression evaluator and drives the executor through SPI plans it manages, plprql's "execution engine" is one `Spi::connect(|client| client.select(...))` per call (`spi.rs:48-71,80-100,107-115`). All parsing, planning, and execution of the generated SQL happen inside core PostgreSQL's SPI/SQL path. plprql is a **transpiler + thin SRF adapter**, not an interpreter. See `[[knowledge/idioms/spi]]`.

5. **Volatility / caching implications.** The PRQL body is recompiled to SQL every call (point 1), and each call opens a fresh `Spi::connect` scope, so nothing about the generated SQL or its plan survives across invocations within the plprql layer [inferred from `spi.rs:45,48,77,80,104,107`]. Function volatility is whatever the user declared on `CREATE FUNCTION`; plprql does not inspect or enforce it.

## Notable design decisions

- **Compile-error → ereport mapping via a single SQLSTATE.** `PlprqlError` (thiserror enum) wraps `prqlc::ErrorMessages` (`err.rs:17-18`) and `pgrx::spi::Error` (`err.rs:14-15`); *all* variants map to **`ERRCODE_FDW_ERROR`** in the `ErrorReport` conversion (`err.rs:21-25`) — a somewhat arbitrary reuse of the FDW error class for PRQL compile failures [verified-by-code]. Errors surface through pgrx `unwrap_or_report()` / `pgrx::error!` (`spi.rs:45`, `plprql.rs:51`), which longjmp into PG's ereport. See `[[knowledge/idioms/error-handling]]`.
- **`AnyDatum` — a dynamic datum wrapper.** Because the SQL's result types aren't known to Rust at compile time, results flow through a custom `AnyDatum` type (`anydatum.rs`, 292 lines) implementing pgrx's `FromDatum`/`IntoDatum` so arbitrary column types round-trip (`spi.rs:59,89,112`).
- **PRQL dialect target is hard-pinned to Postgres.** `Target::Sql(Some(Dialect::Postgres))` with `format:false, signature_comment:false` (`plprql.rs:12-16`) — the generated SQL is Postgres-dialect and comment-free (the debugging `prql_to_sql` in README shows the signature comment because README predates the flag / uses defaults, README.md:60) [inferred].
- **fmgr entry by hand.** The call handler bypasses `#[pg_extern]` codegen and writes its own `pg_finfo` V1 record + `#[pg_guard] extern "C-unwind"` (`plprql.rs:40-48`) because a language handler has the fixed `(FunctionCallInfo) -> Datum` C signature. See `[[knowledge/idioms/fmgr]]`.
- **Cursor support is delegated to PL/pgSQL, not implemented in Rust.** The `prql(text, cursor_name)` wrapper is pure PL/pgSQL: `open cursor for execute prql_to_sql(str); return cursor` (`plprql.rs:81-91`), so `refcursor` semantics come free from core (README.md:78-80 `fetch 2 from player1_cursor`).
- **Test/example surface.** Unit tests live in the `plprql` crate; integration tests in a separate `plprql-tests` crate run via `cargo pgrx test pg18` (README.md:232-236); the `pg_test` harness module is wired in `lib.rs:14-24`. The README's `match_stats` KD-ratio example is the canonical `RETURNS TABLE` demo (README.md:20-41).

## Links into corpus

- `[[knowledge/ideologies/pgrx]]` — the Rust build substrate plprql sits on (`extension_sql!`, `#[pg_extern]`, `#[pg_guard]`, `Spi`).
- `[[knowledge/ideologies/plrust]]` — its Rust/pgrx sibling landing this same run: plrust compiles a *Rust* function body to native code; plprql transpiles a *PRQL* body to SQL. Same substrate, opposite execution model (native code vs. delegated SQL).
- `[[knowledge/ideologies/plv8]]`, `[[knowledge/ideologies/plr]]`, `[[knowledge/ideologies/plsh]]` — sibling non-SQL PLs (JS, R, shell), each with its own foreign-language body and handler trio.
- `[[knowledge/idioms/spi]]` — **the execution path**: plprql *is* an SPI client; `Spi::connect(|c| c.select(sql, None, args))` is its whole engine (`spi.rs:48-71`).
- `[[knowledge/idioms/fmgr]]` — the hand-written V1 finfo + call-handler C ABI (`plprql.rs:40-48`).
- `[[knowledge/idioms/error-handling]]` — PRQL/SPI errors → `ERRCODE_FDW_ERROR` ereport (`err.rs:21-25`).
- `[[knowledge/idioms/plan-cache]]` — the *absent* optimization: PRQL recompiles and SQL re-plans every call, unlike PL/pgSQL's cached plans.

## Sources

All fetched `2026-07-22` from `https://raw.githubusercontent.com/kaspermarstal/plprql/main/`:

- `README.md` — HTTP 200 (266 lines)
- `plprql/src/lib.rs` — HTTP 200 (24)
- `plprql/src/fun.rs` — HTTP 200 (88)
- `plprql/src/plprql.rs` — HTTP 200 (91)
- `plprql/plprql.control` — HTTP 200 (5)
- `plprql/src/spi.rs` — HTTP 200 (117)
- `plprql/src/srf.rs` — HTTP 200 (163)
- `plprql/src/err.rs` — HTTP 200 (27)
- `plprql/src/anydatum.rs` — HTTP 200 (292)
- `plprql/Cargo.toml` — HTTP 200 (37)

No 404s; no substitutions needed. The `.control` file's real name at this path is `plprql/plprql.control`; the task's `plprql.control` shorthand resolved there.

**Confidence:** The hook mechanism, dual call paths, per-call PRQL compile, and SPI-bound-parameter argument handling are all `[verified-by-code]` against the fetched source (`plprql.rs`, `fun.rs`, `spi.rs`, `srf.rs`, `err.rs`). PRQL-language framing and the KD-ratio / cursor examples are `[from-README]`. The absence of an inline (`DO`) handler, the whole-set-materialized-not-streamed reading, and the "nothing cached across calls" claim are `[inferred]` from the code paths cited and not from an explicit design statement. `anydatum.rs` was fetched and line-counted but only spot-cited (its role, not its internals). The `prqlc` version (0.13.12) is from `Cargo.toml`; the `0.11.1` in README output is a stale doc artifact.
