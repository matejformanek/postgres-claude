---
path: src/pl/plperl/plperl.c
anchor_sha: 419ce13b7019f906ebc010af3be09a9deffc2a47
loc: 4254
---

# plperl.c

- **Source path:** `source/src/pl/plperl/plperl.c`
- **Last verified commit:** `419ce13b7019` (re-anchored 2026-06-28 by
  pg-quality-auditor AUDIT mode after anchor-bump
  `f0a4f280b4d3..419ce13b7019`. Triggering commit `4015abe14bb0`
  ("plperl: Fix NULL pointer dereference for forged array object") is
  **line-neutral** — LOC unchanged 4254 — and localized to
  `get_perl_array_ref` (:1144); see the array-conversion note below.
  Sampled ~12 function cites across the file: most are exact
  (`plperl_sv_to_datum` :1329, `plperl_hash_from_tuple` :3030,
  `plperl_trigger_build_args` :1637) or ±1–3 (`_PG_init` :385,
  `plperl_call_handler` :1860, `plperl_inline_handler` :1902); the one
  genuinely-stale cite (`plperl_init_interp` "606-650") is corrected
  below. A full per-cite re-pin of this ~80-cite doc was NOT done — the
  sampled set is within tolerance; flag for a dedicated re-pin pass only
  if a future sample shows wider drift. Prior pin `4b0bf0788b0`.)
- **LOC:** 4254

## One-line summary

The entire PL/Perl procedural-language backend in one file: it
implements BOTH `plperl` (trusted) and `plperlu` (untrusted) via the
same six handler entry points, with the trust decision driven from
`pg_language.lanpltrusted` at function-compile time and enforced
inside the embedded Perl interpreter through an opcode mask plus a
hijacked `require`/`do FILE` opcode (NOT Safe.pm).
[verified-by-code, plperl.c:1-6, 2068-2094, 962-1036]

## Role in PG

`CREATE LANGUAGE plperl` and `plperlu` register handlers
`plperl_call_handler`, `plperl_inline_handler`, `plperl_validator`
(and the trivial `plperlu_*` aliases at plperl.c:2074-2094).
`fmgr` dispatches normal SQL function calls into
`plperl_call_handler`; `EXECUTE DO ... LANGUAGE plperl[u]` into
`plperl_inline_handler`; `CREATE FUNCTION` validation (when
`check_function_bodies = on`) into `plperl_validator`.

A backend hosts at most one Perl interpreter per `(trusted? user_id :
0)` key, kept alive in `plperl_interp_hash` for the whole process
lifetime (plperl.c:226, 86-91, 60-70). Build-time `MULTIPLICITY` is
required to support more than one interpreter per backend;
otherwise the second `select_perl_context` call raises
`ERRCODE_FEATURE_NOT_SUPPORTED` (plperl.c:646-648).

## Public API / entry points

SQL-visible handlers (declared with `PG_FUNCTION_INFO_V1`):

- `plperl_call_handler(PG_FUNCTION_ARGS)` (plperl.c:1857-1894) —
  dispatches into `plperl_trigger_handler`,
  `plperl_event_trigger_handler`, or `plperl_func_handler` based on
  `CALLED_AS_TRIGGER`/`CALLED_AS_EVENT_TRIGGER`. Saves &
  restores `current_call_data` and `plperl_active_interp` via
  `PG_TRY`/`PG_FINALLY` and decrements the prodesc refcount.
  [verified-by-code]
- `plperl_inline_handler(PG_FUNCTION_ARGS)` (plperl.c:1899-1986) —
  DO-block entry; sets up a fake `FmgrInfo`/`plperl_proc_desc`,
  honours `codeblock->atomic` via `SPI_connect_ext(SPI_OPT_NONATOMIC)`
  for non-atomic blocks (plperl.c:1958). The dispatch
  `select_perl_context(desc.lanpltrusted)` is what makes
  `DO LANGUAGE plperl` vs `DO LANGUAGE plperlu` select different
  interpreters.
- `plperl_validator(PG_FUNCTION_ARGS)` (plperl.c:1995-2060) — checks
  `CheckFunctionValidatorAccess`, disallows pseudo-type result types
  other than TRIGGER/EVENT_TRIGGER/RECORD/VOID, disallows pseudo-type
  args other than RECORD; calls `compile_plperl_function` only when
  `check_function_bodies` is on.
- `plperlu_call_handler / plperlu_inline_handler / plperlu_validator`
  (plperl.c:2071-2094) — bare wrappers that forward to the plperl
  versions. The trust posture is then re-derived from
  `pg_language.lanpltrusted` inside `compile_plperl_function`
  (plperl.c:2840).
