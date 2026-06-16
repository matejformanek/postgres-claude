---
path: src/port/pg_strong_random.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 179
depth: deep
---

# src/port/pg_strong_random.c

## Purpose

Generates cryptographically-secure random bytes via `pg_strong_random(void
*buf, size_t len)`. "Strong" here means suitable for security-sensitive uses:
SCRAM salts and nonces, query-cancel keys, RADIUS authenticators,
`gen_random_uuid()` (uuid v4/v7), and TLS-adjacent material. The file is
deliberately built so it can run **very early** in postmaster/backend startup —
the header comment stresses it "cannot rely on backend infrastructure such as
`elog()` or `palloc()`" (`pg_strong_random.c:11-13`). Compiled into both
frontend and backend libpgport. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `void pg_strong_random_init(void)` | three arms: `:60`, `:108`, `:140` | No-op on every supported source; retained only for extension ABI compatibility |
| `bool pg_strong_random(void *buf, size_t len)` | `:62` / `:122` / `:151` | Returns `false` if no source was available — **caller MUST check** |

## Internal landmarks

Three mutually-exclusive backends, selected by build config:

1. **`USE_OPENSSL`** (`pg_strong_random.c:54-90`) — `RAND_bytes()`. Before
   drawing, loops up to `NUM_RAND_POLL_RETRIES` (8) calling `RAND_poll()`
   until `RAND_status() == 1`, i.e. the CSPRNG is sufficiently seeded
   (`:78-90`). If it never seeds, `RAND_bytes()` is still attempted and its
   failure propagates to the caller.
2. **`WIN32`** (`:92-135`) — `CryptAcquireContext` (cached in a process-global
   `hProvider`, freed only at process exit) + `CryptGenRandom()`.
3. **Fallback** (`:137-179`) — opens `/dev/urandom`, `read()`s in a loop
   handling short reads and `EINTR`, closes the fd. Returns `false` on any open
   or read failure.

## Invariants & gotchas

- **The return value is load-bearing.** The header comment warns explicitly:
  "Proceeding with key generation when no random data was available would lead
  to predictable keys and security issues" (`pg_strong_random.c:42-45`). Every
  caller must branch on `false`.
- `pg_strong_random_init()` is a no-op everywhere; its existence is purely
  backward-compat for extensions that learned to call it (`:33-36`).
- Distinct from `pg_prng_*` (the xoshiro non-cryptographic PRNG): A5 flagged
  that DSM control-handle generation uses `pg_prng_uint32`, *not* this. Use the
  right one — this file is the CSPRNG.

## Potential issues

- **[ISSUE-leak: /dev/urandom fd opened without O_CLOEXEC]**
  `pg_strong_random.c:159` — the fallback arm does
  `open("/dev/urandom", O_RDONLY, 0)` with no `O_CLOEXEC`. The fd is `close()`d
  on the normal path (`:175`), so this is not a descriptor *leak* within the
  process, but for the window it is open it would be inherited by any `exec()`
  that occurred concurrently. In practice the postmaster's
  security-sensitive draws happen at fork-not-exec points, so severity is low;
  noting for completeness alongside the secret-scrub theme. Severity: nit. See
  `knowledge/issues/port.md`.

## Cross-refs

- `knowledge/files/src/port/explicit_bzero.c.md` — scrub the buffer after use.
- `knowledge/files/src/backend/utils/adt/uuid.c.md` — `gen_random_uuid` consumer.
- `knowledge/idioms/error-handling.md` — why this file avoids `elog`.

<!-- issues:auto:begin -->
- [Issue register — `port`](../../../issues/port.md)
<!-- issues:auto:end -->
