# set_user — controlled REAL role escalation (incl. superuser) wrapped in an audit trail + a command block-list

> Ideology note produced by the pg-extension-anthropologist cloud routine.
> Repo: `pgaudit/set_user` @ branch `main` (`default_version = '4.2.0'`,
> `PG_MODULE_MAGIC_EXT(.name = "set_user", ...)`), fetched 2026-07-08.
> Caveat: characterization based on the files actually fetched —
> `README.md` (791 lines, read in full), `Makefile`, `src/set_user.c`
> (the 911-line core, read in full), `src/set_user.h`, `extension/set_user.sql`,
> and `set_user.control`. NOT fetched: `src/compatibility.h` (defines the
> version-shim macros `_PU_HOOK`, `_prev_hook`, `_standard_ProcessUtility`,
> `_InitializeSessionUserId`, `NO_ASSERT_AUTH_UID_ONCE` — referenced but not
> read; their call sites in `set_user.c` are cited instead) and the
> `sql/`+`expected/` regression fixtures named by `REGRESS = set_user`.
> Unlike its emulation-family cousins, set_user IS a real `CREATE EXTENSION`
> (there IS a `set_user.control`, and a `set_user.sql` install script) — but it
> is *also* loaded via `shared_preload_libraries`, and the hooks only arm when
> so loaded [from-README, README.md:22, 234-235].

## Domain & purpose

set_user is the **escalation direction** of the privilege-hook family. Where
`supautils` and `pgextwlist` make a *non-superuser look like a superuser* for a
bounded operation (emulation), set_user does the opposite thing honestly: it
lets a role that has been `GRANT`ed `EXECUTE` **actually become another role —
including a real superuser — for the rest of the session**, and then wraps that
real transition in three defenses so the escalation is auditable and bounded
[from-README, README.md:45-71]. Its stated purpose: "an additional layer of
logging and control when unprivileged users must escalate themselves to
superuser or object owner roles in order to perform needed maintenance tasks"
[from-README, README.md:46-48]. The SQL surface is `set_user(text)` /
`set_user(text, token)` (transition to a *non*-superuser), `set_user_u(text)`
(the `_u` variant — the only path allowed to escalate to a superuser),
`reset_user()` / `reset_user(token)` (restore), and `set_session_auth(text)`
(an irrevocable one-way switch) [verified-by-code, extension/set_user.sql:7-49].
`EXECUTE` on the escalating functions is `REVOKE`d from `PUBLIC` at install time
so the grant is the primary gate [verified-by-code, extension/set_user.sql:20-21,42].
The `set_user.control` comment sums the thesis: "similar to SET ROLE but with
added logging" [verified-by-code, set_user.control:2].

## How it hooks into PG

`_PG_init` defines seven GUCs and installs **two hooks plus a transaction
callback** [verified-by-code, set_user.c:512-559]:

- `ProcessUtility_hook = PU_hook` — the command block-list, chained to
  `prev_hook` [verified-by-code, set_user.c:551-552, 629-636].
- `object_access_hook = set_user_object_access` — a second enforcement point
  that blocks the *function-call* route to the same forbidden settings
  (`set_config()`), chained to `next_object_access_hook`
  [verified-by-code, set_user.c:554-556, 719-755].
- `RegisterXactCallback(set_user_xact_handler, NULL)` — the role swap is
  **deferred to transaction pre-commit**, not done inside the SQL function
  [verified-by-code, set_user.c:558, 454-510].

The seven GUCs are all `PGC_SIGHUP` (config-file, not per-session user-settable):
`set_user.block_alter_system`, `set_user.block_copy_program`,
`set_user.block_log_statement` (all default `true`),
`set_user.nosuperuser_target_allowlist` and `set_user.superuser_allowlist`
(both default the wildcard `"*"`), `set_user.superuser_audit_tag` (default
`"AUDIT"`), and `set_user.exit_on_error` (default `true`)
[verified-by-code, set_user.c:515-548].

### The role swap: staged in the function, committed by the xact handler

This is the load-bearing mechanism and it is NOT a bespoke seccontext swap.
`set_user()` does no identity change itself; it validates and **stages** a
`SetUserXactState` (`pending_state`) in `TopMemoryContext`
[verified-by-code, set_user.c:286-289, 300-323]. The actual transition happens
in `set_user_xact_handler` on `XACT_EVENT_PRE_COMMIT`, where it calls core's
own SET ROLE primitive:

```c
SetCurrentRoleId(pending_state->userid, pending_state->is_superuser);   /* set_user.c:473 */
```

