---
source_url: https://www.postgresql.org/docs/current/datetime-posix-timezone-specs.html
fetched_at: 2026-07-12T19:53:20Z
anchor_sha: eed6c0d33e09
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "B.7 POSIX Time Zone Specifications"
---

# Docs distilled — POSIX Time Zone Specifications (datetime-posix-timezone-specs)

The fallback zone-string grammar PG accepts when a `TimeZone` value isn't a
known IANA name — and its infamous **reversed sign convention**.

## Non-obvious claims

- **POSIX offsets are POSITIVE west of Greenwich — the opposite of every other
  offset in PostgreSQL.** "The positive sign is used for zones *west* of
  Greenwich. (Note that this is the opposite of the ISO-8601 sign convention
  used elsewhere in PostgreSQL.)" So `EST5EDT` means EST = **UTC+5 west** (i.e.
  what ISO-8601 writes as `-05`). This is the single biggest datetime-config
  footgun. [from-docs]
- **Grammar:** `STD offset [ DST [ dstoffset ] [ , rule ] ]`, where the DST
  transition `rule` is `dstdate[/dsttime],stddate[/stdtime]`. If `dstoffset` is
  omitted it defaults to one hour ahead of standard; transition times default to
  `02:00:00`. [from-docs]
- **Three transition-date formats, with a Feb-29 quirk** [from-docs]:
  - `n` — plain day-of-year `0–364` (365 in leap years), Feb 29 *counted*.
  - `Jn` — ordinal day `1–365` where **Feb 29 is never counted**, even in a
    leap year (so `Jn` is leap-stable).
  - `Mm.w.d` — month `m` (1–12), occurrence `w` (1–4, or **5 = last**),
    weekday `d` (0=Sun…6=Sat). e.g. `M3.2.0` = 2nd Sunday of March.
- **IANA is tried first; POSIX is the fallback.** A `TimeZone` string is looked
  up in the IANA database first (getting full historical transitions); only if
  not found is it parsed as a POSIX spec. [from-docs]
- **Four names look like POSIX specs but are actually IANA files:** `EST5EDT`,
  `CST6CDT`, `MST7MDT`, `PST8PDT` "are treated as named time zones because (for
  historical reasons) there are files by those names in the IANA time zone
  database" — so they carry *real* US historical transitions, unlike a
  hand-written POSIX string. [from-docs]
- **There is zero validation of a POSIX spec — misspellings silently "work".**
  "`SET TIMEZONE TO FOOBAR0` will work, leaving the system effectively using a
  rather peculiar abbreviation for UTC." [from-docs] And POSIX specs "are
  inadequate to deal with the complexity of real-world time zone history" — use
  IANA names when history matters.
- **Worked example** `CET-1CEST,M3.5.0,M10.5.0/3` = Paris 2020: standard `CET`
  at UTC+1 (note `-1` under the west-positive convention → east of UTC),
  daylight `CEST` (implicit +2), spring-forward last Sunday of March @ 02:00,
  fall-back last Sunday of October @ 03:00. [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/datetime-config-files.md]] — the *abbreviation-set*
  configuration path, the third way (beside IANA names and POSIX specs) that PG
  resolves a zone token.
- [[knowledge/docs-distilled/datetime-invalid-input.md]] — the spring/fall
  boundaries a POSIX rule defines are exactly where the invalid/ambiguous-input
  resolution kicks in.
- [[knowledge/docs-distilled/runtime-config-client.md]] — `TimeZone` is a
  `PGC_USERSET` client GUC; this page defines its accepted string forms.

## Confidence

All [from-docs] — grammar/sign-convention/validation reference. The
reversed-sign and no-validation bullets are the load-bearing gotchas for
anyone debugging a wrong-offset report.
