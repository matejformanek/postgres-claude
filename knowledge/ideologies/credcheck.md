# credcheck — a declarative credential-policy engine bolted onto the two auth hooks core left deliberately empty

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `MigOpsRepos/credcheck` @ branch `master` (`default_version = '5.1.0'`,
> `credcheck.control:2`). All `file:line` cites below point into THAT repo (not
> `source/`), since this doc characterizes an external extension's divergence
> from core idioms. Cites verified against blobs fetched 2026-07-11 (see Sources
> footer). Line numbers are for the `master` blobs as fetched.

credcheck turns the two hooks PostgreSQL core ships as empty function pointers —
`check_password_hook` and `ClientAuthentication_hook` — into a **DBA-configured
password/username policy engine driven entirely by ~40 GUCs**
(`credcheck.c:1817,1829`, 38 `DefineCustom*` calls) `[verified-by-code]`.
**Headline divergence:** core has a deliberate *no-password-policy* stance —
`src/backend/libpq/auth.c`'s `check_password_hook` is a hook precisely so the
server itself asserts nothing about credential complexity, and core actively
*prefers* client-side hashing (SCRAM/md5) so the plaintext never reaches the
server at all. credcheck inverts both: it asserts a large, opinionated policy
(length, character classes, reuse history, expiry, failed-login lockout), and to
do so it must *forbid* the client-side hashing core treats as the secure default
— rejecting any non-plaintext password unless a GUC re-enables it
(`credcheck.c:1716-1721`) `[verified-by-code]`. It is `contrib/passwordcheck` +
`contrib/auth_delay` fused and maximalized, plus a shmem/WAL layer neither core
module has.

## Domain & purpose

The extension "provides few general credential checks, which will be evaluated
during the user creation, during the password change and user renaming"
(`README.md:22`) `[from-README]`. Its rule menu: allow/reject credential sets,
"deny password that can be easily cracked" (optional cracklib), enforce a
minimum `VALID UNTIL`, a password-reuse policy, a failed-authentication ban
count, force-change-on-first-login, and expiry warnings (`README.md:24-31`)
`[from-README]`. The default configuration enforces *nothing* — "will not
enforce any complex checks and will try to allow most of the credentials"; every
rule is a GUC a superuser dials up, changeable only by a superuser
(`README.md:33`) `[from-README]`. It is the credential-policy sibling of the
privilege-hook cluster (`[[set_user]]`, `[[supautils]]`): those govern *who you
can become*; credcheck governs *what secret lets you in*.

## How it hooks into PG

`_PG_init` (`credcheck.c:1726-1833`) installs **six** hooks, chaining each prior
value `[verified-by-code]`:

- `check_password_hook = check_password` (`:1817`) — the complexity/reuse gate,
  the canonical `contrib/passwordcheck` slot.
- `ClientAuthentication_hook = credcheck_max_auth_failure` (`:1829`) — the
  failed-login lockout + optional auth delay, the `contrib/auth_delay` slot.
- `ProcessUtility_hook = cc_ProcessUtility` (`:1815`) — intercepts
  `CREATE/ALTER ROLE … RENAME` and the force-change-password / valid-until DDL
  paths (`:1850-2225`) `[verified-by-code]`.
- `shmem_request_hook`/`shmem_startup_hook` (`:1819-1823`) — allocate the two
  shared-memory areas.
- `emit_log_hook = fix_log` (`:1825-1826`) — masks `PASSWORD '…'` literals in
  every log line when `no_password_logging` is on (`:3144-3163`)
  `[verified-by-code]`.
- `ExecutorStart_hook = cc_ExecutorStart` (`:1831-1832`) — first-login
  enforcement.

