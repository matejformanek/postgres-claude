# `src/backend/utils/adt/levenshtein.c`

- **File:** `source/src/backend/utils/adt/levenshtein.c` (403 lines)
- **Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Purpose

Implementation of `varstr_levenshtein()` and
`varstr_levenshtein_less_equal()` — multi-byte-aware edit distance over
two arbitrary byte buffers. **This file is `#include`d twice by
`varlena.c`** (`:7-10` [from-comment]); the second inclusion defines
`LEVENSHTEIN_LESS_EQUAL` to produce the bounded variant. Before each
inclusion `varlena.c` defines `rest_of_char_same()` as an inline
helper.

The SQL surface (`levenshtein(text, text [, int, int, int [, int]])`)
lives in `contrib/fuzzystrmatch` / `varlena.c`; this file is purely the
algorithm.

## Algorithm

- Standard two-row dynamic-programming Levenshtein, **O(m·n) time, O(m)
  memory** (`:122-127` [from-comment]).
- `prev`/`curr` are int[m+1] buffers held in `palloc(2 * m *
  sizeof(int))` (`:214`).
- Multibyte support: `pg_mbstrlen_with_len` for character counts
  (`:110-111`); `s_char_len[]` caches per-char byte-widths to avoid
  repeated `pg_mblen_range()` calls (`:200-207`); a single-byte
  fast-path is taken when both strings are pure single-byte (`:271-326`).

## `MAX_LEVENSHTEIN_STRLEN` (`:26`) — the DoS cap

The `trusted` parameter governs whether the cap is enforced (`:38`):
- `trusted == false` (default for SQL-callable wrappers) — both m and n
  must be ≤ 255 characters, else `ereport(ERROR,
  "levenshtein argument exceeds maximum length of 255 characters")`
  (`:129-135` [verified-by-code]).
- `trusted == true` — caller is responsible (used e.g. by parser's
  fuzzy match for keyword/identifier suggestions, where inputs are
  bounded by other invariants).

This is the **explicit DoS hardening**: without the cap, an attacker
could submit two strings of 1 GB each and provoke 10^18 operations.

## `LEVENSHTEIN_LESS_EQUAL` variant

When `max_d >= 0`, the bounded variant maintains a `start_column` /
`stop_column` sliding window around the matrix diagonal to avoid
filling cells that can never affect the answer (`:62-64` [from-comment]).
Returns `max_d + 1` as soon as it can prove the distance exceeds the
bound (`:156, :393`).

Theoretical minimum and maximum distances are precomputed
(`min_theo_d` / `max_theo_d`, `:150-162`) and used to short-circuit
impossible bounds.

## Phase D notes

- **DoS surface present and explicitly mitigated.** The 255-char cap is
  small enough that even an O(m·n) worst case is bounded at 65K matrix
  cells per call. SAFE.
- The `trusted` escape hatch is the only way to bypass; callers are
  expected to bound input length themselves. Worth grepping `trusted =
  true` callsites if Phase D wants to harden further.
- Multibyte path: `pg_mblen_range` is the per-char cost; for a 255-char
  string in UTF-8 worst case that's 4·255 = 1020 byte scans — trivial.

## Potential issues

- [ISSUE-dos: `varstr_levenshtein(..., trusted=true)` bypasses the
  255-char cap — any caller passing `trusted=true` must bound input
  themselves. Audit the call sites in varlena.c and selfuncs.c.
  (maybe)]
- [ISSUE-undocumented-invariant: `palloc(2 * m * sizeof(int))` (`:214`)
  could overflow if `m > INT_MAX / (2 * sizeof(int))`, but the
  255-cap-or-trusted-caller invariant prevents that in practice. The
  `trusted=true` path has no guard. (maybe)]

## Cross-references

- `source/src/backend/utils/adt/varlena.c` — wraps and SQL-binds these.
- `source/contrib/fuzzystrmatch/` — older home of the algorithm; the
  in-core version is reachable via standard SQL.
- `source/src/include/mb/pg_wchar.h` — `pg_mblen_range`,
  `pg_mbstrlen_with_len`.

## Confidence tag tally

- `[verified-by-code]` × 5
- `[from-comment]` × 3
