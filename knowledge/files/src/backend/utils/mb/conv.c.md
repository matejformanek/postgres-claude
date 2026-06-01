# `src/backend/utils/mb/conv.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~580
- **Source:** `source/src/backend/utils/mb/conv.c`

Shared helpers used by the per-encoding conversion procs in
`conversion_procs/`. Lookup-by-table + binary-search utility for the
many "Unicode ↔ legacy encoding" mapping tables that ship with PG:

- `LocalToUtf` / `UtfToLocal` — generic single-byte/Unicode conversion
  driven by a sorted `pg_local_to_utf` / `pg_utf_to_local` mapping table
  plus an optional combined-character map for multi-codepoint cases
  (used by GB18030, JOHAB, Shift-JIS).
- `pg_ascii2mic` / `pg_mic2ascii` / `latin2mic` / `mic2latin` and many
  more — the trivial pairwise conversions for ASCII-superset encodings.
- `pg_verify_mbstr_len` plumbing.

All these procs are SQL-callable via `pg_conversion` rows. [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