- `_PG_init(void)` (plperl.c:384-491) — registers the four GUCs,
  reserves the `plperl.*` prefix (plperl.c:461,
  `MarkGUCPrefixReserved`), creates the two hash tables, snapshots the
  default opcode mask via `PLPERL_SET_OPMASK(plperl_opmask)`
  (plperl.c:483), and starts the **held interpreter** by calling
  `plperl_init_interp` *before* knowing whether the first function
  will be trusted or untrusted.

C-callable bridge for the `.xs` files (declared in plperl.h):

- `plperl_spi_exec`, `plperl_spi_query`, `plperl_spi_fetchrow`,
  `plperl_spi_prepare`, `plperl_spi_exec_prepared`,
  `plperl_spi_query_prepared`, `plperl_spi_freeplan`,
  `plperl_spi_cursor_close`, `plperl_spi_commit`,
  `plperl_spi_rollback`, `plperl_return_next`,
  `plperl_sv_to_literal`, `plperl_util_elog`
  (definitions plperl.c:3140-4047, 3252, 4061-4093).

## Key invariants

- INV-1: One backend → one interpreter per `(trusted? user_id : 0)`
  key. Untrusted variant always uses `user_id = InvalidOid` (= 0),
  trusted variant uses `GetUserId()`. Interpreters are never destroyed
  during normal backend life — only at `plperl_fini`/`on_proc_exit`.
  [verified-by-code, plperl.c:65-70, 567-569, 540-548]
- INV-2: `plperl_active_interp` always reflects the Perl-level
  `PERL_SET_CONTEXT`. `activate_interpreter` is the only function
  that may change it (plperl.c:688-699). Handlers save
  `oldinterp` and restore it in `PG_FINALLY`
  (plperl.c:1864-1890, 1909-1981).
- INV-3: The opcode mask is set at interpreter construction with
  `PL_op_mask = plperl_opmask` (plperl.c:1005). Once set, it cannot be
  cleared from Perl code — `PL_op_mask` is per-interpreter and the
  pp_eval opcode is still allowed but is checked against the same
  mask. [from-comment, plperl.c:1001-1005]
- INV-4: For *trusted* interpreters, `OP_REQUIRE` and `OP_DOFILE` are
  redirected to `pp_require_safe`, which only returns YES if the file
  is already in `%INC` and otherwise DIEs (plperl.c:498-499,
  884-914). The original opcode handler is saved in `pp_require_orig`
  the first time any interpreter is built (plperl.c:831-837).
- INV-5: `fn_refcount` on `plperl_proc_desc` is incremented on every
  active call frame *and* by the hashtable entry. The macro
  `decrement_prodesc_refcount` triggers `free_plperl_function` (and
  `MemoryContextDelete(prodesc->fn_cxt)`) when the count hits zero
  (plperl.c:130-137, 2703-2718).
- INV-6: `validate_plperl_function` invalidates a cached prodesc when
  `fn_xmin` or `fn_tid` of the `pg_proc` tuple has changed — this is
  how `CREATE OR REPLACE FUNCTION` (which keeps the same OID)
  invalidates the cached compiled Perl sub (plperl.c:2687-2700).
- INV-7: `plperl_ending` (set in `plperl_fini`) gates SPI usage so
  that END blocks running during process exit can't reach the SPI
  bridge (plperl.c:527, 3113-3120).

## Notable internals

### Held interpreter, on_init, on_plperl_init, on_plperlu_init

`_PG_init` immediately calls `plperl_init_interp()`
(plperl.c:488). This pre-builds a Perl interpreter and runs
`plperl.on_init` *before* the trust decision is known
(plperl.c:765-773). The first function call adopts that held
interpreter and finishes initializing it as either trusted
(`plperl_trusted_init`, plperl.c:962-1036) or untrusted
(`plperl_untrusted_init`, plperl.c:1042-1059); subsequent
interpreters in the same backend are built fresh via
`plperl_init_interp` (plperl.c:710; the trust/MULTIPLICITY dispatch
that calls it lives in `select_perl_context` :558, whose
non-MULTIPLICITY reject is at :627-648). This means:

- `plperl.on_init` always runs in a *not-yet-locked* interpreter.
  It can use arbitrary Perl features, load XS modules, etc. (which is
  the point — preloading expensive modules.) It cannot be set at
  session time: it is `PGC_SIGHUP` and can be set in
  `postgresql.conf` or via `ALTER SYSTEM` (plperl.c:428).
- `plperl.on_plperl_init` runs *after* the lockdown
  (`plperl_trusted_init` → opcode mask + safe require + DynaLoader
  nuking → then `eval_pv(plperl_on_plperl_init, FALSE)`,
  plperl.c:993-1035). It is `PGC_SUSET` — must be superuser
  (plperl.c:432-451).
