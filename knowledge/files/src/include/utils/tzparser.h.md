# `utils/tzparser.h` — timezone-abbreviation config file parser

**Verified against source pin `4b0bf0788b0`** (path:
`source/src/include/utils/tzparser.h`)

## Role

Loads `share/timezonesets/*` files (e.g. `Default`, `Australia`, `India`)
into a `TimeZoneAbbrevTable` consumed by datetime.c when parsing timestamp
strings that use bare zone abbreviations (`EST`, `PDT`, `IST`, …).

## Public API

- `tzEntry { abbrev, zone, offset, is_dst, lineno, filename }` —
  `source/src/include/utils/tzparser.h:23-34`.
- `TimeZoneAbbrevTable *load_tzoffsets(const char *filename)` — `:37`.

## Invariants

- Array of `tzEntry` is sorted by `abbrev` for binary search. [from-comment,
  `:19-20`]
- `abbrev` is downcased. [from-comment, `:26`]
- For a dynamic abbreviation (one resolved from a real zone name like
  `Europe/Prague` rather than a fixed offset), `zone` is non-NULL and
  `offset`/`is_dst` are ignored. [from-comment, `:28-30`]
- Source-tracking fields `lineno`/`filename` exist purely for error messages
  in the parser. [from-comment, `:31-33`]

## Notable internals

The whole struct is allocated by the parser and lives in the timezone
abbrev cache for the postmaster lifetime (re-parsed on
`timezone_abbreviations` GUC change).

## Trust-boundary / Phase D surface

- `filename` comes from the `timezone_abbreviations` GUC, which is
  `PGC_SIGHUP` (requires superuser-touchable config). Default install
  files are under `share/timezonesets/`. The parser supports `@INCLUDE
  filename` directives; the resolver follows them. A malicious file
  could `@INCLUDE` to a sibling and cause repeated parses → memory growth.
  [ISSUE-resource: tz config @INCLUDE depth not visibly bounded in this
  header (maybe; .c may bound it)]
- The output array allocation grows with the file size. A 100 MB
  abbreviation file would produce ~3-4 MB of `tzEntry` structs (each is
  small but contains string pointers). Header exposes no cap.
  [ISSUE-resource: `load_tzoffsets` array growth unbounded; no
  header-documented limit (maybe)]
- `abbrev` and `zone` are heap strings the parser allocates; the cache
  holds them until reset. Repeated SIGHUP cycles with growing files would
  fragment memory. [ISSUE-resource: memory leak / fragmentation
  on repeated SIGHUP reload (nit)]
- Filename in error messages is the literal config path — if symlinked,
  this could leak the underlying target. Low risk; superuser only.
  [ISSUE-audit-gap: error messages echo full filename path (nit)]

## Cross-refs

- `knowledge/files/src/include/utils/datetime.h` — `TimeZoneAbbrevTable`
  is defined there.
- A14 echo: file-based config inputs without header-level size caps.

<!-- issues:auto:begin -->
- [Issue register — `include-utils`](../../../../issues/include-utils.md)
<!-- issues:auto:end -->

## Issues

1. [ISSUE-resource: `load_tzoffsets` array growth unbounded; no
   header-documented limit on file size or @INCLUDE depth (maybe)] —
   `source/src/include/utils/tzparser.h:37`.
2. [ISSUE-resource: repeated SIGHUP timezone-abbreviation reloads
   fragment memory (nit)] — `source/src/include/utils/tzparser.h:37`.
3. [ISSUE-audit-gap: full filename in tz parser errors leaks symlink
   targets (nit)] — `source/src/include/utils/tzparser.h:33`.
