# pltcl.c

Covers `source/src/pl/tcl/pltcl.c` (3389 LOC) — the entire PL/Tcl backend, hosting BOTH the trusted `pltcl` language (Tcl safe-interpreter sandbox) and the untrusted `pltclu` language (full Tcl) from the same source file via a `bool pltrusted` parameter threaded through every code path.

The pltcl module lives at `src/pl/tcl/` (directory name is just `tcl`, not `pltcl`).

Source pin: `4b0bf0788b0`.

## One-line summary

A single shared library (`$libdir/pltcl`) registers two SQL-visible call handlers — `pltcl_call_handler` (trusted, dispatches with `pltrusted=true`) and `pltclu_call_handler` (untrusted, `pltrusted=false`) — and a per-userID interpreter cache where each entry is created via `Tcl_CreateSlave(master, name, isSafe)` with `isSafe` driven by the `pltrusted` flag. Trusted interpreters get Tcl's built-in safe-interpreter sandbox; untrusted interpreters get full Tcl including `exec`, `file`, `socket`, `open`.

## Public API / entry points

C-visible SQL handlers (registered by `PG_FUNCTION_INFO_V1`):

- `pltcl_call_handler(PG_FUNCTION_ARGS)` — entry for the trusted language [verified-by-code: `source/src/pl/tcl/pltcl.c:702-709`]. Forwards to `pltcl_handler(fcinfo, true)`.
- `pltclu_call_handler(PG_FUNCTION_ARGS)` — entry for the untrusted language [verified-by-code: `source/src/pl/tcl/pltcl.c:714-721`]. Forwards to `pltcl_handler(fcinfo, false)`.
- `_PG_init(void)` — library load-time init: notifier override, hold-interp creation, hash-table setup, GUC registration [verified-by-code: `source/src/pl/tcl/pltcl.c:409-490`].

Both call handlers are non-static so that `fmgr.c` can find them by symbol lookup; the comment `/* keep non-static */` at `:704, 716` is explicit.

Internal dispatch chain:

- `pltcl_handler(fcinfo, pltrusted)` — routes to func/trigger/event-trigger sub-handler based on call context [verified-by-code: `source/src/pl/tcl/pltcl.c:728-796`].
- `pltcl_func_handler` [verified-by-code: `source/src/pl/tcl/pltcl.c:802-1054`].
- `pltcl_trigger_handler` [verified-by-code: `source/src/pl/tcl/pltcl.c:1060-1314`].
- `pltcl_event_trigger_handler` [verified-by-code: `source/src/pl/tcl/pltcl.c:1320-1363`].

Tcl-visible commands installed into every interpreter [verified-by-code: `source/src/pl/tcl/pltcl.c:519-540`]:

- `elog`, `quote`, `argisnull`, `return_null`, `return_next`
- `spi_exec`, `spi_prepare`, `spi_execp`
- `subtransaction`, `commit`, `rollback`

## Key invariants