- `plperl.on_plperlu_init` runs in an untrusted (unlocked)
  interpreter (plperl.c:1050-1058). Also `PGC_SUSET`.

### Trust lockdown — `plperl_trusted_init`

Performed exactly once per trusted interpreter on first use
(plperl.c:962-1036):

1. Temporarily restore the original `require`/`dofile` (so the trusted
   init can `require strict`, `Carp`, etc.; see `plc_trusted.pl`).
2. `eval_pv(PLC_TRUSTED, FALSE)` — runs the embedded
   `plc_trusted.pl` which: (a) does `require strict; Carp;
   Carp::Heavy; warnings; feature`; (b) reaches into `%main::ENV`
   and replaces it with a plain-hash tied to `WarnEnv` so writes to
   `$ENV{...}` are silently noisy no-ops.
   [verified-by-code, plc_trusted.pl:28-56]
3. Force-load Perl's utf8 module by evaluating `chr(0x100) =~ /\xa9/i`
   (plperl.c:986) — works around perl bug rt.perl 47576 where later
   regex paths would try to `require utf8_heavy.pl` and fail.
4. Switch `OP_REQUIRE`/`OP_DOFILE` to `pp_require_safe`
   (plperl.c:998-999).
5. Install the opmask: `PL_op_mask = plperl_opmask` (plperl.c:1005).
6. Walk the `DynaLoader::` stash and `SvREFCNT_dec` every CV
   (function) in it, then `hv_clear(stash)` — so even reaching
   `DynaLoader::dl_load_file` via fully qualified name yields undef
   (plperl.c:1007-1021).
7. Bump `PL_sub_generation` and clear `PL_stashcache` so method-cache
   results don't survive the DynaLoader nuke (plperl.c:1020-1021).
8. Run `plperl.on_plperl_init` (plperl.c:1026-1035).

### The opcode mask (`plperl_opmask.h`, regenerated by `plperl_opmask.pl`)

The mask is built by the Opcode.pm `opset` mechanism. Allowed set
(plperl_opmask.pl:23-48): `:default :base_math !:base_io sort time
require entereval caller dofile print prtf` and disabled
`!dbmopen !setpgrp !setpriority !custom`. Notably allowed:
`entereval` (so string `eval` works at runtime — the comment justifies
this by "the opmask is now permanently set", plperl_opmask.pl:30) and
`caller`. Notably blocked by default through `!:base_io`: open,
close, sysopen, fileno, read/sysread, write/syswrite,
unlink/rename/link/chmod/chown, socket/bind/connect/accept,
fork/exec/system/pipe, kill, getpid, etc. — i.e. all
file/network/process IO.

`print` and `prtf` are explicitly allowed because the only writable
filehandles available are STDOUT/STDERR (plperl_opmask.pl:35-37). The
script's comment is the only documentation of this — there is no
runtime mediation that STDOUT/STDERR remain "safe", and
`$SIG{__WARN__}` is bound to ereport WARNING via `plperl_warn` in
`plc_perlboot.pl:63-70`.

### Untrusted "init" is almost nothing

`plperl_untrusted_init` (plperl.c:1042-1059) just runs
`plperl.on_plperlu_init`. The opcode mask is NOT installed; `require`
remains the real Perl one; DynaLoader is NOT cleared; full XS / file /
network IO is available. This is the documented design: `plperlu` is
"unrestricted server-side scripting language" with `pg_language.lanpltrusted = false`,
restricted to superuser via the `pg_language` ACL.

### `plperl_call_handler` — call-frame discipline

The handler is wrapped in `PG_TRY()` / `PG_FINALLY()` to guarantee:
(a) `current_call_data` is restored to the caller's value (essential
because PL/Perl can call SQL → which can call PL/Perl recursively);
(b) `plperl_active_interp` is restored via `activate_interpreter` so a
SECURITY-DEFINER plperl-as-userA→plperl-as-userB→plperl-as-userA chain
ends up in userA's interpreter; (c) `decrement_prodesc_refcount` runs
even on errors (plperl.c:1888-1890).

### `plperl_inline_handler` — fake-fcinfo discipline

DO blocks have no `pg_proc` row, so the handler stack-allocates a
`plperl_proc_desc` with `fn_oid = InvalidOid`, picks the trust posture
from `codeblock->langIsTrusted` (plperl.c:1939), and arranges to
`SvREFCNT_dec` the compiled Perl sub in `PG_FINALLY`
(plperl.c:1976-1977). The fake desc is *not* refcounted
(plperl.c:1950 comment).

### `compile_plperl_function` — caching and re-entry