**The GUC surface** is the extension's real body: 38 `DefineCustom*Variable`
calls (`credcheck.c` grep). The complexity/policy knobs
(`username_min_*`, `password_min_*`, `password_reuse_history/interval`,
`password_valid_until`, `password_change_first_login`, `whitelist`) are all
**`PGC_SUSET`** — superuser-set, per-session tunable but not user-settable
(`:806-956,1750-1792`) `[verified-by-code]`. Structural knobs that size shmem
(`history_max_size`, `auth_failure_cache_size`) are `PGC_POSTMASTER` and only
defined under `shared_preload_libraries` (`:1732-1742`) `[verified-by-code]`;
`reset_superuser` and `auth_delay_ms` are `PGC_SIGHUP` (`:1762-1787`)
`[verified-by-code]`. Two prefixes are reserved: `MarkGUCPrefixReserved`
for both `"credcheck"` and `"credcheck_internal"` (`:1808-1809`)
`[verified-by-code]`.

**Failed-login state lives in shared memory**, not per-backend and not in a
catalog: a `ShmemInitHash` keyed by `roleid` (`pgaf_hash`, `:2640`) guarded by an
LWLock from a named tranche `credcheck_auth_failure` (`:1804-1806`)
`[verified-by-code]`. The `ClientAuthentication_hook` increments the count under
`LW_EXCLUSIVE` on `STATUS_ERROR` and, once `fail_num >= fail_max`,
`ereport(FATAL, …"user '%s' has been banned")` (`:3208-3221`)
`[verified-by-code]`. This cache is memory-only and lost at restart by design —
"I have not seen the interest to restore the cache at startup" (`README.md:372`)
`[from-README]`. The **password-reuse history**, by contrast, is a *second*
shmem area (`pgph_hash`, tranche `credcheck_history`, `:2384,1803-1804`) that is
persisted to `$PGDATA/pg_password_history` and — on PG ≥ 15 — replicated to
standbys via a **custom WAL resource manager** `RM_CREDCHECK_ID = 150`
registered with `RegisterCustomRmgr` (`credcheck.c:106,156,1746`;
`README.md:279`) `[verified-by-code]` `[from-README]`.

## Where it diverges from core idioms

### 1. Policy-as-GUC vs. core's deliberate no-password-policy stance

Core ships `check_password_hook` as a *nul* pointer and `contrib/passwordcheck`
as a minimal example precisely so the backend itself makes no complexity
assertion — password policy is intentionally left to an out-of-tree module.
credcheck fills that void with an entire policy language expressed as ~30
`PGC_SUSET` GUCs (`credcheck.c:806-956`) `[verified-by-code]`, converting a
hook-shaped hole into Oracle-profile-style credential rules. The divergence is
not mechanism but *stance*: core declines to have an opinion; credcheck is
nothing but the opinion.
Cross-ref `[[knowledge/idioms/guc-variables.md]]`,
`[[knowledge/subsystems/contrib-passwordcheck.md]]`.

### 2. It must defeat client-side hashing to see what core hides