- **Single source file, two languages, same `.so`.** Both `pltcl.control` and `pltclu.control` set `module_pathname = '$libdir/pltcl'` [verified-by-code: `source/src/pl/tcl/pltcl.control`, `source/src/pl/tcl/pltclu.control`]. The discriminator is which call handler the catalog binds to — and at runtime that's the same `pltcl_handler` with `pltrusted` bit flipped.
- **One Tcl interpreter per `(SQL-userid, language)` pair for trusted; ONE shared interpreter for untrusted.** [from-comment: `source/src/pl/tcl/pltcl.c:112-120`]. The hash key is OID: real `GetUserId()` for trusted, `InvalidOid` (0) for untrusted. The rationale at `:115-117` is explicit: "ensure that an unprivileged user can't inject Tcl code that'll be executed with the privileges of some other SQL user." Userid-bucketed interpreters are PL/Tcl's defense against same-language proc-pollution attacks.
- **`pltcl_hold_interp` is a dummy master, never used for execution.** [from-comment: `source/src/pl/tcl/pltcl.c:439-442`]. Its only purpose is to prevent Tcl from closing stdout/stderr when a slave interp is deleted. All real work happens in `Tcl_CreateSlave`-created subsidiary interpreters.
- **Tcl Notifier subsystem is overridden to no-ops.** [from-comment: `source/src/pl/tcl/pltcl.c:344-354`, verified-by-code: `:355-398, 429-437`]. Default Tcl notifier code path spawns a thread if Tcl was compiled with `TCL_THREADS`; a multi-threaded backend "breaks all sorts of things" (PG's MemoryContext machinery, signal handlers, etc.). The override installs `pltcl_*` no-op notifier procs.
- **Procedure cache key is `(proc_id, is_trigger, user_id)`** [verified-by-code: `source/src/pl/tcl/pltcl.c:196-206`]. Trigger-vs-function flag is part of the key because the same function OID could in principle be called as both (event triggers vs plain SQL function). `user_id = InvalidOid` for pltclu so there's one cache entry across all callers.
- **Procedure cache invalidation by `(fn_xmin, fn_tid)` of the pg_proc row** [verified-by-code: `source/src/pl/tcl/pltcl.c:1461-1469`]. After `CREATE OR REPLACE FUNCTION` the OID stays the same but xmin/TID changes — that's what triggers recompile. Same trick plpgsql uses (`pl_comp.c`).
- **Procedure cache uses NAME-based internal Tcl proc names, not OID.** The internal proc name is built from `format_procedure(fn_oid)` mangled to ASCII alphanumerics with underscores, then disambiguated by appending the OID if the mangled name collides [verified-by-code: `source/src/pl/tcl/pltcl.c:1527-1576`]. The choice is for human-readable Tcl error messages; the underlying lookup is still OID-keyed via the `pltcl_proc_htab` hash. So NAME is the EXTERIOR identifier (in Tcl error tracebacks) but OID is the LOOKUP identifier.
- **`fn_refcount` discipline** [from-comment: `source/src/pl/tcl/pltcl.c:736-743`, verified-by-code: `:786-791, 1821-1828`]. Per-call entry into `pltcl_handler` bumps refcount; exit decrements; if zero, the prodesc's memory context is deleted. When `compile_pltcl_function` rebuilds a prodesc for an updated pg_proc row, it hashes the new one in and decrements the old; the old prodesc's memory survives while any in-flight call still holds it.
- **`pltcl_call_state` saved/restored around every nested call** [verified-by-code: `source/src/pl/tcl/pltcl.c:749-750, 784-785`]. The static `pltcl_current_call_state` pointer means a Tcl-callable command like `pltcl_argisnull` can find the caller without an explicit arg.
- **Trusted/untrusted parity is enforced at start_proc selection.** `call_pltcl_start_proc` checks `procStruct->prolang != prolang` AND `prosecdef = true` — refusing both [verified-by-code: `source/src/pl/tcl/pltcl.c:642-658`]. The two checks together guarantee the start_proc runs in the SAME Tcl interpreter that triggered its load. Crucial: a SECURITY DEFINER start_proc could otherwise escalate the interpreter to a different user's privileges.

## Notable internals

### `_PG_init` is postmaster-safe

[from-comment: `source/src/pl/tcl/pltcl.c:404-407`, verified-by-code: `:409-490`] — declared safe to run in the postmaster process, in case `shared_preload_libraries = 'pltcl'`. The hold-interp creation and hash-table allocation happen unconditionally; per-userid interpreters are created lazily in `pltcl_fetch_interp`.

### `compile_pltcl_function`: the big function

[verified-by-code: `source/src/pl/tcl/pltcl.c:1418-1838`] — 420 LOC of:

1. Hash-table lookup by `(fn_oid, is_trigger, user_id)`.
2. xmin/TID check for staleness; if stale, fall through to recompile.
3. `pltcl_fetch_interp` to find/create the Tcl interpreter for this user.
4. If recompiling, delete the old internal Tcl command (`Tcl_DeleteCommand`).
5. Build the mangled internal proc name (disambiguate by appending OID until unique).
6. Allocate `pltcl_proc_desc` in a fresh memory context named after `user_proname`.
7. Resolve return type input function, pseudotype checks, set retistuple/retisdomain/retisset.
8. Resolve each argument's output function (for non-rowtype args).
9. Build the Tcl `proc` command — header (`upvar #0 <name> GD`), argument unpacking, then the user's source code appended verbatim.
10. `Tcl_EvalEx` to install the proc in the interpreter.
11. Decrement old prodesc's refcount, replace hashtable entry.

The `GD` upvar at step 9 is the documented per-function "global data" dict. The user's Tcl source is appended via `UTF_E2U` (server-encoded → UTF-8). Tcl source code is interpreted as UTF-8 internally.

### `pltcl_func_handler` per-arg dispatch

[verified-by-code: `source/src/pl/tcl/pltcl.c:867-933`] — rowtype args are passed as Tcl lists for `array set`; scalar args go through the proc's `arg_out_func` and UTF-encoded. NULL args are passed as empty Tcl objects (`Tcl_NewObj()`), which means Tcl code receives them as empty strings — there is no native Tcl null. Compare to plpgsql (which has IS NULL) and plpython (which has Python `None`).

### Trigger arg conventions

[verified-by-code: `source/src/pl/tcl/pltcl.c:1101-1256`] — the trigger receives fixed-name Tcl variables: `TG_name`, `TG_relid`, `TG_table_name`, `TG_table_schema`, `TG_relatts`, `TG_when`, `TG_level`, `TG_op`, plus `NEW`/`OLD` as Tcl arrays via `array set NEW $__PLTcl_Tup_NEW`. The `TG_table_name` and `TG_table_schema` come from `SPI_getrelname` / `SPI_getnspname`. The user's trigger body sees them as plain Tcl strings — and if those strings contain Tcl-list metacharacters, they could be misinterpreted by careless user code that does `eval` or list operations on them. This is the standard pltcl convention and isn't a CVE, but it's a Phase D consideration: a malicious table name could shape a trigger's behavior. (Real attack would require the attacker to already control table creation, which is the normal privilege model.)

### `pltcl_subtransaction` is a Tcl command, not a context manager

[verified-by-code: `source/src/pl/tcl/pltcl.c:2976-3016`] — Tcl users write `subtransaction { ... tcl code ... }`. The semantics: begin internal subxact, eval the body, commit if `TCL_OK`, rollback if `TCL_ERROR`. Note `pltcl_subtransaction` does NOT use `pltcl_subtrans_begin/abort` because it does NOT want to construct the Tcl errorCode — the user's body has already done that via `pltcl_construct_errorCode` inside any errored sub-command.

### `pltcl_SPI_execute`: text-execute path

[verified-by-code: `source/src/pl/tcl/pltcl.c:2410-2512`] — `spi_exec ?-array name? ?-count n? query ?loop_body?`. The query string goes through `UTF_U2E` then straight to `SPI_execute`. **No automatic parameterization.** Tcl user is responsible for using `quote` or `spi_prepare`/`spi_execp` to avoid injection. The `loop_body` argument is a Tcl script evaluated per row with the row's columns set as Tcl variables.

### `pltcl_SPI_prepare` + `spi_execp`: the safe path

[verified-by-code: `source/src/pl/tcl/pltcl.c:2632-2754, 2760-2967`] — `spi_prepare query argtype-list` returns a string queryid (the address of the `pltcl_query_desc` struct, `%p`-formatted). The queryid is stored in a per-interpreter Tcl hash table — NOT global. That means a `pltcl` proc and a `pltclu` proc can't share prepared queries even if they're called by the same user (different interpreters). The plan is saved via `SPI_keepplan`. `spi_execp ?-array name? ?-count n? ?-nulls string? queryid ?args? ?loop_body?` retrieves the plan and runs it with the supplied args; the `-nulls` option is a per-arg `n`/`space` string. Type resolution at prepare time uses `parseTypeString` — same search_path hazard as plpython.

### Memory-leak FIXME on prepared plans

[from-comment: `source/src/pl/tcl/pltcl.c:2666-2667`] — explicit "if the function is recompiled for whatever reason, permanent memory leaks occur. FIXME someday." Each `spi_prepare` allocates a fresh `plan_cxt` under `TopMemoryContext`; the `pltcl_query_desc` lives there. When the prodesc is destroyed (recompile), the per-interpreter hash table is NOT swept. The leaked plan_cxt is bounded by the interpreter's lifetime (which itself is the backend's lifetime), so in practice this is "a leak proportional to (recompiles × prepared_plans)." A long-lived backend with a developer iterating on a pltcl proc could accumulate noticeable memory.

