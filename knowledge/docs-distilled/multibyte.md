---
source_url: https://www.postgresql.org/docs/current/multibyte.html
fetched_at: 2026-07-06T00:00:00Z
anchor_sha: a8c2547eaac7
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18; body numbers §23.3, ToC §24.3)
primary: false
---

# Docs distilled — §24.3: Character Set Support

Server vs client encoding, the `pg_conversion`-driven automatic conversion
between them, the UTF-8 hub, and the `SQL_ASCII` "no conversion" pseudo-
encoding. Maps directly to the recurring `encoding-conversion` corpus gap.

## Server-encoding restriction (not every charset can be a server encoding)

- **Server-capable**: `UTF8`, all `EUC_*`, `LATIN1`-`LATIN10`, `ISO_8859_*`,
  `KOI8R/U`, `WIN*`, `MULE_INTERNAL`, `SQL_ASCII`. `[from-docs]`
- **Client-only** (never a server encoding): `SJIS`, `SHIFT_JIS_2004`,
  `BIG5`, `GBK`, `GB18030`, `UHC`, `JOHAB` — these are stateful/ASCII-
  ambiguous multibyte sets unsafe for internal storage. `[from-docs]`
- Each DB's server encoding must be compatible with its `LC_CTYPE`/
  `LC_COLLATE` (§24.1): under `C`/`POSIX` any charset is allowed; under other
  *libc* locales exactly one charset works. Windows exception: UTF-8 works
  with any locale. `[from-docs]`

## server_encoding vs client_encoding + automatic conversion

- `server_encoding` is set by `initdb -E …` (or `CREATE DATABASE …
  ENCODING`), stored in `pg_database`. `client_encoding` is per-session.
  `[from-docs]`
- Conversion between the two is driven by **`pg_conversion`**: PG converts
  between any pair for which a conversion function is listed; the one flagged
  *default* for that (source,dest) pair is used automatically. Add your own
  with `CREATE CONVERSION name FOR 'src' TO 'dest' FROM func`. `[from-docs]`
- Set client encoding via `SET client_encoding TO 'SJIS'` / SQL-standard
  `SET NAMES 'SJIS'`, psql `\encoding SJIS`, env `PGCLIENTENCODING`, the
  `client_encoding` GUC, or libpq. `[from-docs]`
- A character with no representation in the target encoding → hard error
  (e.g. EUC_JP server → LATIN1 client with Japanese data). `[from-docs]`
- **UTF-8 is the hub**: it converts to/from every supported encoding, so it
  bridges pairs lacking a direct conversion. `[from-docs]`

## SQL_ASCII — the "no conversion" pseudo-encoding

- `SQL_ASCII` means "no assumptions": bytes 0-127 are ASCII, 128-255 are
  uninterpreted, and **no encoding conversion is ever performed** when either
  side is `SQL_ASCII`. `[from-docs]`
- Verified in code: `pg_do_encoding_conversion()` returns the source
  untouched when the destination *or* source encoding is `PG_SQL_ASCII`.
  `[verified-by-code]`
  source/src/backend/utils/mb/mbutils.c:377-380
  (`if (dest_encoding == PG_SQL_ASCII) return src; … if (src_encoding ==
  PG_SQL_ASCII) …`), with the same short-circuit in the fast-path guards at
  mbutils.c:137-138 and :239-240.
- `PG_SQL_ASCII = 0` is deliberately the first/default encoding id.
  `[verified-by-code]` source/src/include/mb/pg_wchar.h:76 (with the comment
  "PG_SQL_ASCII is default encoding and must be = 0" at :67). The full
  encoding enum runs to `_PG_LAST_ENCODING_` at pg_wchar.h:121.

## Links into corpus

- Locale/`LC_CTYPE` compatibility constraint: [docs-distilled/locale.md](./locale.md)
- Encoding-conversion internals (mbutils, pg_wchar) live under
  source/src/backend/utils/mb/ — `pg_do_encoding_conversion` at
  mbutils.c:365, `SetClientEncoding` at mbutils.c:217.
- NLS/message-encoding side: [docs-distilled/nls.md](./nls.md),
  [docs-distilled/nls-programmer.md](./nls-programmer.md).
- Relevant skills: `catalog-conventions` (pg_conversion), `fmgr-and-spi`
  (a CREATE CONVERSION proc is a C function).
