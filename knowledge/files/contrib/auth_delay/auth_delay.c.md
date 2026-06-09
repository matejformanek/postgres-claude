# auth_delay.c

## One-line summary

A 75-line `shared_preload_libraries` extension that sleeps `auth_delay.milliseconds` after **every failed** authentication attempt, to slow brute-force password guessing — installed by chaining `ClientAuthentication_hook`. Source pin `4b0bf0788b0`.

## Public API / entry points

- `_PG_init(void)` — module load callback; defines GUC and chains the hook. `source/contrib/auth_delay/auth_delay.c:54-75` [verified-by-code]
- `auth_delay_checks(Port *port, int status)` — static hook callback; the only non-trivial code in the module. `source/contrib/auth_delay/auth_delay.c:33-49` [verified-by-code]
- `PG_MODULE_MAGIC_EXT(.name = "auth_delay", .version = PG_VERSION)` — standard module magic. `source/contrib/auth_delay/auth_delay.c:19-22` [verified-by-code]

## Key invariants

- **Activation is opt-in via `shared_preload_libraries`.** Nothing in the source loads the module on demand; if not preloaded, the hook is never installed and there is *no delay at all*. `source/contrib/auth_delay/auth_delay.c:73-74` [verified-by-code]
- **Hook chaining preserves prior callback.** The previous `ClientAuthentication_hook` is captured at `_PG_init` time and invoked before the delay logic, so auth_delay composes with other hook users. `source/contrib/auth_delay/auth_delay.c:28, 39-40, 73-74` [verified-by-code]
- **Delay is FAILURE-ONLY.** The sleep only fires when `status != STATUS_OK`. Successful authentications are not delayed. `source/contrib/auth_delay/auth_delay.c:45-48` [verified-by-code]
- **GUC `auth_delay.milliseconds` is `PGC_SIGHUP`.** Changeable by `pg_reload_conf()` / SIGHUP; no restart required to retune the delay. `source/contrib/auth_delay/auth_delay.c:64` [verified-by-code]
- **GUC range is `[0, INT_MAX/1000]`.** Upper bound `INT_MAX/1000 ≈ 2_147_483` ms ≈ 35.8 minutes. This is the cap on a single delay. `source/contrib/auth_delay/auth_delay.c:63` [verified-by-code]
- **GUC namespace is reserved.** `MarkGUCPrefixReserved("auth_delay")` prevents typos in `auth_delay.*` from silently becoming custom placeholders. `source/contrib/auth_delay/auth_delay.c:70` [verified-by-code]

## Notable internals

- The sleep call: `pg_usleep(1000L * auth_delay_milliseconds)`. `pg_usleep` takes microseconds; multiplying ms by 1000 gives µs. `source/contrib/auth_delay/auth_delay.c:47` [verified-by-code]
- GUC flag `GUC_UNIT_MS` — postgresql.conf can use unit suffixes (`'2s'`, `'500ms'`). `source/contrib/auth_delay/auth_delay.c:65` [verified-by-code]
- Default value is `0` — module loaded but inactive is a no-op (calls `pg_usleep(0)`, which on most platforms is effectively a yield). `source/contrib/auth_delay/auth_delay.c:62-63` [verified-by-code]
- Module performs **no per-IP, per-user, or per-database accounting** — the delay is unconditional global on every failed auth. [verified-by-code, by inspection of the 75-line module]

## Trust boundary / Phase D surface

**Activation gate.** The module is harmless unless explicitly added to `shared_preload_libraries`. Once loaded:

