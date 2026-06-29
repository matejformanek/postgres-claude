# source/contrib/fuzzystrmatch/fuzzystrmatch.c

**Source pin:** master @ 4b0bf07. 805 LOC.

## Role

Top-level entry point for the `fuzzystrmatch` extension. Wraps the
backend's `varstr_levenshtein` family with SQL-callable functions,
implements Soundex (4-char) and original Metaphone in-process, and
exposes `difference` (count of matching Soundex digits).

Note: `dmetaphone` / `dmetaphone_alt` live in the sibling
`dmetaphone.c`; `daitch_mokotoff` lives in `daitch_mokotoff.c`.

## Public API (SQL-callable)

| Function | Args | Implementation |
|---|---|---|
| `levenshtein(text, text)` | 2 | wraps `varstr_levenshtein(...,1,1,1,false)` [line 184] |
| `levenshtein_with_costs(text, text, int, int, int)` | 5 | [line 157] |
| `levenshtein_less_equal(text, text, int)` | 3 | wraps `varstr_levenshtein_less_equal` [line 235] |
| `levenshtein_less_equal_with_costs(...)` | 6 | [line 206] |
| `metaphone(text, int reqlen)` | 2 | classic Metaphone [line 267] |
| `soundex(text)` | 1 | American Soundex (4 chars) [line 722] |
| `difference(text, text)` | 2 | count of matching Soundex digits [line 786] |

## Invariants

- INV: `metaphone` hard-caps input AND output at
  `MAX_METAPHONE_STRLEN = 255` bytes
  [verified-by-code source/contrib/fuzzystrmatch/fuzzystrmatch.c:75,
  278-289]. Both input length > 255 and requested output > 255
  → `ereport(ERROR, ERRCODE_INVALID_PARAMETER_VALUE)`.
- INV: `metaphone(text, 0)` → ERROR ("output cannot be empty
  string") [trgm at 291-294]. Despite the comment "Assume largest
  possible" at line 380, max_phonemes=0 is rejected at the SQL
  boundary.
- INV: Soundex output is fixed 4 characters: first letter (raw,
  uppercase), then 3 numeric digits or '0' pad
  [verified-by-code fuzzystrmatch.c:57, 734-782].
- INV: Soundex uses ASCII-only logic; non-ASCII letters are passed
  through as-is in `soundex_code` (returns the letter itself)
  [fuzzystrmatch.c:62-70]. `ascii_isalpha` is ASCII-only
  [line 135-140].
- INV: `_metaphone` allocates output buffer = `max_phonemes + 1`
  bytes [line 386]; loop bounded by `Phone_Len < max_phonemes`
  [line 471]. So output is hard-capped.
- INV: `Lookahead` iterates up to `how_far` characters or until
  NUL, never past [line 329-340]. Safe.

## Notable internals

- `_codes[26]` and the `getcode` family encode the per-letter
  properties used by Metaphone rules (isvowel, NOCHANGE, AFFECTH,
  MAKESOFT, NOGHTOF) [line 119-154]. Bitmask-based.
- `_metaphone` is a single state-machine switch over `Curr_Letter`,
  with `skip_letter` advancing past digraphs handled inline
  [line 469-710].
- `_soundex` strips leading non-alphas, takes first letter as-is,
  then encodes subsequent letters dropping consecutive same-code
  letters; pads with '0' to length 4.

## Trust-boundary / Phase-D surface

1. **Soundex / metaphone are SELECT-grantable side channels.** Same
   pattern as pg_trgm `similarity` and `show_trgm`: any user with
   `SELECT` on a column can compute `soundex(col) = soundex('admin')`,
   which is a side-channel into hashed/encrypted columns IF the
   hash preserves ASCII-letter structure (it doesn't for crypto
   hashes, but DOES for plaintext-near-plaintext columns like
   usernames or addresses). The Phase-D concern: a leak monitor
   that scans for "near matches" using soundex+difference could
   be turned into a discovery oracle.
2. **`levenshtein` and `levenshtein_less_equal` delegate to
   `varstr_levenshtein` in backend/utils/adt/varlena.c.** That
   function's memory footprint is O(s1_chars × s2_chars) for the
   full version and O(s1_chars × max_distance) for less_equal.
   No length cap at the fuzzystrmatch boundary — a 1MB × 1MB call
   would attempt to palloc 1 trillion bytes. The backend's
   `varstr_levenshtein` does check `MaxAllocSize` (verified
   elsewhere) but worth noting that fuzzystrmatch.c adds NO cap.
3. **`metaphone` hard caps at 255 bytes** — well-bounded; no
   Phase-D concern.
4. **`text_to_cstring` of attacker-controlled text** at lines
   727, 794-795 — allocates a NUL-terminated copy; bounded by
   text size. NB: `text_to_cstring` does NOT check for embedded
   NULs but neither soundex nor metaphone treats them as
   terminators in a way that would matter (loops stop on NUL).
5. **`metaphone` uses `pg_ascii_toupper` only**, ignoring
   collation entirely [line 313-323]. So `metaphone('CAFÉ', 4)`
   ignores the É. This is documented and intentional.
6. **No `CHECK_FOR_INTERRUPTS` in `_metaphone` or `_soundex`**
   — but both are bounded by 255 chars in / 4 chars out (soundex)
   and 255 in / max_phonemes out (metaphone), so trivially fast.

## Cross-refs

- `source/backend/utils/adt/varlena.c` — `varstr_levenshtein`
- `source/contrib/fuzzystrmatch/dmetaphone.c` — Double Metaphone
- `source/contrib/fuzzystrmatch/daitch_mokotoff.c` — D-M Soundex

## Issues

- [ISSUE-Phase-D: levenshtein has no length cap at fuzzystrmatch
  boundary (low)] — source/contrib/fuzzystrmatch/fuzzystrmatch.c:184,
  235 — relies entirely on `varstr_levenshtein`'s internal
  MaxAllocSize check. A 100MB × 100MB call asks for 10^16 bytes;
  caught downstream but defense-in-depth would warn earlier.
- [ISSUE-Phase-D: soundex/metaphone as similarity side channels (low)] —
  source/contrib/fuzzystrmatch/fuzzystrmatch.c:719-805 — any
  SELECT user can compute `soundex(col)`, enabling
  side-channel discovery of users / addresses by phonetic
  similarity to a guess. Same family as pg_trgm `show_trgm`.
- [ISSUE-Style: ASCII-only behavior is undocumented as security
  property (low)] — source/contrib/fuzzystrmatch/fuzzystrmatch.c:63-70,
  313-323 — soundex/metaphone silently ignore non-ASCII letters;
  could surprise users with non-English data.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-fuzzystrmatch.md](../../../subsystems/contrib-fuzzystrmatch.md)
