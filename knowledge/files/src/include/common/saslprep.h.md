---
path: src/include/common/saslprep.h
anchor_sha: 4b0bf0788b0
loc: 30
---

# saslprep.h

- **Source path:** `source/src/include/common/saslprep.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 30

## Purpose

Public API for `pg_saslprep`, the SASLprep (RFC 4013) stringprep
profile used to normalise SCRAM passwords. Frontend and backend share
the same implementation. [from-comment, saslprep.h:6]

## Key declarations

- `pg_saslprep_rc` enum: `SASLPREP_SUCCESS`, `SASLPREP_OOM` (frontend
  only — backend `ereport`s), `SASLPREP_INVALID_UTF8`,
  `SASLPREP_PROHIBITED` (saslprep.h:20-26).
- `pg_saslprep(input, output)` (saslprep.h:28): allocates
  `*output` palloc'd / malloc'd on success.

## Phase D notes

- **Best-effort discipline.** Callers in `auth-scram.c` and
  `fe-auth-scram.c` treat *any* non-`SASLPREP_SUCCESS` as "use the
  raw bytes, don't error". This keeps non-UTF8 clients working — see
  the header comment in `auth-scram.c` lines 23-30.
- `OOM` is a frontend-only code; backend `pg_saslprep` `ereport(ERROR)`s
  via `palloc`. The `pg_saslprep_rc` value `SASLPREP_OOM` is therefore
  unreachable in backend code.
- **Output ownership ambiguity.** `pg_saslprep(input, output)` writes
  `*output` as `palloc`'d (backend) or `malloc`'d (frontend). Header
  doesn't say which — caller must know context. Wrong `free()` across
  the FE/BE boundary is a silent leak / heap-mismatch.
- **Input not length-bounded.** Very large input runs SASLprep to
  completion. SCRAM passwords are wire-frame bounded; future
  consumers could miss this implicit bound.
- **SecretBuf candidate.** The password being prep'd IS the secret;
  output is "the same secret, normalized". A `SecretBuf` variant
  would guarantee `explicit_bzero` on the freed output instead of
  leaving the bytes on heap pages until reuse.

## Cross-refs

- Impl: `knowledge/files/src/common/saslprep.c.md`.
- Backend caller: `knowledge/files/src/backend/libpq/auth-scram.c.md`.
- Frontend caller: `src/interfaces/libpq/fe-auth-scram.c`.
- A5 SecretBuf cluster: `knowledge/issues/common.md`.

<!-- issues:auto:begin -->
- [Issue register — `include-common`](../../../../issues/include-common.md)
<!-- issues:auto:end -->

## Issues

1. `[ISSUE-documentation: pg_saslprep's *output allocator (palloc
   vs malloc) is FE/BE context-dependent and not documented at
   header level (likely)]` — `source/src/include/common/saslprep.h:28`.
2. `[ISSUE-defense-in-depth: no input-length bound; very large
   passwords are normalized in full (nit)]` —
   `source/src/include/common/saslprep.h:28`.
3. `[ISSUE-api-shape: normalized password output is a plain char *;
   A5 SecretBuf candidate site (maybe)]` —
   `source/src/include/common/saslprep.h:28`.
4. `[ISSUE-documentation: SASLPREP_OOM is frontend-only; the enum
   should annotate this so backend readers know it's unreachable
   (nit)]` — `source/src/include/common/saslprep.h:23`.

## Tally

`[verified-by-code]=3 [from-comment]=2`