`check_password` switches on `PasswordType`: only `PASSWORD_TYPE_PLAINTEXT` is
inspected; the `default` case (any pre-hashed md5/SCRAM verifier) is *rejected*
unless `encrypted_password_allowed` — `ereport(ERROR … "password type is not a
plain text")` (`credcheck.c:1690-1721`) `[verified-by-code]`. This is the
load-bearing tension: core lets a client hash a password *before* it leaves the
client (SCRAM, `md5`, and psql's `\password`) so the server — and therefore the
hook — never sees the secret. A complexity check on a hash is impossible, so
credcheck's only recourse is to *forbid the secure client-side path*, forcing
plaintext transmission so its policy can run. The README states the limitation
flatly: "This extension only works for the plain text passwords" and warns it
"also affect the `\password` psql command as it sends encrypted password"
(`README.md:530,548`) `[from-README]`. This is a genuine security tradeoff the
policy engine cannot avoid, and the mirror image of `[[pg_tle]]`'s passcheck,
which runs user SQL inside the same hook but inherits the identical
plaintext-only constraint.

### 3. ClientAuthentication lockout as shmem-resident mutable auth state

Core's `ClientAuthentication_hook` is used by `contrib/auth_delay` only to
`pg_usleep` after a failure — it holds *no* state. credcheck keeps a live,
LWLock-protected shmem hash of per-role failure counters and turns the hook into
a stateful lockout: increment on failure, `FATAL`-reject once the count reaches
`max_auth_failure`, reset the counter on a clean login
(`credcheck.c:3199-3227`) `[verified-by-code]`. It even bundles auth_delay's own
behavior via `auth_delay_ms` (`:3187-3188`) `[verified-by-code]`, making
credcheck a strict superset of that contrib module. The one hard-coded seam: a
banned **superuser** (Oid `10`) can be un-banned by setting `reset_superuser`
and reloading (`:3218-3219`) `[verified-by-code]` — a deliberate lockout escape
so an over-aggressive policy can't brick the cluster.

### 4. An extension that owns a WAL resource manager and two LWLock tranches

Most policy hooks are stateless C. credcheck reaches into three shmem/durability
surfaces core reserves for the backend itself: two named LWLock tranches
(`credcheck_history`, `credcheck_auth_failure`, `credcheck.c:94-95,1804-1806`),
a `ShmemInitStruct`/`ShmemInitHash` pair for each (`:2371-2384,2627-2640`), and a
**custom WAL rmgr** (`RM_CREDCHECK_ID = 150`) whose `XLogInsert` calls ship every
history mutation — add/remove/rename/reset/timestamp — to standbys
(`:106,984-1065,1746`) `[verified-by-code]`. So a password-reuse policy becomes a
replicated, crash-durable, WAL-logged subsystem — a far heavier footprint than
`[[set_user]]`'s `TopMemoryContext` state or `[[pg_tle]]`'s catalog rows.
Cross-ref `[[knowledge/idioms/lwlock-rank-discipline.md]]`,
`[[knowledge/idioms/wal-record-construction.md]]`.

## Notable design decisions (cited)

- **Reuse history stores SHA-256 of the plaintext, never the plaintext.** Each
  reuse path hashes via `str_to_sha256(password, username)` before storing or
  comparing (`credcheck.c:1285,1580,1593`; `README.md:279`) `[verified-by-code]`
  `[from-README]` — the username is the salt, so identical passwords across
  users don't collide.
- **All policy GUCs are `PGC_SUSET`; only shmem-sizing ones are
  `PGC_POSTMASTER`.** Policy is superuser-tunable at runtime, but the
  memory footprint is fixed at startup (`credcheck.c:806-956` vs `:1734-1742`)
  `[verified-by-code]`.
- **Log-scrubbing via `emit_log_hook`.** `no_password_logging` (default `true`)
  masks `PASSWORD '…'` literals across `message`/`detail`/`detail_log`/
  `context`/`internalquery` at every elevel (`credcheck.c:3144-3163`)
  `[verified-by-code]` — core would otherwise log the DDL statement verbatim,
  plaintext included.
- **Version-straddle for the shmem-request API.** Under PG ≥ 15 it uses
  `shmem_request_hook` + `MarkGUCPrefixReserved`; under < 15 it calls
  `RequestAddinShmemSpace` directly in `_PG_init` and uses
  `EmitWarningsOnPlaceholders` (`credcheck.c:1794-1811,2320-2330`)
  `[verified-by-code]`.
- **Username checks silently no-op without a password.** `CREATE USER … ` (no
  password) and rename of a passwordless role skip the username policy, because
  the check rides the password hook (`README.md:550-560`) `[from-README]`.
- **Whitelist escape hatches.** `credcheck.whitelist` (skip password policy) and
  `credcheck.whitelist_auth_failure` (skip lockout) are comma-lists checked by
  `is_in_whitelist` at the top of each hook (`credcheck.c:1698-1699,3191`)
  `[verified-by-code]`.

## Links into corpus

- `[[knowledge/subsystems/contrib-passwordcheck.md]]` — core's canonical
  `check_password_hook` example; credcheck is its maximalist superset (§1).
- `[[knowledge/subsystems/contrib-auth_delay.md]]` — the *only* other
  `ClientAuthentication_hook` user in core; credcheck subsumes its `pg_usleep`
  delay (`auth_delay_ms`, §3).
- `[[knowledge/ideologies/pg_tle.md]]` — same two auth hooks, but pg_tle
  dispatches user SQL into them (inheriting the identical plaintext-only
  constraint); credcheck is the pure-C declarative-GUC counterpart.
- `[[knowledge/ideologies/set_user.md]]` / `[[knowledge/ideologies/supautils.md]]`
  / `[[knowledge/ideologies/pgaudit.md]]` — the privilege/audit-policy cluster:
  they govern role escalation/emulation and statement capture; credcheck governs
  the credential itself. All are `PGC_SUSET`/`PGC_SIGHUP`-driven, superuser-fixed.
- `[[knowledge/idioms/guc-variables.md]]` — the `DefineCustom*Variable` /
  `MarkGUCPrefixReserved` surface that *is* credcheck's body.
- `[[knowledge/idioms/process-utility-hook-chain.md]]` — `cc_ProcessUtility`
  intercepting `ALTER ROLE … RENAME` / force-change DDL.
- `[[knowledge/idioms/lwlock-rank-discipline.md]]`,
  `[[knowledge/idioms/wal-record-construction.md]]` — the two shmem tranches and
  the custom `RM_CREDCHECK_ID` WAL rmgr (§4).
- `.claude/skills/gucs-config/SKILL.md`,
  `.claude/skills/extension-development/SKILL.md`,
  `.claude/skills/wal-and-xlog/SKILL.md` — GucContext + `MarkGUCPrefixReserved`,
  `_PG_init` chained-hook install, and custom resource-manager registration.

## Anthropology takeaway

credcheck is the corpus's cleanest example of an extension whose entire value is
*supplying the opinion core deliberately withholds*. Where `[[pg_dirtyread]]`
removes a core invariant and `[[pg_tle]]` reimplements a subsystem against a new
substrate, credcheck fills two intentionally-empty hook slots
(`check_password_hook`, `ClientAuthentication_hook`) with a full credential-policy
engine expressed almost entirely as GUCs. Two patterns worth a corpus note: (a)
the auth-hook plaintext trap — *any* server-side credential-complexity check must
forbid client-side hashing (`credcheck.c:1716-1721`), a security tradeoff shared
verbatim with pg_tle passcheck and worth flagging to anyone auditing why a
managed cluster disabled SCRAM; and (b) a policy hook that grows a *replicated,
WAL-logged, shmem-resident* state layer (custom rmgr `RM_CREDCHECK_ID = 150`, two
LWLock tranches) — a reminder that "just a hook" can quietly acquire the full
durability footprint of a core subsystem.

## Sources

All fetched 2026-07-11, branch `master`, via
`https://raw.githubusercontent.com/MigOpsRepos/credcheck/master/<path>`:

- `README.md` — 200 (588 lines; description, reuse policy, auth-failure ban,
  plaintext limitation — read for domain/purpose + caveats).
- `credcheck.c` — 200 (3628 lines; the whole extension — `_PG_init`, both auth
  hooks, GUC definitions, shmem/WAL history, `fix_log` masking — deep-read of the
  hook install, `check_password`, `credcheck_max_auth_failure`, GUC blocks).
- `credcheck.control` — 200 (4 lines; `default_version = '5.1.0'`,
  `relocatable = false`).
- `Makefile` — 200 (30 lines; `MODULE_big = credcheck`, single `OBJS =
  credcheck.o`, optional cracklib, `REGRESS`/`TAP_TESTS` — confirms the whole
  C surface is one file).

404 gaps (probed, absent): `username_check.c`, `password_check.c` (logic is
inlined in `credcheck.c`, not split), `META.json`. GitHub tree/API blocked this
run, so no directory listing was fetched; the `sql/`, `updates/`, `test/`, and
`event_trigger.sql` artifacts named by the Makefile were not fetched — they are
install scripts and fixtures, not behavioral C. All cites are
`[verified-by-code]` against the fetched `credcheck.c`/`.control`/`Makefile`
except the purpose/limitation narrative and the "history is memory-only /
sha256 / replication-aware" prose, tagged `[from-README]`.
