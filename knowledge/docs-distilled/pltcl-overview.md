---
source_url: https://www.postgresql.org/docs/current/pltcl-overview.html
fetched_at: 2026-07-07T20:55:00Z
anchor_sha: 9d1188f29865
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# PL/Tcl overview (§44.1) — safe-slave interpreter + start_proc GUCs

The trusted/untrusted model for PL/Tcl and the actual sandbox mechanism (a Tcl
*safe slave* interpreter), plus the `start_proc` initialization GUCs. Chapter is
§44 in the current ToC (page bodies still read "42.x" — cite by slug).

## Non-obvious claims

- **Trusted `pltcl` vs untrusted `pltclu`.** Quote: "PL/Tcl provides no way to
  access internals of the database server or to gain OS-level access under the
  permissions of the PostgreSQL server process, as a C function can do." So
  unprivileged users may create `pltcl` functions; `pltclu` uses a full
  interpreter and is superuser-only. [from-docs]
- **The trusted sandbox is a Tcl safe SLAVE interpreter**, not a call-time
  wrapper. `pltcl_init_interp()` creates it with
  `Tcl_CreateSlave(pltcl_hold_interp, interpname, pltrusted ? 1 : 0)`
  (`source/src/pl/tcl/pltcl.c:503`) — the `1` is Tcl's *safe* flag, which
  disables dangerous commands (`open`, `exec`, …). The untrusted case passes `0`
  (full interp; Tcl auto-runs `Tcl_Init`, unwanted for the trusted case).
  [verified-by-code @9d1188f29865]
- **One interpreter per SQL role (per trust flavor).** Interpreter descriptors
  are fetched/created by `pltcl_fetch_interp()` (declared `pltcl.c:277`), keyed
  by `user_id` (`snprintf(interpname, ..., "subsidiary_%u", user_id)`,
  `pltcl.c:506`). This is what isolates one role's Tcl globals from another's.
  [verified-by-code @9d1188f29865]
- **SPI + `elog` are the ONLY backend doors.** Database access is limited to the
  `spi_*` commands and message-raising to `elog` — both installed into the interp
  via `Tcl_CreateObjCommand` in `pltcl_init_interp` (`pltcl.c:519+`:
  `elog`/`quote`/`argisnull`/`return_null`/`return_next`/`spi_exec`/`spi_prepare`/
  `spi_execp`/`subtransaction`/`commit`/`rollback`). [verified-by-code @9d1188f29865]
- **`pltcl.start_proc` / `pltclu.start_proc`** name a Tcl procedure run once when
  the (trusted / untrusted) interpreter is first used in a session — the PL/Tcl
  analog of `plperl.on_init`. Defined via `DefineCustomStringVariable("pltcl.start_proc",
  ...)` / `"pltclu.start_proc"` (`pltcl.c:471` / `:478`), backing
  `pltcl_start_proc` / `pltclu_start_proc` (`pltcl.c:247-248`); invoked by
  `call_pltcl_start_proc()` (`pltcl.c:278`). [verified-by-code @9d1188f29865]
- **Install via `CREATE EXTENSION pltcl` / `pltclu`.** PL/Tcl functions cannot
  implement type I/O functions (no custom-type input/output in Tcl). [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/pltcl-dbaccess.md]] — the `spi_*` command surface.
- [[knowledge/docs-distilled/pltcl-global.md]] — the per-role interpreter
  isolation seen from the `GD`-array side.
- [[knowledge/docs-distilled/plperl-under-the-hood.md]] — Perl's opcode-mask
  sandbox (contrast with Tcl's safe-slave interpreter).
- [[knowledge/docs-distilled/plhandler.md]] — the C PL handler contract.
