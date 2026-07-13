---
source_url: https://www.postgresql.org/docs/current/datetime-julian-dates.html
fetched_at: 2026-07-12T19:53:00Z
anchor_sha: eed6c0d33e09
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "B.6 Julian Dates"
---

# Docs distilled — Julian Dates (datetime-julian-dates)

PostgreSQL's Julian-Date convention and where it deliberately diverges from the
astronomers' definition. Backs the `J`/`JD`/`JULIAN` input modifier and the
`extract(julian from …)` output.

## Non-obvious claims

- **PG Julian dates run midnight-to-midnight, not the astronomers' noon-to-noon.**
  "Although PostgreSQL supports Julian Date notation … it does not observe the
  nicety of having dates run from noon to noon." The astronomical convention has
  each day run noon-UTC to noon-UTC (JD 0 = noon 24 Nov 4714 BC → noon 25 Nov);
  PG runs each Julian day "from local midnight to local midnight, the same as a
  normal date." [from-docs] This half-day offset is the classic gotcha when
  cross-checking against astronomy software.
- **JD 0 dual-calendar anchor:** 1 January **4713 BC** in the *Julian* calendar
  = 24 November **4714 BC** in the *(proleptic) Gregorian* calendar. Each
  subsequent day is a sequential integer from 0. [from-docs] (The Gregorian
  form is what `date2j` computes — see `datetime-units-history`.)
- **To recover the true astronomical JD, do the arithmetic in `UTC+12`.**
  Shifting by 12 hours realigns midnight-based counting onto noon-based:
  `extract(julian from '2021-06-23 7:00:00-04'::timestamptz at time zone
  'UTC+12')` → `2459388.958333…` (a fractional astronomical JD). [from-docs]
- **PG uses Julian day numbers internally for datetime math, not just for I/O.**
  The page notes PG "also uses Julian dates for some internal datetime
  calculations" — consistent with `date2j`/`j2date` being the conversion core.
  [from-docs], corroborated [verified-by-code] by the pervasive `date2j`/`j2date`
  use across `datetime.c` (e.g. day-of-year at `:2611`, today/tomorrow special
  values at `:1352`/`:1369`).

## Links into corpus

- [[knowledge/docs-distilled/datetime-units-history.md]] — the proleptic-
  Gregorian rule that fixes the Gregorian side of the JD-0 anchor.
- [[knowledge/docs-distilled/datetime-keywords.md]] — the `J`/`JD`/`JULIAN`
  modifier (Table B.3) that triggers Julian-Date input parsing.
- [[knowledge/files/src/backend/utils/adt/datetime.c.md:25]] — `date2j`/`j2date`,
  the functions realizing this convention.

## Confidence

All numeric anchors + the noon-vs-midnight divergence + the `UTC+12` workaround
are [from-docs]. The "used internally" claim is [from-docs] and corroborated
[verified-by-code] by `date2j`/`j2date` call sites in `datetime.c` @
`eed6c0d33e09`.
