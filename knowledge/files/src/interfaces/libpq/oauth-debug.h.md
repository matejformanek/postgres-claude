# oauth-debug.h

- **Source path:** `source/src/interfaces/libpq/oauth-debug.h`
- **Last verified commit:** `4b0bf0788b0`
- **Size:** 143 lines

## Purpose

> "Parsing logic for PGOAUTHDEBUG environment variable. Both libpq and libpq-oauth need this logic, so it's packaged in a small header for convenience." [lines 3-7, from-comment]

A header-only utility (the parsing function is `static`) shared by `libpq` and the dynamically-loaded `libpq-oauth` plugin. Note libpq-oauth can't link against libpq-int.h, so the header avoids that dependency and requires callers to pre-declare `libpq_gettext`. [from-comment, lines 25-29]

## Flag layout

`PGOAUTHDEBUG` is a comma-separated list of option names. Flags are split into **unsafe** (low 16 bits) and **safe** (above) by bit position, enforced by `static_assert` at line 57-58. Unsafe flags require a literal `UNSAFE:` prefix on the envvar.

- `OAUTHDEBUG_UNSAFE_HTTP` (1<<0) — allow unencrypted HTTP to issuer endpoints.
- `OAUTHDEBUG_UNSAFE_TRACE` (1<<1) — log HTTP traffic; comment explicitly: "exposes secrets" (line 40).
- `OAUTHDEBUG_UNSAFE_DOS_ENDPOINT` (1<<2) — allow zero-second retry intervals (denial-of-service risk against the issuer).
- `OAUTHDEBUG_CALL_COUNT` (1<<16) — print PQconnectPoll statistics.
- `OAUTHDEBUG_PLUGIN_ERRORS` (1<<17) — print plugin loading errors.
- `OAUTHDEBUG_LEGACY_UNSAFE` (~0) — legacy `PGOAUTHDEBUG=UNSAFE` enables every flag.
- `OAUTHDEBUG_UNSAFE_MASK` 0x0000FFFF — the unsafe-flag region.

## Parser (`oauth_parse_debug_flags`, lines 78-140)

Static inline function in the header (so libpq and libpq-oauth each get their own copy):

1. Read `PGOAUTHDEBUG`; empty → return 0.
2. Bare `"UNSAFE"` → legacy mode, return all flags.
3. `"UNSAFE:..."` prefix → set `unsafe_allowed`, strip prefix.
4. `strdup` + `strtok_r` over commas.
5. Map known option strings to flag bits: `http`, `trace`, `dos-endpoint`, `call-count`, `plugin-errors`.
6. Unknown options → warn via `libpq_gettext` + stderr, drop.
7. Unsafe flags without `UNSAFE:` prefix → warn + drop.
8. OR matched flag into accumulator.

Returns the OR of accepted flags.

## Token-leak concern (Phase D)

[ISSUE-oauth-debug-001 — maybe] `OAUTHDEBUG_UNSAFE_TRACE` enables logging the HTTP traffic to the OAuth issuer. That traffic contains the bearer token in `Authorization: Bearer ...` headers and any client secret. The `UNSAFE:` gate is a deliberate trip-wire but the trace output destination is implementation-defined (likely the conn's `Pfdebug` FILE *) — operators turning this on for diagnosis may leave logs around. Verify the logging path (in libpq-oauth.c, not this header) clearly states the destination and doesn't survive a process restart.

[ISSUE-oauth-debug-002 — maybe] Parsing happens on every call (comment at lines 72-76 calls this out and explicitly punts on caching: "probably not worth the effort for a debugging aid?"). Each lookup does `getenv` + `strdup` + `strtok_r` + a stderr warning loop. If a hot path calls `oauth_parse_debug_flags` per-message (rather than per-connection), the warning text gets duplicated to stderr unboundedly.

[ISSUE-oauth-debug-003 — maybe] `strdup` failure at line 102 silently returns 0 (all flags off). A debug aid silently going dark is acceptable but the user gets no signal.

## Tally

`[verified-by-code]=2 [from-comment]=4 [maybe]=3`
