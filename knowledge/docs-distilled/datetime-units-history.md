---
source_url: https://www.postgresql.org/docs/current/datetime-units-history.html
fetched_at: 2026-07-12T19:52:20Z
anchor_sha: eed6c0d33e09
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "B.5 History of Units"
---

# Docs distilled — History of Units (datetime-units-history)

Why PostgreSQL dates are calendar-uniform across all of history: the **proleptic
Gregorian** rule and its consequences. The conceptual foundation under
`date2j()` / `j2date()` in `datetime.c`.

## Non-obvious claims

- **PostgreSQL counts *every* date in the Gregorian calendar, even before 1582.**
  "PostgreSQL follows the SQL standard's lead by counting dates exclusively in
  the Gregorian calendar, even for years before that calendar was in use. This
  rule is known as the *proleptic Gregorian calendar*." [from-docs] This is a
  deliberate SQL-standard conformance choice, quoting: "Within the definition of
  a 'datetime literal', the datetime values are constrained by the natural rules
  for dates and times according to the Gregorian calendar."
- **It is explicitly *not* historically accurate, and that's by design.** "Since
  it would be difficult and confusing to try to track the actual calendars that
  were in use in various places at various times, PostgreSQL does not try, but
  rather follows the Gregorian calendar rules for all dates, even though this
  method is not historically accurate." [from-docs] Consequence: the real
  Sep 1752 British calendar gap (and every local Julian→Gregorian switch) does
  *not* exist in PG dates.
- **Gregorian leap rule, exactly:** divisible by 4 → leap, except divisible by
  100 → not leap, except divisible by 400 → leap after all. So 1700/1800/1900/
  2100 are **not** leap years; 1600/2000/2400 **are**. [from-docs] (The Julian
  approximation of 365.25 days drifts ~1 day/128 yr; Gregorian's 365.2425 drifts
  ~1 day/3300 yr.)
- **`date2j()` is a closed-form Julian-day conversion, valid into deep BC.**
  [verified-by-code] `src/backend/utils/adt/datetime.c:297` — pure integer
  arithmetic (`julian = year*365 - 32167; julian += year/4 - century +
  century/4; julian += 7834*month/256 + day;`), with a source note (`:290-293`)
  that it "will work sanely … significantly before Nov 24, -4713 … back to Nov 1,
  -4713" per `IS_VALID_JULIAN()`. The inverse is `j2date()` (`:322`).
- **The epoch is self-checked at startup, not hard-coded blindly.**
  [verified-by-code] `datetime.c:4970-4971`:
  `Assert(UNIX_EPOCH_JDATE == date2j(1970,1,1));` and
  `Assert(POSTGRES_EPOCH_JDATE == date2j(2000,1,1));` — PG's internal timestamp
  epoch is **2000-01-01**, distinct from the Unix 1970 epoch. This is why
  `timestamp` seconds are counted from 2000, converted to/from Unix time only at
  the boundaries.

## Links into corpus

- [[knowledge/docs-distilled/datetime-julian-dates.md]] — the Julian-Date
  definition (`JD 0` = 24 Nov 4714 BC proleptic-Gregorian) that `date2j`
  realizes.
- [[knowledge/docs-distilled/datetime-input-rules.md]] — the BC/AD
  no-year-zero adjustment this proleptic rule justifies.
- [[knowledge/files/src/backend/utils/adt/datetime.c.md:25]] — the file doc's
  "Date math: `date2j`/`j2date`/`j2day` (`:297`,`:322`,`:355`)" entry.

## Confidence

Calendar rules + SQL-standard rationale are [from-docs]. The `date2j`/`j2date`
closed form, the deep-BC validity note, and the **2000-01-01 internal epoch**
self-asserts are [verified-by-code] against `datetime.c` @ `eed6c0d33e09`.