[verified-by-code, set_user.c:461-473]. `SetCurrentRoleId` is the same core
function backing `SET ROLE` (it flips the effective user id via
`SetUserIdAndSecContext` internally) — so set_user performs a **real** role
assumption to the target's real OID, not a faked one. This deferral is exactly
why `set_user()` is forbidden inside an explicit transaction block: the swap
must land at commit of the enclosing implicit transaction
[verified-by-code, set_user.c:232-238; from-README, README.md:247-248].
On `XACT_EVENT_ABORT` the pending state is freed and `is_reset` cleared, so a
rolled-back call leaves identity untouched [verified-by-code, set_user.c:503-506].

Escalation gating happens at stage time: if the target role `rolsuper`, the
call must be `set_user_u` (`is_privileged`) AND the caller must pass
`check_user_allowlist(GetUserId(), SU_Allowlist)`; a non-superuser target must
instead pass `check_user_allowlist(target, NOSU_TargetAllowlist)`
[verified-by-code, set_user.c:326-347]. The allowlist parser supports comma
lists, `+group` membership via `has_privs_of_role`, and a solo `*` wildcard —
and errors if a name is intermingled with `*`
[verified-by-code, set_user.c:118-184].

### The audit trail

At pre-commit the transition is logged unconditionally —
`elog(LOG, "%sRole %s transitioning to %sRole %s", ...)` with a `"Superuser "`
prefix when either side is a superuser [verified-by-code, set_user.c:466-470].
When escalating to a superuser *and* `block_log_statement` is on, set_user
force-sets `log_statement = "all"` and appends `superuser_audit_tag` (default
`AUDIT`) to `log_line_prefix`, so every subsequent statement is logged and
tagged [verified-by-code, set_user.c:361-382, 476-478; from-README, README.md:61-67].
Original `log_statement` / `log_line_prefix` are captured into `curr_state`
before the swap and restored on reset [verified-by-code, set_user.c:353-354, 420-421].

## Where it diverges from core idioms

- **Escalation, not emulation.** `supautils`/`pgextwlist` never change *who you
  are* — they run one command as the bootstrap superuser and re-own the result
  back. set_user changes the session's effective role for real, for the session's
  remaining lifetime, via core's `SetCurrentRoleId` [verified-by-code, set_user.c:473].
  It is the inverse security posture: controlled real escalation with a paper
  trail, versus fake-it-for-one-statement.
- **Positioned explicitly against `SET ROLE`.** Core `SET ROLE` is unlogged,
  freely and repeatedly reversible by the session, and cannot be gated by a
  command block-list. set_user reproduces the transition but (a) logs it, (b)
  can require a secret `token` to reverse it (`set_user('r','tok')` →
  `reset_user('tok')`, mismatch errors), and (c) actively **blocks `SET ROLE`
  and `SET SESSION AUTHORIZATION` themselves** while a transition is active, to
  stop the escaped session from side-stepping the audited path
  [verified-by-code, set_user.c:601-616; from-README, README.md:84-101].
- **The block-list as a security boundary.** While `curr_state` is active, the
  `ProcessUtility_hook` refuses `ALTER SYSTEM` (`T_AlterSystemStmt`),
  `COPY ... PROGRAM` (`T_CopyStmt` with `is_program`), and
  `SET log_statement` (`T_VariableSetStmt`) — the commands an escalated user
  would use to persist a backdoor or turn off the logging that is watching them
  [verified-by-code, set_user.c:576-620]. Because a determined user could reach
  the same GUCs through the `set_config()` SQL function rather than `SET`, a
  **second** hook (`object_access_hook`, `OAT_FUNCTION_EXECUTE`) blocks any
  function whose `prosrc` is `set_config_by_name`, maintaining an OID cache of
  such functions kept fresh on `OAT_POST_CREATE`/`OAT_POST_ALTER`
  [verified-by-code, set_user.c:719-755, 762-837]. Two enforcement surfaces for
  one policy is unusual and deliberate.
- **The "NOLOGIN superuser" hardening.** The intended deployment is: grant
  `set_user_u` to a non-superuser admin, then `ALTER ROLE postgres NOLOGIN` so
  the superuser becomes a role you can only `set_user_u` *into*, never connect
  *as* — closing the direct-login path that would bypass the enhanced logging
  entirely [from-README, README.md:159-167]. The extension doesn't enforce this;
  it's a configuration contract the README spells out (and warns must be audited
  for other login-capable superusers).
- **Deferred, transaction-scoped identity change.** Unlike the emulation cousins'
  synchronous switch-run-restore, set_user's swap is queued and applied by a
  `RegisterXactCallback` handler at `PRE_COMMIT`, with abort-safety built in
  [verified-by-code, set_user.c:454-506]. State lives in `TopMemoryContext`
  (`curr`/`pending`/`prev` triple) so it survives across statements within the
  session [verified-by-code, set_user.c:80-82, 286-289].
- **`set_session_auth`: the one-way trapdoor.** A separate function calls
  `_InitializeSessionUserId(newuser, InvalidOid)` — an irrevocable session-auth
  change (no reset, no superuser target), and it is compiled *out* under assert
  builds (`NO_ASSERT_AUTH_UID_ONCE`), erroring instead
  [verified-by-code, set_user.c:676-711; from-README, README.md:103-107]. With
  `exit_on_error` on it flips `ExitOnAnyError` so any failure FATALs the backend.

