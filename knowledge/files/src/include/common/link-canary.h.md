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
- If libpq's startup ever skips the canary assertion, a subtle ABI
  mix could resurrect (e.g. backend `palloc` vs frontend `malloc`
  mismatch on `pfree`). [inferred]
- The mechanism: impl defines `pg_link_canary_is_frontend()` two
  different ways depending on `#ifdef FRONTEND`, and the chosen
  translation unit is link-determined. If libpq is linked but
  somehow resolves the symbol to the backend's copy at runtime
  (LD_PRELOAD, conflicting RTLD_GLOBAL, dlopen mistake), the
  assertion in libpq's PQconnect path catches it.
- **Nothing here gives the caller a way to be loud about
  failure** — `pg_link_canary_is_frontend` returns bool; libpq
  decides what to do. A header-level `pg_assert_link_canary()`
  macro could short-circuit init.

## Cross-refs

- Impl: `knowledge/files/src/common/link-canary.c.md`.
- libpq use: `src/interfaces/libpq/fe-connect.c::PQconnectStart`.

<!-- issues:auto:begin -->
- [Issue register — `include-common`](../../../../issues/include-common.md)
<!-- issues:auto:end -->

## Issues

1. `[ISSUE-documentation: header lacks any pointer to "where this
   gets checked" — a new contributor adding a libpq-like build
   product needs to read the impl to discover the assertion
   convention (nit)]` — `source/src/include/common/link-canary.h:15`.
2. `[ISSUE-defense-in-depth: API returns bool but offers no helper
   for "assert and abort with a coherent diagnostic" — every
   consumer reinvents the check (nit)]` —
   `source/src/include/common/link-canary.h:15`.

## Confidence tag tally
`[from-comment]=1 [verified-by-code]=1 [inferred]=2`
