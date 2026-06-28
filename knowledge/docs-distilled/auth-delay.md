---
source_url: https://www.postgresql.org/docs/current/auth-delay.html
fetched_at: 2026-06-28T00:00:00Z
anchor_sha: 4abf411e2328
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — auth_delay (the ClientAuthentication_hook example)

`contrib/auth_delay` is the minimal example of `ClientAuthentication_hook`: it
sleeps before *reporting* a failed login, slowing online password brute-forcing.
A ~30-line module — the cleanest possible "wrap an auth hook" template.
`[from-docs]`

## The hook (verified against source)

- Saves the prior hook and installs its own on `_PG_init`:
  `original_client_auth_hook = ClientAuthentication_hook;
  ClientAuthentication_hook = auth_delay_checks;` at
  `source/contrib/auth_delay/auth_delay.c:73-74`. `[verified-by-code]`
- The wrapper delays **only on failure**: `if (status != STATUS_OK)
  pg_usleep(1000L * auth_delay_milliseconds);` (`auth_delay.c:45-47`) — successful
  authentication is never delayed. `[verified-by-code]` (It chains: any prior
  `ClientAuthentication_hook` runs first, per the comment at `:37`.)
- Must be in `shared_preload_libraries`. `[from-docs]`

## Configuration

- GUC `auth_delay.milliseconds` (int, default **0** —
  `static int auth_delay_milliseconds = 0;` `auth_delay.c:25`; defined at `:58`).
  `[verified-by-code]`

## The load-bearing limitation

- It does **not** stop a connection-slot-exhaustion DoS — the sleeping backends
  still hold their connection slots, so a flood of bad logins can *worsen* slot
  pressure. auth_delay raises the per-attempt cost of online guessing; it is a
  supplement, not a defense. `[from-docs]`

## Links into corpus

- `[[knowledge/docs-distilled/passwordcheck.md]]` — the other auth-policy hook
  example (password strength vs login throttling); same save-prev/install idiom.
- `[[knowledge/docs-distilled/sasl-authentication.md]]` — the SCRAM exchange whose
  `STATUS_OK`/`STATUS_ERROR` result auth_delay keys off.
- Skills: `bgworker-and-extensions` (hook installation), `gucs-config`.
