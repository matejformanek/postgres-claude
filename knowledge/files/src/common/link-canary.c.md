---
path: src/common/link-canary.c
anchor_sha: 4b0bf0788b0
loc: 36
depth: read
---

# link-canary.c

- **Source path:** `source/src/common/link-canary.c`
- **Lines:** 36
- **Last verified commit:** `4b0bf0788b0`
- **Companion file:** `common/link-canary.h`.

## Purpose

Two-line frontend/backend discriminator. `pg_link_canary_is_frontend()` returns `true` when compiled with `-DFRONTEND` (which is the build flag used for `libpgcommon.a` shipped to `libpq`/`psql`/etc.) and `false` when built into the server. libpq calls it at startup and aborts if the answer is wrong; the test catches platforms where the dynamic linker silently resolves a libpq-internal `src/common` symbol to the backend's identically-named copy. [from-comment, link-canary.c:16-27]

## Role in PG

Build-time link discipline. Called from libpq init code (and a few `src/test/modules` cases). Not present at runtime in postmaster paths.

## Key function

- `pg_link_canary_is_frontend(void)` — `#ifdef FRONTEND` returns `true`; else `false`. [verified-by-code, link-canary.c:28-36]

## Phase D notes

- No external input, no allocation, no state. Pure compile-time discriminator.
- If a future refactor moves the function to a header (`static inline`), the canary becomes useless — both copies would compile to identical TU-local code and the test would always succeed. [inferred] [maybe]

## Confidence tag tally
`[from-comment]=1 [verified-by-code]=1 [inferred]=1`