### `pltcl_returnnext`: SRF + subxact

[verified-by-code: `source/src/pl/tcl/pltcl.c:2240-2336`] — Tcl users write `return_next $row` inside a set-returning function body. The function call wraps every `return_next` in its own internal subtransaction (NOT via `pltcl_subtrans_begin` — manual `BeginInternalSubTransaction` to get a short-lived memory context "for free", per the comment at `:2278-2283`). On error, rolls back the inner subxact and returns TCL_ERROR to the user's body.

### `pltcl_construct_errorCode`: structured error attachment

[verified-by-code: `source/src/pl/tcl/pltcl.c:1931-2070`] — builds Tcl's `errorCode` list with `POSTGRES`/`SQLSTATE`/`condition`/`message`/`detail`/`hint`/`context`/`schema`/`table`/`column`/`datatype`/`constraint`/`statement`/`cursor_position`/`filename`/`lineno`/`funcname`. Tcl scripts can use `lindex $errorCode N` or `dict get` to extract fields. This is the most thorough error-attachment of any PL — plpython attaches a 10-tuple as `spidata`, plperl attaches `%@`. pltcl exposes 16 keys.

### `pltcl_elog`: ERROR is returned to Tcl, not thrown

[verified-by-code: `source/src/pl/tcl/pltcl.c:1843-1924`] — when user calls `elog ERROR "msg"`, pltcl does NOT call `ereport(ERROR, …)` directly; it sets the Tcl interp result to the message and returns `TCL_ERROR`. The PG ereport happens later when the call handler sees `TCL_ERROR` and runs `throw_tcl_error`. The reason: the user might wrap the elog in `catch { elog ERROR ... }`, which is the Tcl way to write `EXCEPTION WHEN ...`. For non-ERROR levels (DEBUG/LOG/INFO/NOTICE/WARNING/FATAL), it DOES call `ereport()` directly inside `PG_TRY` — if THAT throws, the catch path builds the errorCode and returns TCL_ERROR to Tcl. FATAL is a one-way trip ("aren't going to come back to us at all" per the comment at `:1891`).

