---
path: src/port/explicit_bzero.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 73
depth: deep
---

# src/port/explicit_bzero.c

## Purpose

Provides `explicit_bzero(void *buf, size_t len)` — a memory-zeroing call that
the compiler is **not** allowed to elide as a dead store. Ordinary `memset(p,
0, n)` immediately before a buffer goes out of scope is a classic
dead-store-elimination target; the optimizer legally removes it, leaving
secrets (passwords, key material, SCRAM nonces) resident in freed memory. This
file is the in-tree scrub primitive the corpus-wide **SecretBuf** proposal
(see `knowledge/issues/common.md`, A5) would standardize callers on. It is
compiled into `libpgport` only on platforms whose libc lacks a native
`explicit_bzero` (the build picks an implementation via the cascade of
`HAVE_*` probes). `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `void explicit_bzero(void *buf, size_t len)` | `explicit_bzero.c:21` (and four other ifdef arms) | One of five implementations is compiled depending on platform capability |

## Internal landmarks

Five mutually-exclusive implementations, selected at compile time:

1. `HAVE_MEMSET_EXPLICIT` → C23 `memset_explicit()` (`explicit_bzero.c:21`).
2. `HAVE_EXPLICIT_MEMSET` → NetBSD `explicit_memset()` (`:29`).
3. `HAVE_DECL_MEMSET_S` → C11 Annex K `memset_s()`; note `#define
   __STDC_WANT_LIB_EXT1__ 1` at top of file is required to expose it
   (`explicit_bzero.c:15,37`).
4. `WIN32` → `SecureZeroMemory()` (`:45`).
5. **Fallback** (`explicit_bzero.c:60-72`) — calls `memset` through a
   `static void (*volatile bzero_p)(void *, size_t)` function pointer. The
   `volatile` on the pointer is what defeats dead-store elimination: the
   compiler cannot prove the indirect call is a no-op. Idea credited to
   OpenSSH in the comment. `[from-comment]`

## Invariants & gotchas

- **`explicit_bzero` only *hinders*, never *guarantees*, scrub.** None of the
  arms touch register copies, spilled temporaries, or values the caller copied
  elsewhere. It scrubs the named buffer, nothing more.
- The fallback's defeat-the-optimizer trick is the *only* arm that depends on a
  trick; the other four delegate to a platform routine contracted to not be
  elided. A future compiler that constant-folds through the `volatile` pointer
  would silently regress the fallback — but every modern target uses one of the
  first four arms.
- Callers must still avoid leaving the secret in a wider-scope copy; `pgcrypto`
  and `scram-common` get this right for context state but the corpus has
  flagged caller-owned secret buffers that never reach this primitive (A2/A4/A5
  secret-scrub cluster).

## Cross-refs

- `knowledge/issues/common.md` — SecretBuf hosting-site proposal (A5).
- `knowledge/files/src/port/pg_strong_random.c.md` — sibling crypto primitive.
- `knowledge/files/src/port/timingsafe_bcmp.c.md` — sibling constant-time compare.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