The hash key is `(proc_id, is_trigger, user_id)` with `user_id = 0`
for plperlu. The lookup tries the current user's slot first, then
falls back to `user_id = InvalidOid` for plperlu (plperl.c:2744-2766).
This means: if user A and user B both call the same plperlu function,
they reuse the same compiled sub (single global interpreter); if both
call the same plperl function, each has its own compiled sub in its
own interpreter.

On compile, `prodesc->fn_cxt` is an `AllocSetContext` under
`TopMemoryContext` (plperl.c:2797-2799). All FmgrInfos and the
`reference` SV live in or under it. `select_perl_context(prodesc->lanpltrusted)`
(plperl.c:2946) does the actual trust dispatch — this is the single
place where the trust decision becomes effective for caching.

`PG_CATCH` on compile failure: if the Perl sub `reference` was
created, `free_plperl_function` runs; otherwise the
`AllocSetContext` is deleted directly (plperl.c:2980-2989).

### SPI bridge — all variants use sub-transactions

Every `plperl_spi_exec` / `plperl_spi_query` / `*_prepared`
path runs inside `BeginInternalSubTransaction` (e.g.
plperl.c:3153-3196) so a Perl-level `eval { spi_exec("BAD SQL") }` can
catch the error without aborting the outer SPI frame. PG-side
`PG_CATCH` calls `croak_cstr(edata->message)`, which raises a Perl
exception. The pattern is hand-rolled in every SPI entry point — the
function-call body, query, fetchrow, prepare, exec_prepared,
query_prepared, freeplan, commit, rollback variants all follow it.

`SPI_execute` and `SPI_execute_plan` are called with
`current_call_data->prodesc->fn_readonly` (the prodesc-cached
"VOLATILE / STABLE / IMMUTABLE" derived from `provolatile`) as the
read_only flag (plperl.c:3163, 3809). `SPI_prepare(query, 0, NULL)` is
used for the unparameterized `plperl_spi_query` and `spi_exec` paths —
**no parameter binding** — meaning the function body must do its own
quoting. The
docs (`plperl_sv_to_literal`, plperl.c:1450-1478) provide
`encode_typed_literal` for callers to quote, and `mkfunc` evaluates
the function body with `no strict; no warnings` by default
(plc_perlboot.pl:92-101).

### Type conversion — SV ↔ Datum

`plperl_sv_to_datum` (plperl.c:1329-1446) recursively handles:
undef/VOIDOID → NULL via typinput on NULL; transform_tosql
(`pg_transform`) override; arrayref → `plperl_array_to_datum`;
hashref → tuple (composite or domain over composite, with
`domain_check`); scalar → `InputFunctionCall(typinput, sv2cstr(sv))`.
`check_stack_depth()` guards recursion. The text path goes through
`sv2cstr` (plperl.h:88-140) which forces UTF-8 conversion via
`SvPVutf8` and then `pg_any_to_server` (`utf_u2e`). Embedded NULs are
preserved through `len` and rejected by typinput functions that don't
expect them.

**Forged-array hardening** (`get_perl_array_ref`, plperl.c:1144): the
helper that decides whether an SV is array-like — used by
`array_to_datum_internal` (:1191), `plperl_sv_to_datum` (:1364) and the
return path (:2473) — special-cases a `PostgreSQL::InServer::ARRAY`
blessed object by fetching its `array` hash slot. `4015abe14bb0`
("Fix NULL pointer dereference for forged array object") added the guard
`if (sav && *sav && SvOK(*sav) && SvROK(*sav) && SvTYPE(SvRV(*sav)) ==
SVt_PVAV)` before returning `*sav`, with an explicit `elog(ERROR, "could
not get array reference from PostgreSQL::InServer::ARRAY object")`
fallback. Previously a hand-forged object whose `array` slot was missing
or non-array would be dereferenced unchecked, crashing the backend.
[verified-by-code, plperl.c:1144-1164]

`plperl_hash_from_tuple` (plperl.c:3030-3109) skips dropped attributes
and (unless include_generated) generated columns; uses
`OidOutputFunctionCall(typoutput, attr)` for scalars, recurses for
rowtype, builds `PostgreSQL::InServer::ARRAY` blessed refs for arrays.

### Trigger context — what flows to Perl

`plperl_trigger_build_args` (plperl.c:1637-1745) puts these UTF-8
SVs into the `%_TD` hash visible to the function: `name` (trigger
name), `relid` (OID), `event`, `argc`, `args` (raw tgargs), `relname`
(legacy, both `relname` and `table_name` are set to the same value
plperl.c:1717-1722), `table_name`, `table_schema`, `when`, `level`,
`old`, `new`. The values of `tdata->tg_trigger->tgargs` (which are
strings copied from `pg_trigger.tgargs` and are inert) flow in
unescaped.

