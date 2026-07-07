---
source_url: https://www.postgresql.org/docs/current/pltcl-global.html
fetched_at: 2026-07-07T20:57:00Z
anchor_sha: 9d1188f29865
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# PL/Tcl global data (§44.6) — the GD array + per-role interpreter isolation

Why Tcl globals are private per function, the `GD` array escape hatch, and how
this ties back to the per-role interpreter isolation from `pltcl-overview.md`.

## Non-obvious claims

- **Each function body runs as a Tcl proc, so its ordinary globals are invisible
  by default** — you cannot just `set x 1` in one function and read it in
  another. [from-docs]
- **`GD` is a per-function global array reachable via `upvar`.** Quote: "A global
  array is made available to each function via the `upvar` command. The global
  name of this variable is the function's internal name, and the local name is
  `GD`." Mechanically: `upvar #0 <function_internal_name> GD`. `GD` is the
  canonical home for session-persistent per-function state — most importantly the
  `spi_prepare` plan IDs (`set GD(plan) [spi_prepare ...]`). [from-docs]
- **Sharing across functions requires the SAME SQL role.** Interpreters are
  per-role (see `pltcl-overview.md`: `Tcl_CreateSlave` keyed by `user_id`,
  `source/src/pl/tcl/pltcl.c:503-506`), so two `pltcl` functions share ordinary
  Tcl globals only when executed by the same role. For deliberate cross-function
  sharing use regular Tcl globals (not `GD`); to bridge roles, `SECURITY DEFINER`
  with a common owner. [from-docs][verified-by-code @9d1188f29865]
- **`pltclu` (untrusted) uses a single shared interpreter** at superuser trust,
  so all `pltclu` functions see each other's globals with no isolation boundary.
  [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/pltcl-overview.md]] — the per-role safe-slave
  interpreter model this isolation rests on.
- [[knowledge/docs-distilled/pltcl-dbaccess.md]] — `spi_prepare` plan IDs are the
  main thing stashed in `GD`.
- [[knowledge/docs-distilled/plperl-under-the-hood.md]] — Perl's `%_SHARED` is
  the analog (also per-interpreter, hence per-role).
