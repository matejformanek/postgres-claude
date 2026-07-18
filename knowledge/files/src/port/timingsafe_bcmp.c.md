---
path: src/port/timingsafe_bcmp.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 43
depth: deep
---

# src/port/timingsafe_bcmp.c

## Purpose

Provides `timingsafe_bcmp(const void *b1, const void *b2, size_t n)` — a
**constant-time** memory comparison returning 0 iff the two buffers are equal,
nonzero otherwise. Unlike `memcmp`, its execution time does not depend on the
position of the first differing byte, so it does not leak, via a timing side
channel, *how much* of a secret a guess matched. Used for comparing
authentication tags / MACs / tokens where an early-exit `memcmp` would be a
Brumley-style timing oracle. Imported from OpenBSD (Damien Miller, 2010);
compiled into libpgport only where libc lacks it. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int timingsafe_bcmp(const void *b1, const void *b2, size_t n)` | `timingsafe_bcmp.c:27` | 0 = equal; nonzero = differ. Compares all `n` bytes unconditionally |

## Internal landmarks

- **`USE_SSL` arm** (`timingsafe_bcmp.c:31`) — delegates to OpenSSL's
  `CRYPTO_memcmp()`, which carries the same constant-time contract.
- **Portable arm** (`:33-41`) — accumulates `ret |= *p1++ ^ *p2++` across the
  full length with no early break, then returns `ret != 0`. The XOR-OR fold is
  the canonical constant-time-equality construction.

## Invariants & gotchas

- **Never short-circuits.** The loop always runs `n` iterations; that is the
  entire point. Do not "optimize" it with an early `break`.
- Returns a boolean-ish result (equal / not-equal), **not** an ordering like
  `memcmp`. It cannot be used for sorting.
- The A11 pgcrypto sweep found raw HMAC tags compared with SQL `=` (timing-
  attackable at the SQL layer); this primitive is the C-level answer for tag
  comparison inside the backend, and pairs with that finding
  (`knowledge/issues/pgcrypto.md`).

## Cross-refs

- `knowledge/issues/pgcrypto.md` — non-constant-time comparison findings (A11).
- `knowledge/files/src/port/pg_strong_random.c.md` — sibling crypto primitive.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
