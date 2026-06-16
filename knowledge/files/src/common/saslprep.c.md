---
path: src/common/saslprep.c
anchor_sha: 4b0bf0788b0
loc: 1239
---

# saslprep.c

- **Source path:** `source/src/common/saslprep.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 1239

## Purpose

SASLprep stringprep profile (RFC 4013, the SASL profile of RFC 3454
stringprep) used to normalise the SCRAM password before SaltedPassword
derivation. Heavy file: most of it is large static tables of Unicode
codepoint ranges (mapped-to-space, mapped-to-nothing, prohibited,
unassigned, RandALCat, LCat) sourced from the RFC; the entry-point
`pg_saslprep` is the last ~190 lines. [verified-by-code,
saslprep.c:1-21, 1046-1239]

## Role in PG

Shared between backend (`auth-scram.c::scram_verify_plain_password`,
`pg_be_scram_build_secret`) and frontend (`fe-auth-scram.c` during
the client-first / client-final composition). Best-effort discipline:
both callers fall back to raw bytes on non-`SASLPREP_SUCCESS`. Built
on top of `src/common/unicode_norm.c::unicode_normalize(UNICODE_NFKC,
...)`. [verified-by-code, saslprep.c:1120]

## Key functions

- `pg_saslprep(input, output)` (saslprep.c:1046):
  1. UTF-8 sanity-check via `pg_utf8_string_len` (saslprep.c:1002 —
     scans, returns -1 if not legal UTF-8).
  2. Allocate `input_chars[input_size+1]` array of `char32_t`
     codepoints; decode via `utf8_to_unicode` (saslprep.c:1075-1085).
  3. **Map step** — for each codepoint:
     - In `non_ascii_space_ranges` → replace with U+0020.
     - In `commonly_mapped_to_nothing_ranges` → drop.
     - Otherwise keep (saslprep.c:1096-1108).
  4. Reject empty post-map result (`SASLPREP_PROHIBITED`,
     saslprep.c:1113-1114).
  5. **Normalize step** — `unicode_normalize(UNICODE_NFKC, ...)`
     (saslprep.c:1120). Allocates `output_chars`.
  6. **Prohibit step** — scan for `prohibited_output_ranges` or
     `unassigned_codepoint_ranges`; either trips `SASLPREP_PROHIBITED`
     (saslprep.c:1128-1136).
  7. **Bidi check** — if any RandALCat present: forbid LCat
     coexistence, require first and last char both RandALCat
     (saslprep.c:1159-1187).
  8. Convert back to UTF-8 into a freshly-allocated `result`
     (saslprep.c:1192-1216). Backend uses palloc, frontend malloc.
- Helpers:
  - `codepoint_range_cmp` (saslprep.c:49) — bsearch comparator.
  - `is_code_in_table(code, map, mapsize)` — bsearch over a sorted
    `[lo, hi]` range array; tables use the `IS_CODE_IN_TABLE` macro.
  - `pg_utf8_string_len(source)` (saslprep.c:1002) — scan-and-count
    UTF-8 chars, returns -1 on invalid sequence.

## State / globals

- Eight large read-only Unicode range tables (saslprep.c:67-1000):
  - `non_ascii_space_ranges`
  - `commonly_mapped_to_nothing_ranges`
  - `prohibited_output_ranges` (union of multiple RFC tables)
  - `unassigned_codepoint_ranges`
  - `RandALCat_codepoint_ranges`
  - `LCat_codepoint_ranges`
  - (plus a few smaller ones)
- These are **hand-curated from Unicode 3.2 tables per RFC 3454** —
  not regenerated from upstream Unicode data files. The Unicode
  data driving `unicode_normalize` *is* regenerated (see
  `src/common/unicode/`) but stringprep is frozen at Unicode 3.2 per
  the RFC. [from-comment, saslprep.c:60-66]

## Concurrency

Reentrant. All globals read-only.

## Phase D notes

- **Plaintext-password lifetime:** `pg_saslprep` takes a `const char
  *input` (the raw cleartext password) and the caller retains
  responsibility. The `input_chars` codepoint buffer that's
  allocated mid-function holds the *normalised* password — both are
  cleartext-derived material.
  - **`input_chars` is `FREE`d at end without `explicit_bzero`**
    (saslprep.c:1218, 1226, 1234). Same for `output_chars`.
  - The returned `*output` (final UTF-8 normalised password) is the
    caller's problem to scrub.
- **OOM in frontend returns `SASLPREP_OOM`; backend ereports.**
  Asymmetry already documented; do NOT block on it.
- **Unicode 3.2 freeze:** A new codepoint added in Unicode 15 will
  flow through `unicode_normalize` correctly per current Unicode
  data but **bypass any prohibition** that would have been added in
  a newer stringprep profile. RFC 8265 / PRECIS is the modern
  successor; PG hasn't moved. Worth a follow-up note.

## Potential issues

- **[ISSUE-secret-scrub: `input_chars` / `output_chars` (32-bit-wide
  password codepoints) freed without explicit_bzero]**
  `saslprep.c:1218-1236`. Both buffers carry the cleartext password
  in expanded form. Severity: likely.
- **[ISSUE-stale-todo: stringprep frozen at Unicode 3.2 per
  RFC 3454]** `saslprep.c:54-66`. RFC 8265 (PRECIS) is the
  successor since 2017. PG hasn't migrated. Severity: nit
  (intentional — RFC compatibility).
- **[ISSUE-undocumented-invariant: empty-after-map rejected as
  PROHIBITED, not as a distinct empty-password code]**
  `saslprep.c:1113-1114`. Callers see "prohibited chars" when really
  the result is empty. Severity: nit.
- **[ISSUE-correctness: prohibit check uses `input_chars` (pre-NFKC)
  but normalize produced `output_chars` (post-NFKC)]**
  `saslprep.c:1128-1136`. The RFC's "check after normalisation" is
  ambiguous; PG re-uses `input_chars` because NFKC of an
  already-Unicode-clean codepoint cannot introduce a prohibited
  char (assertedly). This is fine but worth a comment.
  Severity: nit.

## Cross-refs

- Public API: `knowledge/files/src/include/common/saslprep.h.md`.
- Unicode normalisation core: `src/common/unicode_norm.c`.
- Backend caller: `knowledge/files/src/backend/libpq/auth-scram.c.md`.
- Frontend caller: `src/interfaces/libpq/fe-auth-scram.c`.

<!-- issues:auto:begin -->
- [Issue register — `common`](../../../issues/common.md)
<!-- issues:auto:end -->

## Tally

`[verified-by-code]=15 [from-comment]=3 [inferred]=2`
