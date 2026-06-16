# src/common/unicode_norm.c

## Purpose

Implements Unicode normalization (UAX #15 NFC/NFD/NFKC/NFKD) on
arrays of `char32_t` codepoints, plus the fast "quick-check"
short-circuit.

## Role in PG

Shared **frontend + backend**, but the single most important
caller is **`src/common/saslprep.c`** — saslprep runs
`unicode_normalize(UNICODE_NFKC, ...)` on SCRAM passwords on both
the libpq and backend sides before they are hashed. A mismatch
between the two sides would yield silent SCRAM auth failures on
codepoints needing normalization.

## Key functions

- `static int conv_compare(p1, p2)` — qsort comparator used by
  `bsearch` on the decomposition table.
  (`unicode_norm.c:52-...`)
- `static const pg_unicode_decomposition *get_code_entry(char32_t)` —
  binary search into the canonical decomposition table generated
  from UCD UnicodeData.txt. (`unicode_norm.c:72-...`)
- `static uint8 get_canonical_class(char32_t)` — CCC lookup.
  (`unicode_norm.c:112-...`)
- `static const char32_t *get_code_decomposition(entry, *dec_size)` —
  returns the inline or pointer-indirected decomposition sequence.
  (`unicode_norm.c:134-...`)
- `static int get_decomposed_size(char32_t, bool compat)` — recursive
  expansion size for buffer pre-sizing. (`unicode_norm.c:159-...`)
- `static bool recompose_code(start, code, *result)` — applies the
  canonical composition table for NFC/NFKC. (`unicode_norm.c:218-...`)
- `static void decompose_code(code, compat, **result, *current)` —
  the recursive decomposer feeding the canonical-ordering step.
  (`unicode_norm.c:321-...`)
- `char32_t *unicode_normalize(form, const char32_t *input)` —
  public entrypoint. Decomposes, canonical-orders by CCC, and
  (for NFC/NFKC) recomposes. Output is palloc'd (backend) or
  malloc'd (frontend). (`unicode_norm.c:402-...`)
- `static const pg_unicode_normprops *qc_hash_lookup(ch, norminfo)` —
  perfect-hash lookup against the quick-check table.
  (`unicode_norm.c:561-...`)
- `static UnicodeNormalizationQC qc_is_allowed(form, ch)` — per-codepoint
  YES/NO/MAYBE for the form. (`unicode_norm.c:592-...`)
- `UnicodeNormalizationQC unicode_is_normalized_quickcheck(form,
  input)` — scans `input`, returns YES if every codepoint is YES,
  MAYBE if any are MAYBE, NO on first NO. The MAYBE case is
  inconclusive — caller must do the full normalize-and-compare to
  decide. (`unicode_norm.c:616-...`)

## State / globals

Generated tables (`unicode_norm_table.h`,
`unicode_normprops_table.h`, `unicode_norm_hashfunc.h`) — all
read-only.

## Phase D notes

- **Auth-critical for SCRAM.** `saslprep.c::pg_saslprep` calls
  `unicode_normalize(UNICODE_NFKC, decomposed)` and returns the
  result as the prepared password. Server side does the same. As
  long as both binaries build from matching generated tables at
  the same PG version, the auth will succeed.
- **Cross-version skew is possible in principle.** If a release
  ever regenerates the normalization tables (UCD bump), then a
  libpq-old + backend-new combination could disagree on exotic
  codepoints. PG has historically been conservative about UCD
  bumps for exactly this reason.
- **No bound on input length.** `unicode_normalize` allocates an
  output buffer whose size comes from `get_decomposed_size` summed
  over the input. A pathological input where most codepoints
  decompose into long sequences could amplify the allocation,
  though the worst-case ratio is small (~18× for the
  worst Hangul cases, much less in practice). The function does
  not impose a length cap — relies on the caller's input being
  reasonable. saslprep passes username/password strings, both
  short.

## Potential issues

`[ISSUE-correctness: NFKC table regeneration between PG releases
could cause libpq-old vs backend-new SCRAM auth failures on exotic
codepoints. No version-skew guard. (maybe)]`

`[ISSUE-dos: unicode_normalize has no input-length cap and a
modest worst-case expansion ratio; not a hazard for saslprep
(short inputs) but a generic exposed API. A future caller that
feeds attacker-controlled text could see memory amplification. (low)]`

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `common`](../../../issues/common.md)
<!-- issues:auto:end -->
