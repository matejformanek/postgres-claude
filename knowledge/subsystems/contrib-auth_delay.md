# contrib-auth_delay (brute-force authentication delay)

- **Source path:** `source/contrib/auth_delay/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Loading model:** `shared_preload_libraries` (no `.control` file)
- **Surface:** zero SQL functions; one GUC; one hook installed

## 1. Purpose

Inject a configurable delay AFTER a failed authentication attempt
to slow brute-force credential-guessing attacks. The smallest
contrib extension in the tree — 75 LOC total [verified-by-code
`wc -l source/contrib/auth_delay/auth_delay.c`].

Installs `ClientAuthentication_hook` and, on `status != STATUS_OK`
(authentication failed), calls `pg_usleep` for the configured
milliseconds. Successful authentications get no delay.

## 2. The mechanism

```c
static void
auth_delay_checks(Port *port, int status)
{
    if (original_client_auth_hook)
        original_client_auth_hook(port, status);

    if (status != STATUS_OK)
        pg_usleep(1000L * auth_delay_milliseconds);
}
```

[verified-by-code `auth_delay.c:35-50`]

The hook fires after the authentication exchange completes —
success, failure, or timeout. If failed, the backend sleeps in
this hook **before** responding to the client. The client sees
"the connection took 5 seconds and then was rejected" rather than
"the connection was rejected instantly."

## 3. Why slow brute-force matters

A brute-force credential attack tries thousands of passwords per
minute. With auth_delay = 5000 (5 seconds), the attack rate drops
to 12 attempts/minute per backend connection. Spread across
limited concurrent connections, the effective rate falls to <1
attempt/second cluster-wide.

This doesn't STOP an attacker; it makes the attack expensive enough
that other detection (failed-login monitoring, fail2ban-style IP
banning) has time to react.

## 4. The single GUC

```c
static int auth_delay_milliseconds = 0;
```

[verified-by-code `auth_delay.c:25`]

`auth_delay.milliseconds` — integer, bounded [0, INT_MAX]. Default
0 (no delay). Registered in `_PG_init`.

The unit is **milliseconds**. Common values:
- 500 ms — barely noticeable to legitimate users typing a wrong
  password; halves attack rate.
- 5000 ms — significant for legitimate users; 10× attack-rate
  reduction.
- 30000 ms — production-paranoid; 60× reduction but legitimate
  user errors become painful.

## 5. The hook installation

```c
original_client_auth_hook = ClientAuthentication_hook;
ClientAuthentication_hook = auth_delay_checks;
```

[verified-by-code `auth_delay.c:73-74`]

The canonical hook-chain pattern. Multiple modules using
`ClientAuthentication_hook` all observe authentication outcomes.

## 6. What this does NOT do

- **Doesn't limit connection rate.** A determined attacker opens N
  parallel connections and sees N delays in parallel; rate scales
  with concurrency.
- **Doesn't block IPs.** Use `pg_hba.conf` IP rules + external
  fail2ban for that.
- **Doesn't notify on failure.** Use `log_connections=on`
  + `log_failed_authentications` for that.
- **Doesn't differentiate between attack types.** Wrong password
  / wrong username / wrong-cluster-secret all get the same delay.

It's a **single-knob defense-in-depth** measure, not a complete
authentication-security solution.

## 7. The `Port *` argument

[verified-by-code `auth_delay.c:33`]

The hook receives a `Port *` containing connection metadata
(client IP, database name, SSL state, etc.). The default callback
doesn't use it, but a derived extension could implement
per-source-IP delays or graduated delays based on the failure
type.

## 8. Production-use guidance

- **Load via `shared_preload_libraries`**. The hook must be
  installed before the first authentication attempt.
- **Start at 500 ms** in production. Measure user complaints
  before raising. Most "wrong password, retried successfully"
  events involve a 1-2 second human reaction time anyway.
- **Pair with `log_failed_authentications=on`** so SOC tooling
  observes the rate of failed attempts.
- **Pair with `pg_hba.conf` IP restrictions** as the primary
  defense. auth_delay is a layer, not the only layer.
- **Don't apply to internal-network applications.** Application
  servers reconnecting after a transient password rotation will
  hit the full delay on every connection attempt during the
  rotation window.

## 9. Invariants

- **[INV-1]** Delay applies ONLY on `status != STATUS_OK`.
- **[INV-2]** Hook chain via `original_client_auth_hook`
  preserved.
- **[INV-3]** GUC is in milliseconds, not seconds.
- **[INV-4]** No SQL surface; activation via
  `shared_preload_libraries`.
- **[INV-5]** Per-backend; parallel connections see parallel
  delays.

## 10. Useful greps

- The hook installation:
  `grep -n 'ClientAuthentication_hook\|auth_delay_checks' source/contrib/auth_delay/auth_delay.c`
- The GUC:
  `grep -n 'auth_delay_milliseconds' source/contrib/auth_delay/auth_delay.c`
- The fire site:
  `grep -n 'ClientAuthentication_hook' source/src/backend/libpq/auth.c`

## 11. Cross-references

- `.claude/skills/bgworker-and-extensions/SKILL.md` —
  shared_preload_libraries loading + hook installation pattern.
- `.claude/skills/gucs-config/SKILL.md` —
  `DefineCustomIntVariable` for the GUC.
- `knowledge/subsystems/contrib-passwordcheck.md` — companion
  auth-path contrib; the two install different auth hooks.
- `source/src/backend/libpq/auth.c` — fires
  `ClientAuthentication_hook` after the auth exchange.
- `source/src/include/libpq/auth.h` — hook type declaration.
- `source/contrib/auth_delay/auth_delay.c` — full 75-LOC
  implementation.