## Trust posture

**THE central feature of this file.** pltcl is the OTHER dual-posture PL (along with plperl).

### How a single .c dispatches trusted vs untrusted

The bool `pltrusted` is set once by which SQL call handler the catalog invoked:

```
pltcl_call_handler   → pltcl_handler(fcinfo, true)   → "safe" interpreter via Tcl_CreateSlave(..., 1)
pltclu_call_handler  → pltcl_handler(fcinfo, false)  → full Tcl via Tcl_CreateSlave(..., 0)
```

The third argument to `Tcl_CreateSlave` at `source/src/pl/tcl/pltcl.c:507-508` is the `isSafe` flag: `1` = create as a Tcl Safe Interpreter, `0` = create with full command set.

### What Tcl's safe interpreter blocks

Tcl's safe-interp model (Tcl-core feature, NOT a pltcl invention) hides "dangerous" Tcl commands by aliasing them out of the safe interpreter's command table. In a safe-interp:

- `exec` → not present (no shell-out).
- `open`, `close` (when applied to files) → not present.
- `socket` → not present.
- `file` → most subcommands hidden (no `file delete`, `file rename`, `file mtime`); a handful of "read-only" file subcommands may remain.
- `source` → restricted (can `source` only from a master-controlled path token, normally empty).
- `pwd`, `cd` → not present.
- `load` → restricted (cannot load arbitrary `.so`).
- `package require` of unsafe packages → fails.
- Tcl init is NOT run for safe interps (`Tcl_Init` is skipped in the safe case per the comment at `:503-504`).

The trusted user gets `clock`, `string`, `list`, `proc`, `set`, `if`, `for`, `expr`, all the data-structure and control-flow primitives — but no I/O and no shell access. This is genuinely a sandbox at the language-design level (unlike Python, where there is no equivalent), and is comparable in strength to Perl's Safe.pm.

### Compared to plperl's Safe.pm

