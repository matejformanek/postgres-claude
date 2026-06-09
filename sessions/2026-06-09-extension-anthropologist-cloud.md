# 2026-06-09 — extension-anthropologist cloud run (4 ideology docs, queue refill)

## What I did
- Found the `progress/_queues/extensions.md` queue empty (drained 2026-06-08).
  Ran the refill rule: `topic:postgresql-extension stars:>500` → 14 hits; 9 not
  yet under `knowledge/ideologies/`. Appended all 9 as `[pending]`.
- Processed the top 4 by anthropology value (divergence from core), looping until
  the ≥70% output-budget floor:
  - `knowledge/ideologies/orioledb.md`
  - `knowledge/ideologies/pgrx.md`
  - `knowledge/ideologies/plv8.md`
  - `knowledge/ideologies/pg_squeeze.md`
- Marked those 4 `[done:placeholder]`; left 5 `[pending]` (pg_auto_failover,
  pgrouting, plpgsql_check, orafce, uuidv47).
- All external source fetched via `raw.githubusercontent.com` + `api.github.com`
  tree listings (curl + GH_TOKEN) — the GitHub MCP is scoped to the meta repo, so
  it served only `search_repositories`, not external file reads.

## What I learned
- **orioledb is the corpus's boundary case.** Every other ideology lives inside a
  pluggable seam; orioledb needed PostgreSQL itself patched. Its `_PG_init`
  installs ~10 hooks that don't exist in core (`src/orioledb.c:1255-1270`:
  `CheckPoint_hook`, `after_checkpoint_cleanup_hook`, `get_xidless_commit_lsn_hook`,
  `snapshot_hook`/`snapshot_register_hook`/`reset_xmin_hook`, …), pins the patched
  server via `.pgtags`, and the build refuses vanilla. That hook list is a literal
  Phase-D wishlist for "make the table-AM seam wide enough for OrioleDB-class engines."
- **pgrx is the substrate under two already-documented extensions.** Its license
  header (`pgrx/src/lib.rs:1-9`) shows it was extracted from zombodb; wrappers is
  also built on it. The crown jewel is `pg_guard_ffi_boundary`
  (`pgrx-pg-sys/src/submodules/ffi.rs:72-179`): a `sigsetjmp` barrier wrapping
  *every* bindgen'd C call to reconcile `ereport`/`longjmp` with Rust unwinding —
  the same problem pg_duckdb (`InvokeCPPFunc`) and plv8 (`PG_TRY`+`js_error`) solve
  pointwise, but universal and bidirectional.
- **plv8 sharpens the A10 trust-gate ranking.** Its sandbox is strongest *because*
  V8 is a pure-compute VM with no host bindings — nothing to mask (Perl) or remove
  (Tcl Safe). One full `v8::Isolate` per database user, cached for backend life
  (`ContextVector`, `plv8.cc:572-577`), is the A10 per-user-interpreter leak at V8
  scale. Caveat: `plv8.v8_flags` is a raw `V8::SetFlagsFromString` passthrough.
- **pg_squeeze vs pg_repack is the cleanest A/B in the set.** Same job (online
  CLUSTER/bloat removal), opposite means: pg_squeeze uses in-process logical
  decoding + bgworkers (pure server) where pg_repack uses triggers + a client.
  Its `swap_relation_files` (`pg_squeeze.c:3131-3185`) is *copied out of core's
  `static` `cluster.c` function* — the recurring "core internals aren't exported"
  tax (also hit by cstore_fdw, pg_repack, hydra-columnar).

## What I'm unsure about
- plv8 `plcoffee`/`plls` dialects: the queued manifest named `coffee-script.cc`,
  but it is absent from the `r3.2` tree (only `plv8.control.common` remains). The
  doc characterizes the plain-JS handler only and marks the dropped dialect
  `[unverified]`.
- pgrx `pgrx-macros` proc-macro internals + `pgrx-sql-entity-graph` topological
  ordering were inferred from re-exports + README, not deep-read.
- Several large `.c`/`.cc`/`.rs` files (orioledb `handler.c` 77 KB / `orioledb.c`
  57 KB, plv8 `plv8.cc` 66 KB, pg_squeeze `pg_squeeze.c` 103 KB) were read only in
  their cited regions; remainder skimmed. Cites are anchored, but broader claims
  carry `[from-README]`/`[inferred]` tags.

## Pointers left for next time
- 5 `[pending]` refill candidates remain: pg_auto_failover (HA monitor/keeper
  bgworker), pgrouting (C++ graph routing on postgis), plpgsql_check (plpgsql
  static analyzer / compile hooks), orafce (Oracle-compat shim), uuidv47 (small
  header-only uuid type). pg_auto_failover + plpgsql_check are the higher-signal two.
- Phase-D corpus deliverables surfaced by this run: (a) a survey of core `static`
  functions copied-out by extensions (orioledb, pg_squeeze `swap_relation_files`,
  cstore_fdw, pg_repack, hydra-columnar); (b) a `knowledge/idioms` note on logical
  decoding as a *transient intra-backend change-capture API* (pg_squeeze) vs a
  replication transport; (c) the orioledb patchset-hook list as a concrete
  "pluggable-storage seam gaps" enumeration.
