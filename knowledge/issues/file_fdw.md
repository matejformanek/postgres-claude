# Issues — `contrib/file_fdw`

Per-subsystem issue register for **file_fdw**, the file-system
Foreign Data Wrapper (CSV/TEXT files or external programs as
foreign tables). 1 source file / 1 340 LOC. **The in-tree
path-traversal-class module.**

**Parent doc:** `knowledge/files/contrib/file_fdw/file_fdw.c.md`.

**Source:** 15 entries surfaced 2026-06-09 by A12-4.

## Headlines

1. **file_fdw is single-layer trust** — relies entirely on
   `pg_read_server_files` / `pg_execute_server_program` predefined-
   role membership. **Diverges from A11's postgres_fdw two-layered
   `password_required` gold standard.**

2. **`filename`/`program` validation: NONE.** No `..` check, no
   in-data-dir check, no absolute-path-only check, no symlink
   refusal, no `O_NOFOLLOW`, no `S_ISREG` mode-check. Comment at
   `:279-285` explicitly acknowledges: "putting this sort of
   permissions check in a validator is a bit of a crock" — the
   `valid_options[]` table restricting `filename`/`program` to
   FT-level (not SERVER/USER MAPPING) is what closes the otherwise-
   gaping hole.

3. **Inherits A6 pg_rewind's symlink-TOCTOU surface** — PG's
   file-open path lacks `O_NOFOLLOW` system-wide. For a
   `pg_read_server_files` holder who creates an FT against
   `/data/some_link`, the link can be swapped between ANALYZE and
   SELECT to change the file's identity silently.

4. **`program` option = shell command at backend's UID.** Same
   defense (`pg_execute_server_program` role) but argv handling
   delegates entirely to COPY's option parser.

## Cross-sweep references

- **A11 postgres_fdw** is the gold-standard contrast — two-layered
  `password_required` + SCRAM passthrough + runtime re-check via
  `pgfdw_security_check`.
- **A6 pg_rewind `O_NOFOLLOW` gap** is INHERITED here.
- **A2 + A4 + A5 + A6 secret-scrub cluster** — file_fdw is the only
  contrib module that opens server-side files from SQL; the file
  contents are read into bytea/text on the server side without any
  scrub discipline.

## Entries (15)

- [ISSUE-defense-in-depth: NO path-traversal sanitization (no `..`
  reject, no symlink reject, no in-data-dir restriction) (likely)]
  — `source/contrib/file_fdw/file_fdw.c:279-285` — comment
  acknowledges the gap; closes via role-gate only.
- [ISSUE-security: inherits A6 pg_rewind's `O_NOFOLLOW` gap —
  symlink TOCTOU between ANALYZE and SELECT (maybe)].
- [ISSUE-defense-in-depth: `program` option = shell command at
  backend's UID; argv handling delegates to COPY parser (likely)].
- [ISSUE-correctness: encoding option not verified against server
  encoding (nit)].
- [ISSUE-correctness: `copy_options` passthrough — any privilege
  amplification by COPY-side options inherited (nit)].
- [ISSUE-correctness: EOF behavior / partial-read recovery — hostile
  file with intentional truncation = incorrect query results
  without error (maybe)].
- [ISSUE-defense-in-depth: block-device / pipe / character-device
  as filename accepted; no `S_ISREG` check (nit)].
- [ISSUE-correctness: NULL-byte in file row handling — CSV row
  containing `\0` (nit)].
- [ISSUE-concurrency: reading concurrently with the writer; no
  atomicity guarantee (nit)].
- [ISSUE-api-shape: validator runs at CREATE/ALTER time only; no
  runtime re-check vs postgres_fdw's `pgfdw_security_check`
  (likely)].
- [ISSUE-audit-gap: no audit log entry on FT-creation or open
  (nit)].
- [ISSUE-defense-in-depth: `valid_options[]` is the ONLY thing
  blocking SERVER/USER-MAPPING-level `filename`/`program`
  inheritance (likely)] — `source/contrib/file_fdw/file_fdw.c:279-
  285`.
- [ISSUE-correctness: `program` option output captured then COPY-
  parsed; piping protocol assumptions (nit)].
- [ISSUE-documentation: comment "a bit of a crock" is the canonical
  acknowledgement (nit)].
- [ISSUE-defense-in-depth: no length cap on filename string; very
  long paths could waste catalog space (nit)].
