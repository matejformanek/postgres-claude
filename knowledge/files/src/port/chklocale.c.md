---
path: src/port/chklocale.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 383
depth: deep
---

# src/port/chklocale.c

## Purpose

Determines the **PostgreSQL encoding** that corresponds to the C library's
current locale (or a given `LC_CTYPE` string). This is how `initdb` and
`CREATE DATABASE` derive a sensible default server encoding from the
environment, and how the backend learns the encoding implied by the OS locale.
The core mapping is a static table translating libc codeset names
(`nl_langinfo(CODESET)` on Unix, codepage numbers on Win32) to PG encoding IDs.
`[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int pg_get_encoding_from_locale(const char *ctype, bool write_message)` | `chklocale.c:301` | Returns a `PG_*` encoding id, or -1 if undetermined |
| `int pg_codepage_to_encoding(UINT cp)` | `chklocale.c:267` | Win32-only: map a codepage number to a PG encoding |

## Internal landmarks

- `encoding_match_list[]` (`chklocale.c:45-199`) — the big static table of
  `{ libc codeset string, PG encoding }` pairs. This is the heart of the file;
  everything else looks up here.
- `win32_get_codeset` (`chklocale.c:202-266`) — parses the locale string's
  codepage suffix on Windows when `nl_langinfo` isn't available.
- `pg_get_encoding_from_locale` (`:301-383`) — saves/sets `LC_CTYPE` to the
  requested `ctype`, reads the codeset via `nl_langinfo(CODESET)` (or the Win32
  path), restores the locale, then binary/linear-searches the match list.
  `write_message` controls whether an unrecognized codeset elicits a warning —
  it is suppressed in contexts (like the backend) where `elog` isn't safe or
  wanted.

## Invariants & gotchas

- **Locale is saved and restored** around the `nl_langinfo` probe
  (`pg_get_encoding_from_locale` sets then restores `LC_CTYPE`); failing to
  restore would corrupt the process's locale state. The function is written to
  be callable from early startup where the backend `elog` machinery may not be
  ready — hence the `write_message` flag rather than unconditional `ereport`.
- A return of -1 ("can't determine") is a normal outcome the callers handle, not
  an error per se — e.g. an exotic codeset PG has no encoding for.
- The match table is the drift surface: as libc/ICU add codeset spellings, a
  missing row silently degrades to -1. Low risk, but it is why the table is long
  and platform-conditional.

## Cross-refs

- `knowledge/files/src/backend/utils/mb/encnames.c.md` — PG encoding name/id
  registry the result indexes into.
- `knowledge/files/src/bin/initdb/initdb.c.md` — derives default encoding via
  this.
