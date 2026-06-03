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

## Cross-refs

- Impl: `knowledge/files/src/common/saslprep.c.md`.
- Backend caller: `knowledge/files/src/backend/libpq/auth-scram.c.md`.
- Frontend caller: `src/interfaces/libpq/fe-auth-scram.c`.

## Tally

`[verified-by-code]=2 [from-comment]=1`
