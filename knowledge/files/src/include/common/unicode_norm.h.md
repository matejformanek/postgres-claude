# src/include/common/unicode_norm.h

## Purpose

Public API for Unicode normalization (NFC/NFD/NFKC/NFKD) plus the
quick-check enumeration used by `unicode_is_normalized_quickcheck`.

## Role in PG

Shared **frontend + backend**. The single most important consumer
is **saslprep** (`src/common/saslprep.c`), which normalizes SCRAM
passwords with NFKC before they are hashed — see Phase D notes.

## Key declarations

- `enum UnicodeNormalizationForm` — `UNICODE_NFC=0`, `UNICODE_NFD=1`,
  `UNICODE_NFKC=2`, `UNICODE_NFKD=3`. (`unicode_norm.h:17-23`)
- `enum UnicodeNormalizationQC` — `NO=0`, `YES=1`, `MAYBE=-1` per
  UAX #15 quick-check semantics. (`unicode_norm.h:26-31`)
- `char32_t *unicode_normalize(form, const char32_t *input)` —
  allocates and returns a new codepoint sequence. Backend version
  uses palloc; frontend uses malloc. (`unicode_norm.h:33`)
- `UnicodeNormalizationQC unicode_is_normalized_quickcheck(form,
  const char32_t *input)` — fast path, may return MAYBE if a full
  normalization round-trip is required to be sure.
  (`unicode_norm.h:35`)

## Phase D notes

**Auth-critical.** SCRAM (RFC 5802) password preparation runs
`unicode_normalize(UNICODE_NFKC, ...)` on both ends of the wire.
If `psql`-side and server-side normalization disagree on a given
codepoint sequence (different generated tables, different Unicode
version), the password the user typed will hash differently — leading
to a hard-to-debug auth failure. Both sides build from the same
generated table (`unicode_norm_table.h`) at the same PG version, so
this is consistent within one build; but a backend and a libpq from
*different* PG versions could disagree if the Unicode tables were
regenerated between releases.

## Potential issues

`[ISSUE-correctness: NFKC table version skew between mismatched
libpq+server can cause SCRAM auth failure on exotic codepoints
(maybe)]`
