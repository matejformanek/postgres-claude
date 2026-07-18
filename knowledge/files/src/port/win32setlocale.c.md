---
path: src/port/win32setlocale.c
anchor_sha: e18b0cb7344
loc: 193
depth: read
---

# src/port/win32setlocale.c

## Purpose

Wrapper around Windows' `setlocale(3)` to paper over two specific bugs
in Microsoft's implementation:

1. **Dots in country names** (`win32setlocale.c:13-22`): `setlocale`
   refuses to accept locale names containing extra dots like
   `"Chinese (Traditional)_Hong Kong S.A.R..950"` *even though*
   `setlocale(LC_ALL, NULL)` will *return* that exact string on those
   locales. Windows accepts alternative abbreviations (e.g. `"HKG"`,
   `"ARE"`, `"ZHM"`) that this file maps to.
2. **Non-ASCII characters in locale names** (`win32setlocale.c:24-31`):
   the Norwegian Bokmål locale is returned as
   `"Norwegian (Bokm\xE5l)_Norway"` with a non-ASCII a-ring byte. The
   encoding of that byte is ambiguous (which locale's codepage?) and
   it ends up in `pg_database`, where it then breaks cross-database
   reads. This file rewrites the result string to the pure-ASCII alias
   `"Norwegian_Norway"`.

`[from-comment]` `[verified-by-code]`

PG always routes `setlocale()` through `pgwin32_setlocale` on Windows
(via macro indirection in `port.h`).

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `char *pgwin32_setlocale(int category, const char *locale)` | `win32setlocale.c:172` | Single entry point; `locale == NULL` is "query current" |

## Internal landmarks

- `struct locale_map` (`win32setlocale.c:39-52`): `{start, end,
  replacement}` triple. With `end == NULL`, replace any occurrence of
  `start` with `replacement`. With `end != NULL`, replace everything
  from `start` through `end` (a poor-man's regex for
  `start.*end`).
- `locale_map_argument[]` (`win32setlocale.c:57-87`): applied to the
  user's *input* before calling real `setlocale`. Maps:
  - `"Hong Kong S.A.R."` → `"HKG"` (one entry).
  - `"U.A.E."` → `"ARE"` (one entry; ISO-3166 three-letter code).
  - Four variants of `"Chinese (Traditional|simplified)_Macau S.A.R..950"`
    → `"ZHM"` (whole-locale rewrite, not just country part). Includes
    `Macao` spelling as well as `Macau` — Windows is inconsistent.
- `locale_map_result[]` (`win32setlocale.c:92-106`): applied to the
  *return value* of real `setlocale`. Two entries map both
  parenthesized and non-parenthesized Bokmål spellings to
  `"Norwegian_Norway"`. The `start, end` two-part form is used
  because the a-ring character is the part being elided.
- `map_locale` (`win32setlocale.c:110-169`) — string-matching engine:
  - `strstr` for the start needle (`:126`).
  - If `end` is set, second `strstr` from past-the-end-of-start
    (`:136`); set `match_end` if found, else clear the match (`:138-141`).
  - Else `match_end = match_start + strlen(needle_start)` (`:143`).
  - Bounds check against `MAX_LOCALE_NAME_LEN` (100, `:108, :155`).
  - Splice: prefix + replacement + suffix into static buffer
    (`:158-161`).
- `pgwin32_setlocale` (`:172-193`):
  1. `map_locale(argument)` if locale != NULL (`:177-180`).
  2. Call real `setlocale(category, argument)` (`:183`).
  3. `map_locale(result)` on the return value (`:189-190`).
  4. `unconstify(char *, ...)` — POSIX says result must not be
     modified by caller, so the `const`-cast is documented as
     innocuous (`:185-188`).

## Invariants & gotchas

- **Single static `aliasbuf[100]` for both input and output mappings**
  (`win32setlocale.c:113`). Calling `pgwin32_setlocale` from two
  threads concurrently can corrupt the buffer. PG is single-threaded
  in startup-time locale selection so this hasn't bitten — but
  third-party Windows clients of libpq could race.
- **`MAX_LOCALE_NAME_LEN` = 100** — locale names longer than this
  after mapping return `NULL` (`win32setlocale.c:156`), which
  `setlocale` callers may misinterpret as "locale rejected" rather
  than "name truncation".
- **The same buffer is reused for the input rewrite and the output
  rewrite** within a single `pgwin32_setlocale` call. The output
  rewrite happens *after* the input rewrite has been consumed by real
  `setlocale`, so they don't overlap — but it means the returned
  pointer is only valid until the next call.
- The Macau/Macao mappings are **alias-rewrites for the whole
  string** (`:77-79`), unlike HKG/ARE which only replace the country
  part. The data layout supports either via `end == NULL`.
- The `ZHM` abbreviation has no clear documentation — the comment
  (`:72-74`) describes it as "must be some legacy naming scheme" that
  empirically works.

## Cross-refs

- `knowledge/files/src/port/chklocale.c.md` — sibling locale-handling
  port file.
- `source/src/backend/utils/adt/pg_locale.c` — primary backend
  consumer.
- `source/src/include/port.h` — macro routing `setlocale` →
  `pgwin32_setlocale` on Windows.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
