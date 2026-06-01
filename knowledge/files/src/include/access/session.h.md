# session.h

- **Source path:** `source/src/include/access/session.h`
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `session.c`, `utils/typcache.c`.

## Purpose

Defines the `Session` struct and declares the four lifecycle functions implemented in `session.c`. A `Session` holds the per-process pointer to the session-scope DSM segment + DSA area plus the shared record-typmod registry (so parallel leader and workers agree on ephemeral RECORD typmods). [from-comment, session.h:1-12, 19-24]

## Key type

- **`Session`** (25) — `dsm_segment *segment; dsa_area *area; struct SharedRecordTypmodRegistry *shared_typmod_registry; dshash_table *shared_record_table; dshash_table *shared_typmod_table;` [verified-by-code]

## Public surface

- `InitializeSession(void)`, `GetSessionDsmHandle(void)`, `AttachSession(dsm_handle)`, `DetachSession(void)`.
- Global: `extern PGDLLIMPORT Session *CurrentSession`. May be NULL very early in startup.

## Cross-references

- Behaviour: `knowledge/files/src/backend/access/common/session.c.md`.

## Confidence tag tally
`[verified-by-code]=2 [from-comment]=1 [from-readme]=0 [inferred]=0 [unverified]=0`
