# Issues — `pg_combinebackup`

Per-subsystem issue register for the `src/bin/pg_combinebackup`
utility (introduced PG17 alongside incremental backup). See
`knowledge/issues/README.md` for the tag convention.

**Parent subsystem doc:** _none yet_ (covered only at file level
under `knowledge/files/src/bin/pg_combinebackup/`).

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | src/bin/pg_combinebackup/pg_combinebackup.c:1100,1162 | correctness | likely | Line 1100 borrows `mfile->checksum_payload` from the manifest hash; line 1162 unconditionally `pfree`s it — possible free of hash-owned memory or double-free across iterations | open | knowledge/files/src/bin/pg_combinebackup/pg_combinebackup.c.md §Potential issues |
| 2026-06-11 | src/bin/pg_combinebackup/pg_combinebackup.c:674-678 | security | likely | Inconsistent `data_checksum_version` across input backups is warned but not blocked; can produce a combined cluster whose pg_control claims checksums-on while reconstructed pages carry stale per-page checksums | open | knowledge/files/src/bin/pg_combinebackup/pg_combinebackup.c.md §Potential issues |
| 2026-06-11 | src/bin/pg_combinebackup/reconstruct.c:663-676 | undocumented-invariant | maybe | Missing-block→zero-fill assumption is unverifiable; documented in comment but no manifest-based audit | open | knowledge/files/src/bin/pg_combinebackup/reconstruct.c.md §Potential issues |
| 2026-06-11 | src/bin/pg_combinebackup/copy_file.c:217 | correctness | likely | Write-side `close()` not error-checked on `copy_file_blocks` `dest_fd`; missed late-error reports on filesystems that flush at close | open | knowledge/files/src/bin/pg_combinebackup/copy_file.c.md §Potential issues |
| 2026-06-11 | src/bin/pg_combinebackup/copy_file.c (clone/link/copy_file_range) | undocumented-invariant | nit | clone/link/copy_file_range strategies double-read source from disk when `--manifest-checksums` is requested | open | knowledge/files/src/bin/pg_combinebackup/copy_file.c.md §Potential issues |
| 2026-06-11 | src/bin/pg_combinebackup/load_manifest.c:247 | correctness | likely | `combinebackup_version_cb` accepts any manifest version ≥ 2 silently; a future v3 with breaking semantics surfaces only as later parse errors | open | knowledge/files/src/bin/pg_combinebackup/load_manifest.c.md §Potential issues |
| 2026-06-11 | src/bin/pg_combinebackup/write_manifest.c:174 | doc-drift | nit | `Manifest-Checksum` is hard-coded SHA-256 regardless of `--manifest-checksums`; not documented | open | knowledge/files/src/bin/pg_combinebackup/write_manifest.c.md §Potential issues |
| 2026-06-11 | src/bin/pg_combinebackup/pg_combinebackup.c:567 | stale-todo | maybe | XXX comment notes overly-strict cross-backup LSN equality check; should accept `start_lsn > check_lsn` if within switchpoint | open | knowledge/files/src/bin/pg_combinebackup/pg_combinebackup.c.md §Potential issues |
| 2026-06-11 | src/bin/pg_combinebackup/pg_combinebackup.c:1083-1102 | undocumented-invariant | nit | Missing manifest entry is warned but tolerated; pg_combinebackup is not a manifest verifier — documented nowhere | open | knowledge/files/src/bin/pg_combinebackup/pg_combinebackup.c.md §Potential issues |
| 2026-06-11 | src/bin/pg_combinebackup/backup_label.c:151 | question | maybe | `INCREMENTAL FROM `-prefix-based strip could silently drop a future field with the same prefix | open | knowledge/files/src/bin/pg_combinebackup/backup_label.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|

## Notes

- The most security-significant finding is the data_checksum
  inconsistency warning (line 674-678): users with a chain of
  backups taken across a checksum toggle can produce a cluster
  that fails CRC checks on first read. The warning recommends
  user action but doesn't enforce it.
- The double-pfree concern at line 1100/1162 deserves manual
  re-verification with cassert + valgrind on a multi-file
  combine run. Worth raising on pgsql-hackers if confirmed.
- The manifest-checksum algorithm being hard-coded SHA-256 is
  consistent with backend behaviour
  (`backup/backup_manifest.c:AddWALInfoToBackupManifest`) but
  worth a docs patch.
