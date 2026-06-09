# Issues — `contrib/auth_delay`

Per-subsystem issue register for **auth_delay**, the brute-force-
mitigation extension that adds artificial sleep on failed
authentication. 1 source file / 75 LOC. Tiny but security-explicit.

**Parent doc:** `knowledge/files/contrib/auth_delay/auth_delay.c.md`.

**Source:** 6 entries surfaced 2026-06-09 by A12-4.

## Headlines

1. **Failure-only delay = deliberate timing oracle.** `pg_usleep`
   fires only when `status != STATUS_OK`. A network observer
   measuring round-trip time on auth attempts can distinguish
   "wrong password" (slow) from "right password" (fast). The
   upstream design accepts the oracle in exchange for the brute-
   force mitigation benefit.

2. **No per-IP, no per-user, no rate-limit, no jitter.** One global
   timeout; a single attacker can flood failed-auth attempts in
   parallel from one IP and degrade global auth latency uniformly.

3. **35-minute upper bound** on `auth_delay.milliseconds`
   (INT_MAX/1000) combined with `PGC_SIGHUP` reloadability =
   notable DoS amplifier for legitimate auth-failure callers, even
   though the role required to set it is already superuser-level.

4. **Activation gate**: `shared_preload_libraries` required.
   `_PG_init` chains `ClientAuthentication_hook`; sleep runs in the
   forked backend (not the postmaster), so other connections aren't
   blocked.

## Cross-sweep references

- **A2 libpq SCRAM/SCRAM-passthrough** + **auth_delay** — the
  combined story for "how PG defends against credential brute
  force" is incomplete (auth_delay is a deliberate trade-off).
- **A11 postgres_fdw `password_required`** — same authentication-
  failure surface but at FDW layer.

## Entries (6)

- [ISSUE-security: failure-only delay creates a deliberate timing
  oracle distinguishing wrong-password from right-password (likely
  — by design)] — `source/contrib/auth_delay/auth_delay.c` —
  `pg_usleep(1000L * auth_delay.milliseconds)` only fires on
  `status != STATUS_OK`.
- [ISSUE-defense-in-depth: no per-IP / per-user / per-database
  rate-limiting; one global timeout (likely)].
- [ISSUE-defense-in-depth: no jitter — deterministic timing makes
  the oracle precise even under network noise averaging (nit)].
- [ISSUE-defense-in-depth: 35-minute upper bound on
  `auth_delay.milliseconds` combined with PGC_SIGHUP = DoS
  amplifier for legitimate auth callers (nit)].
- [ISSUE-defense-in-depth: ineffective without
  `shared_preload_libraries=auth_delay`; no startup warning if
  configured but not loaded (nit)].
- [ISSUE-documentation: README does not explicitly acknowledge the
  failure-only-delay timing oracle (nit)].
