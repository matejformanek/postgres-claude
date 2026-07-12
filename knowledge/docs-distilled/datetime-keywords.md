---
source_url: https://www.postgresql.org/docs/current/datetime-keywords.html
fetched_at: 2026-07-12T19:52:10Z
anchor_sha: eed6c0d33e09
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "B.3 Date/Time Key Words"
---

# Docs distilled — Date/Time Key Words (datetime-keywords)

The static token tables the datetime decoder searches for non-numeric fields:
month names, day-of-week names, and field modifiers. The user-facing listing of
the backend's `datetktbl` array.

## Non-obvious claims

- **Three keyword categories, all served from static tables** [from-docs]:
  - Month names (Table B.1): full (`January`…`December`) + abbrevs
    (`Jan`…`Dec`; `Sept` is an accepted alt for `Sep`; `May` has no abbrev).
  - Day-of-week names (Table B.2): full + abbrevs, with multi-spelling
    tolerance (`Tue`/`Tues`, `Wed`/`Weds`, `Thu`/`Thur`/`Thurs`).
  - Field modifiers (Table B.3): `AM` (before 12:00), `PM` (on/after 12:00),
    `T` (next field is time), `JULIAN`/`JD`/`J` (next field is a Julian Date),
    and the **noise words `AT` / `ON`** which are simply *ignored*.
- **Day-of-week names are validated but otherwise ignored.** A weekday name in
  input is checked for internal consistency but does not set any field — it's
  effectively decorative. [from-docs] (Matches the noise-word treatment of
  `AT`/`ON`.)
- **The tables are alphabetically sorted and binary-searched, not hashed or
  linearly scanned.** [verified-by-code] `datetktbl`
  `src/backend/utils/adt/datetime.c:106`, searched by `datebsearch()` (`:4303`,
  invoked at `:3275`); the sibling **`deltatktbl`** holds `interval`-unit
  keywords and is searched the same way (`:4205`). `datebsearch` prechecks the
  first character before `strncmp` for speed and uses `strncmp` so **truncated
  tokens still match** (`TOKMAXLEN`). [verified-by-code] `datetime.c:4303-4327`.
- **Recognition is case-insensitive via lowercasing before lookup.** The decoder
  lowercases the token (`lowtoken`) before calling `datebsearch`.
  [verified-by-code] `datetime.c:3275` (`datebsearch(lowtoken, …)`).
- **Timezone abbreviations are a *separate*, configurable table — not in this
  static list.** Month/day/modifier keywords are compiled-in and fixed; zone
  abbreviations come from the current IANA zone + the `timezone_abbreviations`
  file set and are searched against a distinct `zoneabbrevtbl->abbrevs` table.
  [verified-by-code] `datetime.c:3205`/`:3444`. See
  `datetime-config-files` for that side.

## Links into corpus

- [[knowledge/files/src/backend/utils/adt/datetime.c.md:46]] — documents
  `datetktbl` (`:106`) + the `datebsearch` (`:4303`) mechanism and the
  static-vs-dynamic (TZ/DTZ/DYNTZ) token split.
- [[knowledge/docs-distilled/datetime-input-rules.md]] — the decode algorithm
  that consults these tables for alphabetic tokens.
- [[knowledge/docs-distilled/datetime-config-files.md]] — the *configurable*
  zone-abbreviation tables that sit beside this static keyword set.

## Confidence

Table contents + modifier semantics are [from-docs]. The binary-search
mechanism, case handling, truncated-token matching, and the separate zone-abbrev
table are [verified-by-code] against `datetime.c` @ `eed6c0d33e09`.
