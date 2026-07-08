---
source_url: https://www.postgresql.org/docs/current/plperl-under-the-hood.html
fetched_at: 2026-07-07T20:50:00Z
anchor_sha: 9d1188f29865
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# PL/Perl under the hood (§45.8) — trusted interpreter, %_SHARED, on_init GUCs

The load-bearing internals leaf of the PL/Perl chapter: the trusted (`plperl`)
vs untrusted (`plperlu`) split, how the trusted interpreter is sandboxed via a
Perl **opcode mask** (not Safe.pm directly), the per-role interpreter model, and
the three `on_init` GUCs and their load timing. Complements the §43 PL/pgSQL
family with "the other reference PL." Maps to `plhandler` + `fmgr-and-spi` +
`extension-development` skills.

## Non-obvious claims

- **Trusted vs untrusted are two languages backed by two interpreter flavors.**
  `plperl` is trusted (unprivileged users may create functions); `plperlu` is
  untrusted (superuser-only, full unrestricted Perl including `open`/`system`).
  [from-docs]
- **The trusted sandbox is a Perl opcode mask, applied at interpreter setup, not
  Safe.pm wrapping each call.** The handler saves the default opmask
  (`PLPERL_SET_OPMASK(plperl_opmask)` at `source/src/pl/plperl/plperl.c:483`,
  mask array `plperl_opmask[MAXO]` at `plperl.c:241`, generated header
  `#include "plperl_opmask.h"` at `plperl.c:50`) and, for the trusted case,
  redirects the `require`/`dofile` opcodes to a safe stub
  (`PL_ppaddr[OP_REQUIRE] = pp_require_safe` / `OP_DOFILE` at
  `plperl.c:499-500`), so a trusted function cannot pull in arbitrary modules or
  read files. `plperl_trusted_init()` (`plperl.c:285`) is where trusted
  lock-down happens. [verified-by-code @9d1188f29865]
- **One interpreter per (language, SQL role) per session.** A fresh Perl
  interpreter is created when a different language is called, or when a new SQL
  role first invokes a PL/Perl function; interpreters are kept in a Postgres hash
  table (`plperl_interp_desc`, `plperl.c:86`, comment at `plperl.c:68`). Extra
  interpreters created later in the same session must **re-run `plperl.on_init`.**
  [from-docs][verified-by-code @9d1188f29865]
- **`%_SHARED` is the cross-call scratchpad**, session-persistent within one
  interpreter; the canonical use is caching `spi_prepare` plan handles across
  invocations. It is NOT shared across roles (different interpreters). [from-docs]
- **`plperl.on_init`** (string) runs when the Perl interpreter first
  initializes, *before* it specializes into trusted/untrusted — **SPI is
  unavailable at this stage.** If `plperl` is in `shared_preload_libraries` it
  runs once in the postmaster (so the code becomes available to all `plperl`
  functions — a security consideration). It is `PGC_SIGHUP` (`plperl.c:418`), set
  only in `postgresql.conf` / command line. Longer setup loads a module:
  `plperl.on_init = 'require "plperlinit.pl"'`. [from-docs][verified-by-code @9d1188f29865]
- **`plperl.on_plperl_init` / `plperl.on_plperlu_init`** run right after
  specialization into the trusted / untrusted flavor (SPI still unavailable);
  superuser-only, because trusted-init code runs after the interpreter is locked
  down. [from-docs]
- **`plperl.use_strict`** enables the `strict` pragma for *subsequently* compiled
  functions only — already-compiled functions in the session are unaffected.
  [from-docs]
- **Session cleanup is Perl-shaped, not backend-shaped.** `END` blocks run on
  normal session exit, but file handles are **not** auto-flushed and objects are
  **not** auto-destroyed. Windows gets no preload savings (postmaster interpreter
  doesn't propagate to forked children). [from-docs]
- **Known limits with internals bite:** PL/Perl functions cannot call each other
  directly; `spi_exec_query` materializes the whole result in memory; a
  `return`-based SRF accumulates all rows in memory (use `return_next` to stream).
  [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/plhandler.md]] — the C-level PL handler contract
  this specializes.
- [[knowledge/docs-distilled/plperl-builtins.md]] — the `spi_*` / `%_SHARED`
  surface referenced above.
- [[knowledge/docs-distilled/plpgsql-implementation.md]] — sibling "under the
  hood" leaf for the reference PL; contrast PARAM-substitution vs Perl-string.
- [[knowledge/idioms/fmgr.md]] / `fmgr-and-spi` skill — how a PL function is
  entered from the executor.
