---
path: src/include/common/link-canary.h
anchor_sha: 4b0bf0788b0
loc: 17
depth: skim
---

# link-canary.h

- **Source path:** `source/src/include/common/link-canary.h`
- **Lines:** 17
- **Last verified commit:** `4b0bf0788b0`
- **Companion file:** `common/link-canary.c` (the implementation).

## Purpose

One-symbol API used by libpq to assert it was linked against the **frontend** copy of `src/common`/`src/port`, not the backend's. Mitigates the ELF symbol-collision risk when libpq is loaded into the backend (or a backend extension) and the dynamic linker resolves `src/common` symbols to the backend's copy instead of libpq's own. [from-comment, link-canary.h:1-11]

## Public surface

- `pg_link_canary_is_frontend()` — returns `true` when compiled `#ifdef FRONTEND`, `false` otherwise. [verified-by-code, link-canary.h:15]

## Phase D notes

- Pure build/link sanity-check; no trust-boundary surface.
- If libpq's startup ever skips the canary assertion, a subtle ABI mix could resurrect (e.g. backend `palloc` vs frontend `malloc` mismatch on `pfree`). [inferred] [maybe — Phase D, see ISSUE register]

## Confidence tag tally
`[from-comment]=1 [verified-by-code]=1 [inferred]=1`
