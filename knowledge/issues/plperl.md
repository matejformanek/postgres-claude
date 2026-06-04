# Issues — `pl/perl` (src/pl/plperl/)

Per-subsystem issue register for the **PL/Perl procedural language**
— BOTH the trusted variant (`plperl`) and the untrusted variant
(`plperlu`), implemented in a single source file (`plperl.c`)
dispatched via `pg_language.lanpltrusted` and `select_perl_context`.

**Parent docs:** `knowledge/files/src/pl/plperl/*` (3 docs covering 3
source files: `plperl.c.md`, `plperl.h.md`, `plperl_system.h.md`;
`ppport.h` SKIPPED as vendored Perl `Devel::PPPort` boilerplate, NOT
PostgreSQL code).

**Source:** 16 entries surfaced 2026-06-04 by the A10 foreground sweep
(agent A10-1). Mirrored in the per-file doc's `## Issues spotted` block.

This sweep documents PL/Perl as the COMPARISON CASE to A9's plpgsql
baseline — the language with a real sandbox (opcode-mask, NOT Safe.pm
despite docs hand-wave) for its trusted variant, and a separate
untrusted variant gated by superuser.

## The headlines (vs A9 plpgsql baseline)

1. **PL/Perl uses an opcode mask + a hijacked `require`/`do FILE`
   opcode — NOT Safe.pm.** The actual sandbox is
   `PL_op_mask = plperl_opmask` (`plperl.c:1005`), where
   `plperl_opmask` is generated at build time by `plperl_opmask.pl`
   from Perl's `Opcode.pm`. Pattern:
   `:default :base_math !:base_io sort time require entereval caller
   dofile print prtf !dbmopen !setpgrp !setpriority !custom`. Plus
   `pp_require_safe` to block dynamic loading. Plus DynaLoader stash
   nuking. **`grep Safe plperl.c` = 0 matches.** The PG documentation
   describes the gate as "Safe-like" but the source uses a different
   mechanism entirely. Worth documenting because Safe.pm has a known
   CVE history (CVE-2014-4330, CVE-2016-1238) that does NOT apply to
   plperl — and any opcode added to Perl that escapes the mask DOES
   apply. **Plpgsql has nothing of this kind because it has no I/O
   constructs to gate in the first place.**

2. **Trusted and untrusted run through the same source file and even
   the same handler entry points.** `plperlu_call_handler` is a
   one-line wrapper that calls `plperl_call_handler`
   (`plperl.c:2076`). The trust posture is re-derived from
   `pg_language.lanpltrusted` at compile time inside
   `compile_plperl_function` (`plperl.c:2840`), and the actual
   dispatch happens in `select_perl_context(prodesc->lanpltrusted)`
   (`plperl.c:2946`). The interpreter cache hashtable is keyed by
   `(proc_id, is_trigger, user_id)` with `user_id = 0` for plperlu
   — plperlu functions are shared across users, plperl functions are
   per-user.

3. **One Perl interpreter per `(trusted? user_id : 0)` for the whole
   backend lifetime, never evicted.** plperl keeps interpreters for
   the lifetime of the process (`plperl.c:70`). Long-lived backends
   (connection-pooled with `SET ROLE`) accumulate one Perl
   interpreter per distinct UID with no eviction — invisible to PG's
   memory accounting. Combined with `plperl.on_init` running once in
   the postmaster (when preloaded) being inherited by every fork:
   plperl has a substantially different threat model than plpgsql —
   postmaster-side untrusted Perl code can persist across the entire
   instance.

4. **Validator surface is nearly identical to plpgsql** —
   `CheckFunctionValidatorAccess`, pseudotype-result/arg checks, body
   compilation gated by `check_function_bodies` (`plperl.c:1995-2060`).
   The same `check_function_bodies=off` audit gap exists. But the
   validator does NOT pre-check Perl source for unsafe opcodes —
   that check happens at first-call compile time inside the locked-
   down interpreter. So a function whose body uses banned ops will
   succeed validation and fail at first call. (Compare: plpgsql's
   validator skips body compilation entirely under
   `check_function_bodies=off`; plperl's validator is broadly
   stronger but the opcode-mask check is deferred.)

## Cross-sweep references

- **Cross-PL trust-gate ranking** (A9 + A10 combined): plpgsql
  (nothing — language has no I/O) vs plperl (opcode-mask, drift-
  prone) vs plpython (untrusted-only by design) vs pltcl (Tcl Safe
  slave-interp, structurally strongest). Single corpus-wide
  comparison doc proposed at `knowledge/idioms/pl-trust-gates.md`.
- **Per-user interpreter cache** is unique to plperl among the four
  PLs; plpython has one interpreter per backend regardless of UID;
  plpgsql has no per-user state; pltcl has one master interp + one
  safe slave interp per backend.
- **postmaster-inherited PL state**: `plperl.on_init` is the only
  case in the four PLs where untrusted code can be made to run at
  postmaster start time (via `shared_preload_libraries=plperl`).
  Comment in `plperl.c:417-429` acknowledges this is "not really
  right either way."

---

## Entries

### plperl.c (4254 LOC)

