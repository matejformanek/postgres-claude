---
source_url: https://www.postgresql.org/docs/current/datetime-config-files.html
fetched_at: 2026-07-12T19:52:40Z
anchor_sha: eed6c0d33e09
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "B.4 Date/Time Configuration Files"
---

# Docs distilled — Date/Time Configuration Files (datetime-config-files)

How the **input-side** timezone-abbreviation tables are configured on disk: the
`.../share/timezonesets/` files, their grammar, and the
`timezone_abbreviations` GUC that selects one.

## Non-obvious claims

- **Two abbreviation sources, IANA-first.** With a `TimeZone` set to an IANA
  zone, that zone's own abbreviations are recognized preferentially (e.g.
  `TimeZone='America/New_York'` → `EST`=UTC-5, `EDT`=UTC-4). Any abbreviation
  *not* found in the current zone is then sought in the file named by
  `timezone_abbreviations`. [from-docs] So the GUC is "primarily useful for
  allowing datetime input to recognize abbreviations for time zones other than
  the current zone."
- **These abbreviations are input-only.** "These abbreviations will not be used
  in datetime output" — output always uses the current zone's rules. [from-docs]
- **File grammar (`.../share/timezonesets/<file>`)** [from-docs]:
  - `zone_abbrev offset` — integer **seconds** from UTC, positive = east
    (so US-East standard = `-18000`).
  - `zone_abbrev offset D` — the trailing `D` marks the abbrev as *daylight*
    time rather than standard.
  - `zone_abbrev time_zone_name` — defer to an IANA zone; the meaning is the
    one "currently in use at the timestamp whose value is being determined"
    (i.e. historically correct, but costlier).
  - `@INCLUDE file_name` — nest another file from the same directory.
  - `@OVERRIDE` — allow later entries to override earlier ones (e.g. from an
    included file); without it, a duplicate abbreviation definition is an
    **error**, not a silent last-wins.
- **Fixed-integer offsets are deliberately cheaper than name references.** "Using
  a simple integer `offset` is preferred when defining an abbreviation whose
  offset from UTC has never changed, as such abbreviations are much cheaper to
  process than those that require consulting a time zone definition." [from-docs]
  This is the whole reason abbreviations aren't just IANA aliases.
- **`timezone_abbreviations` accepts only alphabetic file names — a security
  guard, not a style rule.** The prohibition on non-alphabetic characters
  "prevents reading files outside the intended directory, as well as reading
  editor backup files and other extraneous files." [from-docs] Hence the shipped
  reference files with dots (`Africa.txt`, `America.txt`) **cannot** be selected
  directly; only `Default`, `Australia`, `India`, etc. can.
- **`Default` = all non-conflicting worldwide abbreviations; region files layer
  on top.** `Australia` and `India` `@INCLUDE Default` first, then add/override.
  This is why `SAT` means *South Australian Standard Time* under the `Australia`
  set, colliding intentionally with the "Saturday" reading elsewhere. [from-docs]
- **These files are not covered by `pg_dump`.** They live in the install tree,
  so custom abbreviation sets are the admin's manual backup responsibility.
  [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/datetime-keywords.md]] — the *static*
  month/day/modifier keyword tables that sit beside these *configurable*
  zone-abbrev tables.
- [[knowledge/docs-distilled/datetime-input-rules.md]] — the decode step that
  consults the current-zone abbreviations then the `timezone_abbreviations` set.
- [[knowledge/docs-distilled/datetime-posix-timezone-specs.md]] — the other way
  to name a zone at input time (POSIX spec vs abbreviation set vs IANA name).
- [[knowledge/docs-distilled/locale.md]] — sibling locale-configuration surface
  (LC_* vs `timezone_abbreviations` are two of the runtime-configurable locale
  axes).

## Confidence

All [from-docs] — this is a configuration/format reference page with no
distinct backend struct to code-verify beyond the `datebsearch(…, zoneabbrevtbl
->abbrevs, …)` lookup already cited in `datetime-keywords.md`.
