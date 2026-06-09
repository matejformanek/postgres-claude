# Issues — `contrib/fuzzystrmatch`

Fuzzy string-matching algorithms (soundex, metaphone, dmetaphone, daitch_mokotoff, levenshtein). 3 source files / ~2819 LOC.

**Parent docs:** `knowledge/files/contrib/fuzzystrmatch/*` (3 docs: fuzzystrmatch.c, dmetaphone.c, daitch_mokotoff.c).

**Source:** 10 entries surfaced 2026-06-09 by A14-4.

## Headlines

1. **dmetaphone has NO input length cap** (unlike classical metaphone's 255-byte cap) AND no CFI in its main loop — adversary input designed to never grow either primary/secondary code stalls the loop O(input_length).
2. **Phonetic coding as similarity side channel** — soundex/metaphone/dmetaphone/daitch_mokotoff are SELECT-grantable oracles enabling phonetic discovery of usernames/addresses without direct equality. Same family as pg_trgm `show_trgm`.
3. **`daitch_mokotoff` main loop has no CFI** — provably O(input × const) but 1 GB input runs without yield.
4. No length cap at fuzzystrmatch `levenshtein` boundary — relies entirely on backend `varstr_levenshtein` `MaxAllocSize` check (defense-in-depth gap).
5. ASCII-only soundex/metaphone undocumented as security boundary — silently ignores non-ASCII letters.

## Entries — `fuzzystrmatch.c`

- [ISSUE-resource: no length cap at fuzzystrmatch levenshtein boundary (nit)] — `:184,235` — defense-in-depth gap.
- [ISSUE-security: phonetic coding as similarity side channel (maybe)] — `:719-805` — SELECT-grantable oracle.
- [ISSUE-documentation: ASCII-only soundex/metaphone undocumented as security boundary (nit)] — `:63-70,313-323`

## Entries — `dmetaphone.c`

- [ISSUE-resource: no `CHECK_FOR_INTERRUPTS` in DoubleMetaphone loop (likely)] — `:437` — for adversary inputs that never grow primary/secondary fast (all silent letters), loop runs O(input_length) with no cancel point.
- [ISSUE-resource: no input length cap on dmetaphone (maybe)] — `:143,172` — unlike classical `metaphone()` (255-byte cap), `dmetaphone()` accepts 1 GB text.
- [ISSUE-security: phonetic coding as similarity side channel (maybe)] — `:132,161` — SELECT-grantable.
- [ISSUE-memory: `META_FREE` no-op relies on context cleanup (nit, acknowledged)] — `:196-201`
- [ISSUE-api-shape: `StringAt` varargs `""` terminator is a footgun (nit)] — `:353-379`

## Entries — `daitch_mokotoff.c`

- [ISSUE-security: phonetic coding as similarity side channel (maybe)] — `:122` — SELECT-grantable.
- [ISSUE-resource: no CFI in daitch_mokotoff main loop (nit)] — `:544-555`
- [ISSUE-resource: no length cap at daitch_mokotoff SQL entry (nit)] — `:125-140`
- [ISSUE-defense-in-depth: implicit trust in generated static tables for d_m fan-out bound (nit)] — `:480-510`

## Cross-sweep references

- A14 pg_trgm `show_trgm` — same SELECT-grantable text oracle pattern.
- A11 pgcrypto `crypt()` weak hash defaults — similarity-as-side-channel cluster.
- A10 plpython/plperl text→SPI sinks — similarity-as-injection-channel cluster.