- [ISSUE-defense-in-depth: `pp_require_safe` accepts any non-undef
  `%INC` value as "loaded" (maybe)] —
  `source/src/pl/plperl/plperl.c:900-901` — trusted user could spoof
  `$INC{Foo}=1` to bypass the DIE branch; downstream opmask still
  applies, so exploit is narrow but the check should validate the
  `%INC` value too.
- [ISSUE-defense-in-depth: `on_init` postmaster fork-inheritance is
  acknowledged but not loudly warned (maybe)] —
  `source/src/pl/plperl/plperl.c:417-429` —
  `shared_preload_libraries=plperl` runs on_init Perl code in the
  postmaster; every fork inherits side effects; comment itself says
  "isn't really right either way".
- [ISSUE-defense-in-depth: `WarnEnv` %ENV protection is informational;
  trusted code can `untie %ENV` (maybe)] —
  `source/src/pl/plperl/plc_trusted.pl:35-56` — the tie warns but
  doesn't block, and the plc_trusted.pl comment explicitly says the
  user can untie it.
- [ISSUE-memory: no per-UID interpreter eviction in long-lived
  backends (maybe)] —
  `source/src/pl/plperl/plperl.c:60-91, 540-548` — connection-pooler-
  style backends with many `SET ROLE` users accumulate one Perl
  interpreter per user with zero eviction.
- [ISSUE-correctness: embedded-NUL handling in
  `sv2cstr → InputFunctionCall` truncates ambiguously (maybe)] —
  `source/src/pl/plperl/plperl.c:1432-1444` — `sv2cstr` retains Perl
  byte-length but result handed to typinput as a NUL-terminated
  cstring; behaviour depends on typinput.
- [ISSUE-audit-gap: `check_function_bodies=off` bypasses plperlu
  validator's body compilation (nit)] —
  `source/src/pl/plperl/plperl.c:2053-2056` — same gap as plpgsql but
  more interesting on plperlu given XS access.
- [ISSUE-error-handling: 4 occurrences of "XXX need to find a way to
  determine a better errcode here" all using
  ERRCODE_EXTERNAL_ROUTINE_EXCEPTION (nit)] —
  `source/src/pl/plperl/plperl.c:1029, 1056, 2263, 2331` — long-
  standing XXX; collapses every Perl-side error to one SQLSTATE.
- [ISSUE-documentation: opcode mask justification lives only in
  `plperl_opmask.pl`, not referenced from plperl.c lockdown code
  (nit)] — `source/src/pl/plperl/plperl.c:1001-1005` —
  `PL_op_mask = plperl_opmask` is one line; the actual policy is in
  a separate `.pl` generator script.

### plperl.h (206 LOC)

- [ISSUE-correctness: `sv2cstr` returns a cstring whose length the
  comment claims is preserved for "embedded null byte to ensure we
  error out properly", but the result is then used as
  NUL-terminated by all callers (maybe)] —
  `source/src/pl/plperl/plperl.h:130-140` — comment vs. callsite
  reality mismatch.
- [ISSUE-correctness: `cstr2sv` uses `newSVpv(utf8_str, 0)` which
  strlens; a PG cstring with an embedded NUL silently truncates on
  the Perl side (nit)] —
  `source/src/pl/plperl/plperl.h:155-159` — text types can't carry
  NULs anyway; theoretical hazard.
- [ISSUE-defense-in-depth: `static inline` shape — each `.xs` TU
  inlines its own copy of `sv2cstr`/`cstr2sv`/`croak_cstr`; if Perl
  macro definitions diverge between TUs, subtle behaviour drift can
  happen (nit)] — `source/src/pl/plperl/plperl.h:50-204`.
- [ISSUE-documentation: SQL_ASCII byte-soup mode is a cross-cutting
  invariant only documented inline in `sv2cstr` and `cstr2sv` comments
  (nit)] — `source/src/pl/plperl/plperl.h:120-126, 153-155`.

### plperl_system.h (197 LOC)

- [ISSUE-defense-in-depth: Win32 XSUB.h block unconditionally
  `#undef`s 18 libc/socket macros with no push/pop_macro, silently
  rerouting socket/open/stat/etc. to Perl's versions in `.xs` TUs
  (nit)] — `source/src/pl/plperl/plperl_system.h:97-117`.
- [ISSUE-api-shape: `AV_SIZE_MAX` differs (`SSize_t_MAX` vs
  `I32_MAX`) between Perl ≥5.19.4 and older; the Perl-version-
  dependent cap surfaces as a `program_limit_exceeded` to users
  without warning (nit)] —
  `source/src/pl/plperl/plperl_system.h:190-195`.
- [ISSUE-documentation: `#pragma GCC system_header` suppresses
  warnings for the *entire* file including PG's own fallback macros
  like the triple-ternary `HeUTF8` (nit)] —
  `source/src/pl/plperl/plperl_system.h:26-28, 179-183`.
- [ISSUE-defense-in-depth: `__builtin_expect(expr, val) → (expr)`
  under MSVC+Strawberry-Perl drops branch hints throughout Perl
  (perf-only, but worth noting in Phase D) (nit)] —
  `source/src/pl/plperl/plperl_system.h:70-72`.