- **Hook installation timing.** Hook chain is set in `_PG_init`, which runs in the postmaster process before forking client backends. Every backend inherits the chained hook via fork. `source/contrib/auth_delay/auth_delay.c:73-74` [verified-by-code]
- **GUC change discipline.** `PGC_SIGHUP` means an attacker who can edit `postgresql.conf` (file-write on the data dir, or already-superuser via `ALTER SYSTEM`) can set `auth_delay.milliseconds` to its `INT_MAX/1000` cap. The cap is ~35 min — long enough to DoS legitimate auth retries by triggering one failed login on a shared account; not long enough to permanently wedge. `source/contrib/auth_delay/auth_delay.c:63-64` [verified-by-code]
- **Sleep mechanism: `pg_usleep`.** Per src/port/pgsleep.c (cross-reference), `pg_usleep` on backends is interruptible by signal — but since this is called inside the auth path, the connection has not yet been promoted to a full backend and SIGTERM/cancel are not generally delivered until after auth completes. **The sleep effectively pins the auth-worker for up to ~35 minutes per failed attempt.** [inferred from `pg_usleep` semantics + ClientAuthentication position in startup path]
- **Branch on auth failure (THE KEY POLICY QUESTION).** Only failures are delayed: `if (status != STATUS_OK) { pg_usleep(...) }`. **This is a timing-oracle design.** A network attacker can probe `username@db` pairs and learn from response time whether the username/auth_method succeeded or failed — modulo network jitter. The README (not shown here) documents this is a brute-force mitigation, but it intentionally accepts the side-channel. `source/contrib/auth_delay/auth_delay.c:45-48` [verified-by-code] `[ISSUE-defense-in-depth: failure-only delay is a deliberate timing oracle that distinguishes wrong-password from right-password by response time; defenders who want to hide that should delay successful auth too (maybe)]`
- **No per-IP / per-user differentiation.** A single attacker can saturate the auth path globally, and a flood of bogus logins on user A degrades latency for user B's legitimate failures equally. There is no rate-limiter, no token-bucket, no per-source-IP backoff. `[ISSUE-defense-in-depth: no per-source-IP escalation; trivial to DoS the auth queue with parallel failed connections from one attacker IP (maybe)]`
- **Client-side timeout interaction.** With `auth_delay.milliseconds = 2000` and a client using `connect_timeout=5` (libpq default 0 = none), the connection is held open by the server for the full sleep before returning the auth error. A misconfigured client with `tcp_user_timeout` shorter than `auth_delay.milliseconds` will drop the connection on the server's side without ever seeing the FATAL response. `[ISSUE-documentation: interaction with client connect_timeout / tcp_user_timeout is undocumented in the README (nit)]`
- **Postmaster-thread question.** Backend authentication runs in the forked-child backend, not in postmaster itself, so `pg_usleep` here does NOT block other connections (each connect is a separate process). The postmaster's accept loop keeps spinning. [inferred from PG fork-per-connect model; cross-ref `postmaster/postmaster.c` `BackendStartup`] `[ISSUE-correctness: would be a critical bug if the delay ran in postmaster — verify by cross-checking ClientAuthentication_hook call-site (likely nit, but worth a comment)]`
- **No randomized jitter.** Two consecutive failed auths from the same IP get exactly the same delay. A side-channel attacker can subtract the known constant `auth_delay.milliseconds` from each measurement to recover the underlying timing signal. `[ISSUE-defense-in-depth: deterministic delay is subtractable; adding random jitter ∈ [0, milliseconds] would make timing attacks harder (maybe)]`

## Cross-references

- `source/src/backend/libpq/auth.c` — `ClientAuthentication()` is the call-site that fires the chained hook; sets `status` to `STATUS_OK` or `STATUS_ERROR` before calling the chain.
- `source/src/include/libpq/auth.h` — declares `ClientAuthentication_hook_type` and the global hook pointer.
- `source/src/backend/postmaster/postmaster.c` — `BackendStartup` forks a child that eventually calls `ClientAuthentication`; the fork-per-connect model is why this module's sleep is per-connection, not per-postmaster.
- `source/src/port/pgsleep.c` — `pg_usleep` implementation; signal handling.
- Prior sweep A2 (libpq SSL/SCRAM) — auth hook fires AFTER any SCRAM exchange, so SCRAM iteration count + auth_delay compound when guessing.

## Issues spotted

- `[ISSUE-defense-in-depth: failure-only delay is a deliberate timing oracle distinguishing wrong-password from right-password by response time (maybe)]`
- `[ISSUE-defense-in-depth: no per-source-IP rate-limiting / backoff escalation; trivial parallel-flood DoS of auth queue (maybe)]`
- `[ISSUE-defense-in-depth: deterministic delay (no jitter) is subtractable by a timing attacker (maybe)]`
- `[ISSUE-documentation: interaction with client connect_timeout / TCP user-timeout is undocumented in README (nit)]`
- `[ISSUE-audit-gap: no logging — silently sleeping on every failure leaves no signal of brute-force in progress for fail2ban-style log scrapers; relies on caller's own `log_connections=on` (maybe)]`
- `[ISSUE-api-shape: 75 lines of code is fine, but no public C API to chain a same-pattern "delay on successful auth" or "delay on specific error codes" — extending this requires a fork (nit)]`