## Notable design decisions

- Role swap delegates to core's `SET ROLE` machinery, not a bespoke seccontext
  hack: `SetCurrentRoleId(userid, is_superuser)` [verified-by-code, set_user.c:473].
- Swap deferred to `XACT_EVENT_PRE_COMMIT`; hence `set_user()` is banned inside
  a transaction block [verified-by-code, set_user.c:232-238, 461-473].
- Superuser targets require the `set_user_u` entry point AND membership in
  `superuser_allowlist`; the single-arg `set_user` errors on a superuser target
  with hint "Use 'set_user_u' to escalate" [verified-by-code, set_user.c:326-339].
- Block-list enforced in the utility hook only while a transition is live
  (`curr_state != NULL && curr_state->userid != InvalidOid`)
  [verified-by-code, set_user.c:576-620].
- `SET ROLE` / `SET SESSION AUTHORIZATION` are themselves blocked mid-transition
  to force use of `reset_user()` [verified-by-code, set_user.c:601-616].
- Second enforcement surface: `object_access_hook` blocks `set_config_by_name`
  via a maintained OID cache, closing the function-call bypass of the `SET`
  block [verified-by-code, set_user.c:719-755, 800-837].
- Superuser escalation force-enables `log_statement = all` + an `AUDIT` prefix
  tag, guaranteeing a log record for everything the escalated session does
  [verified-by-code, set_user.c:361-382, 476-478].
- Optional reset `token` stored for the session lifetime and required (and
  string-compared) at `reset_user`, so a leaked session can't trivially unwind
  [verified-by-code, set_user.c:302-314, 398-415].
- Cross-extension coordination via a rendezvous-variable hook queue
  (`SET_USER_HOOKS_KEY`), letting other modules react to transitions
  [verified-by-code, set_user.h:12-42, set_user.c:644-666].
- All GUCs are `PGC_SIGHUP` so the security policy is fixed by the DBA in
  `postgresql.conf`, not tunable by the (possibly escalated) session
  [verified-by-code, set_user.c:515-548].

## Links into corpus

- Privilege-hook cluster: [[supautils]], [[pgextwlist]] — the *emulation*
  siblings; set_user is the *escalation* counterpart (real role assumption +
  block-list, vs. faked superuser for one command).
- [[pgaudit]] — the audit sibling set_user is designed to pair with (same
  `pgaudit` GitHub org); set_user produces the escalation log records, pgaudit
  the statement-level detail.
- `knowledge/idioms/process-utility-hook-chain.md` — the `ProcessUtility_hook`
  chaining pattern set_user uses for its block-list (`prev_hook` + shim macros).
- `knowledge/idioms/guc-variables.md` — the `DefineCustom*Variable` /
  `PGC_SIGHUP` surface backing the seven `set_user.*` GUCs.
- `knowledge/idioms/error-handling.md` — the `ereport(ERROR,
  ERRCODE_INSUFFICIENT_PRIVILEGE, ...)` guard idiom used at every block point.
- `knowledge/subsystems/tcop.md` — `ProcessUtility` / utility-statement
  dispatch, the layer the hook intercepts.
- `knowledge/subsystems/access-transam.md` — the `RegisterXactCallback` /
  `XactEvent` machinery driving the deferred swap and abort cleanup.

## Sources

- `https://raw.githubusercontent.com/pgaudit/set_user/main/README.md`
  @ ~23:16 UTC → 200 (791 lines; first attempt clobbered in shared scratchpad,
  refetched clean).
- `https://raw.githubusercontent.com/pgaudit/set_user/main/src/set_user.c`
  @ ~23:12 UTC → 200 after retry (initial attempts → 429 Too Many Requests;
  succeeded on backoff, 911 lines).
- `https://raw.githubusercontent.com/pgaudit/set_user/main/src/set_user.h`
  @ ~23:13 UTC → 200 (43 lines).
- `https://raw.githubusercontent.com/pgaudit/set_user/main/extension/set_user.sql`
  @ ~23:08 UTC → 200.
- `https://raw.githubusercontent.com/pgaudit/set_user/main/set_user.control`
  @ ~23:08 UTC → 200.
- `https://raw.githubusercontent.com/pgaudit/set_user/main/Makefile`
  @ ~23:08 UTC → 200.
- NOT fetched (gaps): `src/compatibility.h` (version-shim macros `_PU_HOOK`,
  `_prev_hook`, `_standard_ProcessUtility`, `_InitializeSessionUserId`,
  `NO_ASSERT_AUTH_UID_ONCE` — cited by call site only); `sql/` + `expected/`
  regression fixtures; `updates/*.sql` upgrade scripts.
