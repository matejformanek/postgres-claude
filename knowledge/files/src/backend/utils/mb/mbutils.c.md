# `src/backend/utils/mb/mbutils.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~1960
- **Source:** `source/src/backend/utils/mb/mbutils.c`

The encoding-conversion runtime: every byte that crosses the
client-encoding / server-encoding boundary or that gets stored under a
db-encoding goes through here.

## Key API surface

- `pg_do_encoding_conversion(src, len, src_enc, dest_enc)` and the
  thinner `pg_server_to_client` / `pg_client_to_server` /
  `pg_any_to_server` / `pg_server_to_any` — these wrap conversion-proc
  lookup + fmgr dispatch.
- `pg_verify_mbstr(encoding, str, len, noError)` / `pg_verify_mbstr_len`
  — validity check without conversion. ERRORs on invalid sequences
  unless `noError`.
- `pg_mbstrlen`, `pg_mbcliplen`, `pg_mbstrlen_with_len` — character
  counting in the current encoding.
- `cliplen(str, len, limit)` — safe truncation that won't split a
  multibyte char.

## "Same-encoding return as-is" idiom

> "The functions return a palloc'd, null-terminated string if conversion
> is required. However, if no conversion is performed, the given source
> string pointer is returned as-is." [from-comment] (`mbutils.c:6-11`)

This means callers must **not** unconditionally pfree the result. The
standard wrapper pattern is `if (converted != original) pfree(converted)`.

## Cached lookups

- `ClientEncoding` GUC drives `pg_get_client_encoding()`. On client-
  encoding change (via `SET client_encoding`), `SetClientEncoding`
  looks up the (client, server) conversion procs and caches their OIDs +
  fmgr info so per-message conversion is one fmgr call.
- Per-database default encoding fixed at `initdb` time, exposed via
  `GetDatabaseEncoding()`.

## Notable

- `pg_unicode_to_server` / `pg_server_to_unicode` for JSON, XML, regex
  paths that go via UTF-8 internally even when the server encoding is
  something else.
- Built-in pseudo-conversions: `latin1↔SQL_ASCII` etc. trivial paths
  skip fmgr.
- Conversions are pluggable: `pg_conversion` catalog rows + the
  conversion procs in `conversion_procs/`.
