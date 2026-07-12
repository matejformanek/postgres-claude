---
source_url: https://www.postgresql.org/docs/current/datetime-input-rules.html
fetched_at: 2026-07-12T19:52:00Z
anchor_sha: eed6c0d33e09
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "B.1 Date/Time Input Interpretation"
---

# Docs distilled — Date/Time Input Interpretation (datetime-input-rules)

The **field-decoding algorithm** the datetime parser runs on an already-tokenized
input string: given a list of tokens, decide which token becomes year/month/day
vs hour/min/sec vs time zone. This is the user-facing spec for `DecodeDateTime()`
(the general timestamp path) in `datetime.c`; the load-bearing subsystem for the
`datetime.c` file doc + the type-conversion family. This is the **decode** stage,
distinct from the lexer (`ParseDateTime()`) that splits the raw string into fields
first.

## Non-obvious claims

- **Punctuation, not position, picks the category first.** A token containing a
  colon `:` is a *time* string (grab all following digits and colons); a token
  containing a dash `-`, slash `/`, or **two or more dots** is a *date* string
  (possibly with a text month). [from-docs]
- **A second date-shaped token becomes a time-zone name, not a date.** Once a
  date field has already been read, a later slash-bearing token (e.g.
  `America/New_York`) is interpreted as a timezone name rather than a second
  date. [from-docs] This is why `2004-10-19 10:23:54 America/New_York` parses.
- **Bare numeric tokens are disambiguated by digit count + what's been read so
  far**, in this order [from-docs]:
  - 8 or 6 digits, no date fields yet → concatenated ISO date `YYYYMMDD` /
    `YYMMDD` (e.g. `19990113` → 1999-01-13).
  - 3 digits, year already read → **day-of-year**.
  - 4 or 6 digits, year already read → concatenated time `HHMM` / `HHMMSS`.
  - 3+ digits and no date fields found yet → it's the **year**, and this
    *forces* yy-mm-dd ordering for the remaining fields.
  - anything else → fall back to the **`DateStyle`** setting (mm-dd-yy /
    dd-mm-yy / yy-mm-dd); error if the resulting month/day is out of range.
- **`DateStyle` only breaks ties.** It governs field ordering *only* when the
  numeric tokens didn't already match a concatenated or year-forcing pattern —
  ISO 8601 concatenated forms and a 3+-digit leading year both override it.
  [from-docs] The non-obvious consequence: `990113` and `19990113` are
  DateStyle-independent, but `01-02-03` is not.
- **2-digit year adjustment is asymmetric around 70.** A 2-digit year `< 70`
  gets `+2000`; `>= 70` gets `+1900`. To write AD 1–99 literally you must use a
  4-digit zero-padded form (`0099` = AD 99). [from-docs]
- **BC is stored as (negated year + 1)** — there is no year zero in the
  Gregorian calendar, so "1 BC" is internally year 0. [from-docs] Cross-links to
  the proleptic-Gregorian rule in `datetime-units-history`.
- **Alphabetic tokens are resolved timezone-abbrev-first, then keyword table.**
  An alpha token is first checked against the known timezone abbreviations (the
  IANA current-zone set + the `timezone_abbreviations` file), then binary-searched
  in the static keyword table for special strings (`today`), day names, month
  names, and noise words (`at`, `on`); unknown → error. [from-docs]
  [verified-by-code] the binary search is `datebsearch()`
  `src/backend/utils/adt/datetime.c:4303`, invoked for the keyword table at
  `:3275` and for zone abbreviations at `:3205`/`:3444`.

## Links into corpus

- [[knowledge/files/src/backend/utils/adt/datetime.c.md:46]] — the static
  `datetktbl` keyword table (`:106`) binary-searched by `datebsearch` (`:4303`),
  exactly the alpha-token path this page specifies.
- [[knowledge/docs-distilled/datetime-keywords.md]] — the keyword/day/month/
  modifier tables this algorithm searches.
- [[knowledge/docs-distilled/typeconv-overview.md]] — the parser-level coercion
  layer that hands string literals to this decode path via the type input
  function.
- [[knowledge/docs-distilled/datetime-units-history.md]] — the BC/AD no-year-zero
  and proleptic-Gregorian rules this page's year adjustment depends on.

## Confidence

Algorithm rules are [from-docs] (this is the normative spec page). The one
[verified-by-code] anchor is the `datebsearch` binary-search path for the
alphabetic/zone-abbrev branch, confirmed against `datetime.c` @ `eed6c0d33e09`.