[A10-1 baseline, plperl] — plperl's trusted variant uses Perl's `Safe.pm` module, which works by `Safe->new(NS)->reval(code)`, intercepting opcodes via Perl's op-mask. Safe.pm has had a long history of CVEs (CVE-2010-1168, CVE-2010-1447, etc.) because the Perl op-set evolved and Safe.pm needed updating; pltcl's safe interp is, by contrast, a feature of the Tcl core maintained alongside the rest of Tcl. **Tcl Safe is generally considered stronger than Safe.pm** because the safety boundary is in the C-level command dispatch (you cannot reach the unsafe primitive at all), whereas Safe.pm relies on opcode masking (the primitive exists, you just can't compile a reference to it). Verifying this comparison empirically would require a CVE-by-CVE audit; the *architecture* is stronger.

Compared to **plpgsql** (A9 baseline): plpgsql has nothing — it doesn't need a sandbox because it has no I/O primitives at all. No file commands, no socket, no exec — just SQL execution and control flow. plpgsql's "trust" is by elimination, not by gating.

Compared to **plpython** (this sweep): plpython is **untrusted-only**. There is no `plpython3` (trusted), only `plpython3u`. The reason, per the upstream design discussion that's documented across plpython.h and the PG mailing list: Python's stdlib is too large and too dynamically reflective to safely subset; restricting `import` is insufficient because `__builtins__`, `getattr`, `()`-cell traversal, and ctypes all provide trivial escapes. Verifying this design choice across years of plpython development — the PG community gave up on a trusted Python in early plpython development and never revisited.

### GUC: `pltcl.start_proc` and `pltclu.start_proc`

[verified-by-code: `source/src/pl/tcl/pltcl.c:471-484`] — both are `PGC_SUSET` (superuser-only to set; can be set globally or per-database/per-role by a superuser via `ALTER ROLE ... SET`). The chosen proc runs once per interpreter creation (i.e. first call to pltcl/pltclu in a backend, per userid for pltcl).

The dispatch in `call_pltcl_start_proc` picks `pltcl_start_proc` or `pltclu_start_proc` based on `pltrusted` [verified-by-code: `source/src/pl/tcl/pltcl.c:614-615`]. **Critical safety checks** [verified-by-code: `source/src/pl/tcl/pltcl.c:642-658`]:

1. `procStruct->prolang != prolang` — the start_proc must be in the SAME language as the just-initialized interpreter. Without this, a superuser setting `pltcl.start_proc = my_pltclu_fn` could effectively run pltclu code inside the trusted interpreter (but actually no — it would just fail to compile in the safe interp, since the start_proc is invoked through normal fmgr — so the practical effect is "use a pltclu function from a trusted interp's start_proc would fail"). The check makes this explicit.
2. `procStruct->prosecdef` — start_proc must NOT be SECURITY DEFINER. Otherwise the start_proc would execute as its definer's privileges, but inside the *invoker*'s Tcl interpreter — a privesc.

Together these two checks enforce the rule: **the start_proc executes in the same Tcl interpreter, same userid, same language as the caller**. The GUC author chose the proc, but the proc runs with no privilege amplification.

### `pltcl_func_handler` vs `pltclu_func_handler` divergence

There is none — they're the same code path. `pltrusted` is a parameter, not a code-fork. The only behavioral difference is which interpreter the call lands in, and what commands the user's Tcl body has access to inside that interpreter. Everything else (SPI bridge, error handling, trigger conventions, argument marshalling, result conversion) is identical. This is by design and is more maintainable than plperl's parallel `plperl_call_handler` + `plperlu_call_handler` paths.

## Cross-references

- `pg_language` ACL: `pltcl.control` sets `trusted = true`, `pltclu.control` does NOT. `pg_language.lanpltrusted` becomes the catalog's view of trust; PG core's CREATE EXTENSION machinery uses it to decide whether USAGE can be granted to non-superusers. See `source/src/pl/tcl/pltcl.control` and `source/src/pl/tcl/pltclu.control`.
- `source/src/backend/executor/spi.c` — every `SPI_*` call from `pltcl_SPI_execute`, `pltcl_SPI_prepare`, `pltcl_SPI_execute_plan`, `pltcl_commit`, `pltcl_rollback`.
- `source/src/backend/access/transam/xact.c` — `BeginInternalSubTransaction`, `ReleaseCurrentSubTransaction`, `RollbackAndReleaseCurrentSubTransaction`, `SPI_commit`/`SPI_rollback`.
- `source/src/backend/utils/cache/typcache.c` — `lookup_rowtype_tupdesc` for rowtype arguments at `:893`.
- `source/src/backend/commands/event_trigger.c` — `GetCommandTagName` used in `pltcl_event_trigger_handler`.
- A9 baseline (plpgsql): trust by elimination — no I/O primitives at all. The "trust" gate is implicit.
- A10-1 (plperl): dual-posture (plperl/plperlu) via `Safe.pm`. Comparable safety architecture, weaker historical CVE record.
- A10-2/A10-3 (plpython core + helpers): **untrusted-only** by design. The "no trusted Python" decision is documented in `plpython.h.md` of A10-2 sweep.
- A10-4 (plpython spi/util/subxact, this same sweep): `plpy_spi.c`, `plpy_subxactobject.c`, `plpy_util.c`. The SPI bridge here is structurally identical (subxact-wrap every SPI call), but the trust posture is opposite.
- `pltclerrcodes.h` — included verbatim into `exception_name_map[]` at `:266-269` to map SQLSTATE → condition name.

## Issues spotted

- **[ISSUE-security: `spi_exec query` does NOT parameterize; user must call `quote` or use `spi_prepare`+`spi_execp` (likely, by design)]** — `source/src/pl/tcl/pltcl.c:2491`. Standard PL hazard, documented behavior. Phase D audit: every pltcl function that interpolates a parameter into the query string of `spi_exec` is a SQLi sink. Note that `quote` (`:2095-2142`) doubles single-quotes and backslashes but does NOT understand schema-qualified identifiers — users who need identifier quoting must build it themselves.
- **[ISSUE-security: `pltcl.start_proc` / `pltclu.start_proc` are PGC_SUSET — superuser-only to set, but their safety checks rely on prolang match + non-secdef (defense-in-depth, confirmed)]** — `source/src/pl/tcl/pltcl.c:471-484, 642-658`. The two checks are present; without them a misconfigured GUC could allow privilege amplification at first-use of the language. Sound design, but a defense-in-depth audit should verify there are no other paths to set these GUCs (e.g. via `pg_db_role_setting`) that might bypass `PGC_SUSET`. Quick check: PGC_SUSET applies to all routes including ALTER ROLE/DB SET, so this is solid.
- **[ISSUE-memory: prepared-plan leak FIXME (confirmed)]** — `source/src/pl/tcl/pltcl.c:2666-2667`. The file's own comment marks this. Bounded by backend lifetime; only meaningful for very long-lived sessions with many recompiles.
- **[ISSUE-security: trigger TG_table_name / TG_table_schema are user-controlled if the attacker can name a table (maybe)]** — `source/src/pl/tcl/pltcl.c:1126-1136`. A trigger body that does `spi_exec "SELECT * FROM $TG_table_name"` is a SQLi sink. The attacker would need CREATE privilege on a schema and the ability to attach the trigger; the typical PG privilege model already prevents this. Worth a doc note for trigger authors.
- **[ISSUE-correctness: NULL trigger args passed as empty Tcl strings, indistinguishable from empty-string values (likely, by design)]** — `source/src/pl/tcl/pltcl.c:910-911, 879`. Tcl has no native null. A pltcl function with arg `text` receives `""` for both NULL and empty-string. The user must call `argisnull` to distinguish. This is the documented pltcl idiom and matches the absence of a Tcl null concept. Flagging for the audit trail.
- **[ISSUE-error-handling: `pltcl_elog` for FATAL hits the same `ereport(level, ...)` path inside PG_TRY; FATAL "isn't going to come back" per comment, but PG_CATCH is still set up around it (nit)]** — `source/src/pl/tcl/pltcl.c:1891-1921`. The PG_CATCH at `:1903` is unreachable in the FATAL case (FATAL → proc_exit). Harmless dead code; comment at `:1891` acknowledges it.
- **[ISSUE-audit-gap: no audit logging of which Tcl commands were called (audit-gap, maybe)]** — there is no per-PL audit hook. Backend logs of `SPI_execute` calls (via `log_statement`/`auto_explain`) capture only the SQL, not the Tcl-side flow. Same gap as plpython.
- **[ISSUE-defense-in-depth: Tcl_DeleteCommand of old internal proc "ignores any error" on recompile (confirmed)]** — `source/src/pl/tcl/pltcl.c:1518-1519`. The comment says we assume Tcl's refcounting prevents physical deletion during execution. If a future Tcl ABI breaks that assumption, recompiling a function mid-call could SEGV. Bounded by Tcl-version compatibility (`Tcl >= 8.4` enforced at compile time at `:53-56`).
- **[ISSUE-concurrency: Notifier override globally disables Tcl threading (confirmed, by design)]** — `source/src/pl/tcl/pltcl.c:344-354, 429-437`. If a future Tcl library version starts using the notifier in unexpected ways (e.g. for `clock` operations), pltcl could behave subtly differently from standalone tclsh. Locked-in compatibility cost.
- **[ISSUE-documentation: trust-posture rationale lives in scattered comments (nit)]** — `source/src/pl/tcl/pltcl.c:113-119, 503-504, 642-658`. Phase A consideration: consolidate into a top-of-file block. Currently a reader has to assemble the picture across `pltcl_init_interp`, `pltcl_fetch_interp`, and `call_pltcl_start_proc`.
- **[ISSUE-api-shape: dual call handlers + bool param could be one call handler with a per-pg_proc bit, but isn't (api-shape, nit)]** — `source/src/pl/tcl/pltcl.c:702-721`. The choice to keep them separate is right (the SQL catalog needs two distinct handler symbols for two distinct `pg_language` rows), but worth a one-line comment near `:702` explaining why.
