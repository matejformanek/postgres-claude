---
source_url: https://www.postgresql.org/docs/current/pgarchivecleanup.html
fetched_at: 2026-07-18
anchor_sha: 03480907e9ff
app: src/bin/pg_archivecleanup/pg_archivecleanup.c
---

# pg_archivecleanup — prune obsolete WAL from an archive

A tiny standalone utility (also usable as `archive_cleanup_command`) that deletes
every WAL segment in a directory that logically **precedes** a given
"oldest-to-keep" segment. The canonical use is on a standby, where the server
substitutes the restartpoint segment for `%r`.

## Non-obvious claims

- As `archive_cleanup_command = 'pg_archivecleanup <archivedir> %r'`, **`%r`
  expands to the oldest WAL segment the standby still needs** (its current
  restartpoint). pg_archivecleanup then removes everything older, keeping the
  transient replay-staging archive minimal. `[from-docs]`
- **Safety scope is the key rule**: this is only valid when the archive is a
  *transient staging area for a single standby*. Pointing it at a long-term or
  multi-consumer archive silently destroys WAL another consumer still needs.
  `[from-docs]`
- **The comparison deliberately ignores the timeline ID.** The deletion test is
  `strcmp(walfile + 8, exclusiveCleanupFileName + 8) >= 0` — it skips the first 8
  hex chars (the TLI) and compares only the 16-char log+segment portion. So
  cleanup is timeline-agnostic: a segment is kept iff its log/segment number is
  `>=` the threshold, regardless of which timeline produced it.
  `[verified-by-code source/src/bin/pg_archivecleanup/pg_archivecleanup.c:139]`
- A `%r` (or CLI) argument may be a `.partial` or `.backup` filename; the tool
  parses off the suffix with `sscanf` and uses only the leading segment name as
  the threshold — so you can safely feed it a `.backup` filename and it keeps the
  base backup's start segment and later.
  `[verified-by-code source/src/bin/pg_archivecleanup/pg_archivecleanup.c:198-231]`
- It **ignores** anything in the directory that isn't a WAL segment, a `.partial`,
  or (with `-b`) a backup-history file — so stray files aren't touched.
  `[verified-by-code source/src/bin/pg_archivecleanup/pg_archivecleanup.c:122-123]`
- `-x <ext>`/`--strip-extension` strips a compression suffix (e.g. `.gz`) before
  the name comparison, so a gzip'd archive can still be ordered/pruned by segment
  name. `[verified-by-code source/src/bin/pg_archivecleanup/pg_archivecleanup.c:87]`
- `-b`/`--clean-backup-history` additionally removes backup-history (`.backup`)
  files that precede the threshold; without it those are left in place.
  `[verified-by-code source/src/bin/pg_archivecleanup/pg_archivecleanup.c:290,321]`
- `-n`/`--dry-run` prints the segments that *would* be removed (no deletion);
  `-d`/`--debug` narrates "keep … and later" + each "removing file" to stderr.
  `[verified-by-code source/src/bin/pg_archivecleanup/pg_archivecleanup.c:149,327,378]`

## Links into corpus

- WAL segment naming (`TTTTTTTTLLLLLLLLSSSSSSSS`) whose byte layout the +8 offset
  exploits: `[[knowledge/docs-distilled/wal-internals.md]]`,
  `[[knowledge/docs-distilled/pgwaldump.md]]`.
- Restartpoints on a standby that produce `%r`: `[[knowledge/docs-distilled/wal-configuration.md]]`,
  `hot-standby.md`.
- Continuous archiving + `archive_command`/`restore_command` context this
  complements: `[[knowledge/docs-distilled/continuous-archiving.md]]`,
  `[[knowledge/docs-distilled/backup-file.md]]`, the `backup-and-recovery` skill.
