```
pg_dump: Avoid NULL deref on empty --exclude-schema argument

When --exclude-schema was passed an empty string, pg_dump's pattern
processing dereferenced a NULL pointer instead of treating the empty
pattern as "match nothing" or producing a clear error.  This crashed
pg_dump before any dump output was produced.

Reject an empty pattern argument up front with a clear error message,
matching the treatment of other --exclude-* options.

Reported-by: Bob Smith <bob@example.com>
Reviewed-by: Tom Lane <tgl@sss.pgh.pa.us>
Discussion: https://postgr.es/m/CAB7nPqTexample@mail.gmail.com
```

Notes:
- Subject uses the `pg_dump:` subsystem prefix (lowercase, module + colon),
  imperative mood, no trailing period, under ~64 chars.
- **No `Author:` line** — the committer is the sole patch author here, so
  per PG convention we omit `Author:` entirely rather than writing
  `Author: <self>`. (Matches `08127c641c0`.)
- Body is prose explaining *why* and *what*, wrapped near 72-76 cols.
- No `Backpatch-through:` because this is master-only.
- Trailer order: `Reported-by:`, `Reviewed-by:`, `Discussion:`. Each tag at
  column 0, one per line.
- `Discussion:` uses `https://postgr.es/m/<message-id>` shortener
  (https preferred over http).
- No `Co-Authored-By: Claude` trailer, no `Signed-off-by`, no
  conventional-commits prefix (`fix:`).