For event triggers (plperl.c:1749-1764), only `event` and `tag` (via
`GetCommandTagName`) reach Perl.

### `pp_require_safe` and `dofile` lock-down

The pp opcode (plperl.c:884-914): pops the filename SV, looks it up in
`%INC` (GvHVn(PL_incgv)). If already loaded (`*svp != PL_sv_undef`),
returns true. Otherwise `DIE("Unable to load %s into plperl", name)`.
This means a trusted function can `use Module` only if `Module.pm`
has *already* been loaded into this interpreter via `plperl.on_init`
or `plperl.on_plperl_init`. There is no whitelist mechanism per se —
preloading is the gating mechanism.

### `perl_destruct` not used — END blocks only

`plperl_destroy_interp` (plperl.c:922-956) explicitly does NOT call
`perl_destruct`. Comment: "we'd need to audit its actions very
carefully". Instead only END blocks are run (via `call_list(PL_endav,
…)`). On `plperl_fini` (proc-exit), END blocks have access to a
mostly-intact interpreter but `plperl_ending = true` denies SPI
(plperl.c:527, 3113-3120). [from-comment, plperl.c:931-936]

## Trusted vs untrusted boundary

**The single source file dispatches as follows:**

1. `CREATE LANGUAGE plperl` vs `plperlu` → SQL-level
   `pg_language.lanpltrusted` is set true vs false. ACL on the
   `pg_language` row (only superuser may `GRANT USAGE ON LANGUAGE
   plperlu`) is the OUTER gate.
2. `fmgr` dispatches into `plperl_call_handler` *or*
   `plperlu_call_handler` — but both wrappers immediately call the
   *same* `plperl_call_handler` (plperl.c:2076).
3. `compile_plperl_function` reads
   `pg_language.lanpltrusted` and stores it in `prodesc->lanpltrusted`
   (plperl.c:2840). This is the **canonical trust bit for the rest of
   the call**.
4. `select_perl_context(prodesc->lanpltrusted)` (plperl.c:2946) picks
   the interpreter for `user_id = GetUserId()` (trusted) or
   `InvalidOid` (untrusted), creating it via `plperl_trusted_init`
   or `plperl_untrusted_init` if first use.

**What `plperl_trusted_init` actually blocks** (vs Safe.pm, which is
NOT used):

| What                          | How                                        |
|-------------------------------|--------------------------------------------|
| File I/O (open, read, write, sysopen, unlink, rename, chmod, chown, link, symlink, mkdir, rmdir, stat, lstat) | `!:base_io` in opmask (plperl_opmask.pl:26) |
| Network (socket, bind, connect, accept, send, recv) | `!:base_io` in opmask |
| Process (fork, exec, system, pipe, kill, wait, getpid) | `!:base_io` in opmask |
| `require Foo`, `use Foo`, `do "file"` | `pp_require_safe` overrides the opcode (plperl.c:498-499, 884-914) |
| `DynaLoader::*` | All CVs in the stash freed and stash cleared (plperl.c:1007-1017) |
| `dbmopen`, `setpgrp`, `setpriority`, `custom` | Explicit `!` in plperl_opmask.pl:41-48 |
| `%ENV` writes | Tied to `PostgreSQL::InServer::WarnEnv` — warn but no-op, perl-side (plc_trusted.pl:35-56) |

**What's allowed:** `:default` minus `:base_io` plus `sort time
require entereval caller dofile print prtf`. This means:
all arithmetic, regex, string ops, hash & array, `sort`, `time`,
`localtime`, `eval` (both BLOCK and STRING — `entereval`),
`caller` (for stack inspection), `print` and `printf` (writable to
STDOUT/STDERR only). [verified-by-code, plperl_opmask.pl:23-48]

**Cannot the function reach untrusted via the trusted handler?** Two
plausible attacks, both addressed:

- *Reach into a coexisting `plperlu` interpreter via Perl-level
  globals.* `MULTIPLICITY` builds give each interpreter its own
  `PERL_NO_GET_CONTEXT` view; `PERL_SET_CONTEXT` is required to even
  look at the other's symbol table. Trusted code does not have
  arbitrary symbol-table access across interpreters because each call
  to `select_perl_context` switches via `PERL_SET_CONTEXT` (plperl.c:694).
  Non-MULTIPLICITY builds *cannot* coexist trusted + untrusted in one
  backend (plperl.c:646-648). [inferred from MULTIPLICITY semantics
  in perlembed]
- *Bypass `pp_require_safe` by setting `%INC` to point at an attacker
  file before calling `require`.* `pp_require_safe` checks `%INC`
  by *key*, but it does not verify the value. A trusted function that
  can pre-poke `%INC` to mark `Foo` as loaded **could then `use Foo`
  successfully** — but the modules it then sees would still be
  interpreted by the opcode-masked interpreter, so attempting to
  define a sub that uses a banned op would fail at compile time.
  [ISSUE-defense-in-depth: pp_require_safe accepts any non-undef
  %INC value as "loaded", so a trusted function could spoof %INC{Foo}
  to bypass the would-DIE branch (maybe)] — `source/src/pl/plperl/plperl.c:900-901`
  the check is `*svp != &PL_sv_undef`, no value validation. Even if
  bypassed, the loaded module is still subject to the opmask, so this
  is exploitable only against a module that's already been compiled
  in the held interp and is being concealed for a later `use`.

**GUC trust posture summary:**

| GUC                          | Default | Class      | Risk if user-set    |
|------------------------------|---------|------------|---------------------|
| `plperl.use_strict`          | false   | PGC_USERSET| Worst case: error in someone else's function (plperl.c:440-443) |
| `plperl.on_init`             | NULL    | PGC_SIGHUP | Code runs in unlocked interp at first use; only postgresql.conf / ALTER SYSTEM can set it |
| `plperl.on_plperl_init`      | NULL    | PGC_SUSET  | Superuser-only; runs in locked-down trusted interp |
| `plperl.on_plperlu_init`     | NULL    | PGC_SUSET  | Superuser-only; runs in unlocked untrusted interp |

The `PGC_SUSET` choice for `on_plperl_init` is justified inline
(plperl.c:432-444): a `USERSET` GUC would let a non-privileged user
inject code into a SECURITY-DEFINER plperl function's first-use init
path, escalating to the definer's privileges.

## State / globals

Everything backend-private — there is no shared memory. Process-local
statics (plperl.c:226-244):

- `plperl_interp_hash` — `HTAB *` keyed by `Oid user_id`.
- `plperl_proc_hash` — `HTAB *` keyed by `(proc_id, is_trigger, user_id)`.
- `plperl_active_interp` — currently-selected interpreter desc.
- `plperl_held_interp` — the partially-initialized first interp.
- `plperl_use_strict` / `plperl_on_init` / `plperl_on_plperl_init` /
  `plperl_on_plperlu_init` — GUC backing variables.
- `plperl_ending` — set in `plperl_fini` to gate SPI usage from END
  blocks.
- `pp_require_orig` — saved Perl-default require opcode handler.
- `plperl_opmask[MAXO]` — process-global mask table built from
  `PLPERL_SET_OPMASK` (plperl.c:483).
- `current_call_data` — per-call data, saved/restored across nested
  PL/Perl calls.

## Concurrency

A single backend ⇒ no concurrent threads. Each call-stack frame uses
`save_call_data` + `PG_FINALLY` to restore `current_call_data` and
`plperl_active_interp`. Cross-backend, no state is shared.

## Phase D notes

- **Opcode-based sandbox vs Safe.pm.** plperl deliberately does not
  use Perl's `Safe` module (which uses `Opcode` and `compartment`
  isolation differently). The choice is reasonable — Safe.pm has its
  own CVE history (CVE-2014-4330, CVE-2016-1238 affected Safe
  internals via `@INC`-relative loading) — but it does mean the
  upstream Perl ecosystem doesn't audit *this* opmask shape. Any new
  opcode added to Perl (`OP_*`) defaults to disabled because of
  `memset(opmask, 1, MAXO)` (plperl_opmask.pl:20), which is the
  correct fail-closed default. [verified-by-code]

- **`entereval` is allowed.** `eval "string"` works in trusted
  PL/Perl. The justification (plperl_opmask.pl:30) is that the opmask
  is permanent on the interpreter, so eval'd code is also masked.
  This is correct for opcode-level checks. It does mean that any
  string-injection vulnerability in plperl user code that ends in
  `eval $user_string` can do anything the opmask allows, which still
  includes calling SPI (and so executing arbitrary SQL as the function
  owner under SECURITY DEFINER). [inferred]

- **One interpreter per UID is heavy.** A backend that processes
  function calls for many different users (e.g. via SET ROLE in a
  connection pooler) will accumulate a Perl interpreter per user with
  no eviction. `plperl_destroy_interp` is only called from
  `plperl_fini` (on proc exit). This is documented in passing
  ("Once created, an interpreter is kept for the life of the
  process.", plperl.c:70) but the memory footprint scales linearly
  with distinct UIDs and is invisible to PG's memory accounting.
  [ISSUE-memory: no per-UID interpreter eviction; long-lived backend +
  many SET ROLE values → unbounded growth (maybe)]
  `source/src/pl/plperl/plperl.c:60-91, 540-548`

- **`plperl.on_init` runs in postmaster if loaded via
  `shared_preload_libraries`.** The comment at plperl.c:417-421
  acknowledges this is "not really right either way". If a DBA does
  `shared_preload_libraries = 'plperl'`, the on_init Perl code runs
  once in the postmaster process and is inherited by every fork. If
  the on_init script has side effects (opens sockets, spawns
  threads), every backend inherits them. [verified-by-code,
  from-comment, plperl.c:417-429] [ISSUE-defense-in-depth: on_init
  fork-inheritance from postmaster is not loudly documented
  (maybe)]

- **`%INC`-bypass nuance in `pp_require_safe`.** The check is
  `svp && *svp != &PL_sv_undef` (plperl.c:900). Any non-undef value
  in `%INC` is treated as "loaded". Standard Perl writes the resolved
  filename there, so this is consistent with normal behaviour, but
  trusted user code could (in principle) set `$INC{Foo} = 1` and
  then `use Foo` would short-circuit YES. The downstream import would
  then either succeed (if Foo's package is actually loaded in some
  other module) or noisily fail. Not a direct exploit, but
  defense-in-depth would validate the value too. [ISSUE-defense-in-depth:
  `pp_require_safe` doesn't validate the `%INC` value (nit)]
  `source/src/pl/plperl/plperl.c:900-901`

- **`%ENV` write protection is informational only.** The
  `PostgreSQL::InServer::WarnEnv` tie (`plc_trusted.pl:35-56`)
  *warns* on writes via `STORE`/`DELETE`/`CLEAR` and does nothing
  else. It also explicitly says "user can untie or otherwise disable
  this". This means **trusted PL/Perl can write to `%ENV`** —
  it just has to call `untie %ENV` first, which is plain Perl, not an
  opcode. The `*main::ENV = {%ENV}` line on plc_trusted.pl:49 detaches
  the magic, so the writes won't reach the OS environment, but the
  in-perl hash is fully mutable. [ISSUE-defense-in-depth:
  `WarnEnv` is informational, can be untied by trusted code
  (maybe)] `source/src/pl/plperl/plc_trusted.pl:35-56`

- **SPI uses no parameter binding for `spi_exec(query)`.** A trusted
  PL/Perl function that does `spi_exec("SELECT * FROM t WHERE x = '" .
  $user_input . "'")` runs that string with the function owner's
  privileges — `pg_verifymbstr` validates encoding but does no
  escaping. This is the standard SQL-injection-via-SPI surface
  shared with plpgsql's `EXECUTE`. plperl_sv_to_literal is provided
  as the escape primitive but documentation has to push users to it.
  [verified-by-code, plperl.c:3163, 1450-1478]

- **`PERL_SYS_INIT3` sets SIGFPE to SIG_IGN; plperl restores it.**
  plperl.c:790-801 explicitly notes that Perl's startup leaves SIGFPE
  ignored, which would cause forced process kill on Linux per POSIX.
  The fix is to call `pqsignal(SIGFPE, FloatExceptionHandler)` after
  `PERL_SYS_INIT3`. This is a real production correctness issue
  that has presumably been fixed once and gets re-fixed each time
  Perl regresses. [from-comment, plperl.c:790-801]

- **`perl_destruct` not invoked.** On backend exit, only END blocks
  run; SVs are not freed, Perl's mortal-list isn't drained, and
  cryptographic / secret SV contents may live in memory until
  process death. Since process death frees the address space anyway,
  this is not a residency concern unless the backend forks (it
  doesn't, fork happens at the postmaster). [from-comment,
  plperl.c:931-936]

- **Type conversion DoS.** `plperl_spi_execute_fetch_result` checks
  `processed > AV_SIZE_MAX` and raises (plperl.c:3223-3227). Large
  arrays going perl → datum go through `array_to_datum_internal` with
  `check_stack_depth()` (plperl.c:1175, via `plperl_sv_to_datum`
  plperl.c:1338). Embedded NULs in scalars going perl → datum are
  passed to `InputFunctionCall` as cstrings with no separate length —
  so an embedded NUL is silently truncated when `sv2cstr` happens to
  not contain one and is full-length when it does (sv2cstr stores the
  Perl length, then `utf_u2e` may or may not preserve it).
  [ISSUE-correctness: embedded-NUL handling in sv2cstr→InputFunctionCall
  path is ambiguous; UTF-8 byte stream with `\0` may reach typinput as
  a NUL-truncated cstring (maybe)] `source/src/pl/plperl/plperl.h:120-140`,
  `source/src/pl/plperl/plperl.c:1432-1444`

- **Trigger-context strings are inert but unverified.** `tg_trigger->tgargs`
  flows into the `%_TD` hash without `pg_verifymbstr`. Since they
  come from `pg_trigger.tgargs` which was validated at trigger
  creation, this is safe; but an attacker who can write to the
  catalog (already superuser) could inject malformed UTF-8 that
  surfaces as a Perl-side parse error inside the trigger. Not a
  practical threat. [inferred]

- **The validator forces compile-side privilege checks but the
  body-check is gated on `check_function_bodies`.** A non-superuser
  who has `USAGE ON LANGUAGE plperlu` (rare but possible) could create
  a plperlu function with `check_function_bodies = off` set in their
  session, and the body would never be compiled until first call.
  [verified-by-code, plperl.c:2053-2056] [ISSUE-audit-gap:
  check_function_bodies-off bypass on plperlu validator (nit)] —
  `source/src/pl/plperl/plperl.c:2053-2056`

## Cross-references

- `source/src/pl/plperl/plperl.h` — declares the SPI bridge functions
  and the inline conversion helpers (`sv2cstr`, `cstr2sv`,
  `croak_cstr`).
- `source/src/pl/plperl/plperl_system.h` — perl headers + Windows
  fixups; pulled in by `plperl.h`.
- `source/src/pl/plperl/plperl_opmask.pl` — generator for
  `plperl_opmask.h` (compiled into the binary).
- `source/src/pl/plperl/plc_trusted.pl` — the Perl source string
  embedded as `PLC_TRUSTED` and `eval_pv`'d during
  `plperl_trusted_init`.
- `source/src/pl/plperl/plc_perlboot.pl` — the Perl source string
  embedded as `PLC_PERLBOOT` and passed via `-e` during
  `perl_parse` — sets up `mkfunc`, the `$SIG{__WARN__}` / `$SIG{__DIE__}`
  handlers, the `ARRAY` overload class, `is_array_ref` and
  `encode_array_literal/encode_array_constructor`.
- `source/src/pl/plperl/SPI.xs` / `Util.xs` — XSUB wrappers that call
  `plperl_spi_exec` etc.
- `source/src/backend/catalog/pg_language.dat` — declares the
  language entries; `lanpltrusted` is the canonical trust bit.
- **A9 baseline (plpgsql):** PL/pgSQL has NO interpreter at all in the
  Perl sense — it is a SQL-extending procedural language compiled
  directly into a `PLpgSQL_function` tree. Its "trusted" gate is
  *exclusively* `pg_language.lanpltrusted = true` enforced by GRANT
  USAGE — no opmask, no sandbox, because there are no Perl-style
  unsafe ops to mask. plperl, by contrast, must wrap a Turing-complete
  general-purpose runtime (with file/network/process access) and so
  needs the opmask + `pp_require_safe` defense-in-depth layer that
  plpgsql doesn't have.

<!-- issues:auto:begin -->
- [Issue register — `plperl`](../../../../issues/plperl.md)
<!-- issues:auto:end -->

## Issues spotted (inline)

- [ISSUE-defense-in-depth: `pp_require_safe` accepts any non-undef
  `%INC` value as "loaded" (maybe)] —
  `source/src/pl/plperl/plperl.c:900-901`
- [ISSUE-defense-in-depth: `on_init` postmaster fork-inheritance is
  acknowledged but not loudly warned in docs (maybe)] —
  `source/src/pl/plperl/plperl.c:417-429`
- [ISSUE-defense-in-depth: `WarnEnv` `%ENV` protection is informational;
  trusted code can `untie %ENV` (maybe)] —
  `source/src/pl/plperl/plc_trusted.pl:35-56`
- [ISSUE-memory: no per-UID interpreter eviction in long-lived
  backends (maybe)] — `source/src/pl/plperl/plperl.c:60-91, 540-548`
- [ISSUE-correctness: embedded-NUL handling in
  `sv2cstr→InputFunctionCall` truncates ambiguously (maybe)] —
  `source/src/pl/plperl/plperl.h:120-140`,
  `source/src/pl/plperl/plperl.c:1432-1444`
- [ISSUE-audit-gap: `check_function_bodies=off` bypasses plperlu
  validator's body compilation (nit)] —
  `source/src/pl/plperl/plperl.c:2053-2056`
- [ISSUE-error-handling: `plperl_on_plperl_init` / `on_plperlu_init`
  GUCs report `ERRCODE_EXTERNAL_ROUTINE_EXCEPTION` for any compile
  failure with comment "XXX need to find a way to determine a better
  errcode here" repeated 4 times (nit)] —
  `source/src/pl/plperl/plperl.c:1029, 1056, 2263, 2331`
- [ISSUE-documentation: `plperl_trusted_init` opcode mask is documented
  only in `plperl_opmask.pl` comments, not in plperl.c (nit)] —
  `source/src/pl/plperl/plperl.c:1001-1005`
