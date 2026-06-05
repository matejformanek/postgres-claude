# Issues — `fe_utils`

Per-subsystem issue register for `src/fe_utils/` (PostgreSQL
frontend-shared utility code, linked into psql, pg_dump,
pg_basebackup, reindexdb/vacuumdb, etc.). See
`knowledge/issues/README.md` for the tag convention, severity scale,
and workflow.

**Parent corpus:** `knowledge/files/src/fe_utils/*.md` (per-file docs).
Surfaced during the A11 `src/fe_utils` sweep (cloud/pg-file-backfiller,
2026-06-04), anchor `4b0bf0788b0`.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-04 | string_utils.c:44 | undocumented-invariant | maybe | `fmtId`/`fmtIdEnc` return a shared `static` buffer; callers must consume before the next call or get silent aliasing (`fmtId(a).fmtId(b)` → `b.b`); no compile-time guard | open | knowledge/files/src/fe_utils/string_utils.c.md §Potential issues |
| 2026-06-04 | string_utils.c:600 | undocumented-invariant | maybe | `appendShellString` shell-injection safety rests entirely on the `strspn` allowlist + single-quote wrap; widening the safe-set would reintroduce injection | open | knowledge/files/src/fe_utils/string_utils.c.md §Potential issues |
| 2026-06-04 | string_utils.c:701 | question | nit | `appendConnStrVal` `needquotes` control flow (init true, last-iteration decides) is non-obvious; empty value correctly quoted `''` but fragile under edits | open | knowledge/files/src/fe_utils/string_utils.c.md §Potential issues |
| 2026-06-04 | string_utils.c:451 | stale-todo | nit | `appendStringLiteralConn` pre-v19 `escape_string_warning` kluge gated on `PQserverVersion < 190000`, to remove when pre-v19 out of support | open | knowledge/files/src/fe_utils/string_utils.c.md §Potential issues |
| 2026-06-04 | mbprint.c:294 | undocumented-invariant | maybe | `pg_wcsformat` writes into a caller buffer with no length param; correctness depends on a matching prior `pg_wcssize` call (same string + encoding); "keep in sync" is comment-only | open | knowledge/files/src/fe_utils/mbprint.c.md §Potential issues |
| 2026-06-04 | mbprint.c:396 | correctness | nit | `mbvalidate` is a no-op for non-UTF-8 multibyte encodings; malformed bytes reach the terminal (cosmetic; width math still advances by `PQmblen`) | open | knowledge/files/src/fe_utils/mbprint.c.md §Potential issues |
| 2026-06-04 | astreamer_tar.c:305 | undocumented-invariant | maybe | client trusts server tar metadata verbatim (name/size/mode/uid/gid/type); only `isValidTarHeader` + non-empty name + `path_is_safe_for_extraction` validate — concrete realization of the A4 trust-the-stream finding | open | knowledge/files/src/fe_utils/astreamer_tar.c.md §Potential issues |
| 2026-06-04 | astreamer_tar.c:312 | question | nit | server-supplied tar `member.size` has no ceiling; flows to per-member `fwrite` loop → malicious server forces arbitrarily large local files (disk-exhaustion analogue of A5) | open | knowledge/files/src/fe_utils/astreamer_tar.c.md §Potential issues |
| 2026-06-04 | astreamer_file.c:248 | question | maybe | absolute symlink `linktarget` short-circuits past `path_is_safe_for_extraction` and is handed to `symlink()`; intentional for tablespace mappings but a server-controlled arbitrary-target symlink under basepath (defense-in-depth gap) | open | knowledge/files/src/fe_utils/astreamer_file.c.md §Potential issues |
| 2026-06-04 | astreamer_file.c:336 | question | nit | no `O_NOFOLLOW`/`O_EXCL` on extracted file/dir creation; extraction into a pre-populated/mutated basepath follows pre-existing symlinks and overwrites | open | knowledge/files/src/fe_utils/astreamer_file.c.md §Potential issues |
| 2026-06-04 | astreamer_gzip.c:286 | question | nit | gzip decompressor caps resident memory (256 KB) but has no cumulative decompressed-output cap (output/disk bomb dimension of A5) | open | knowledge/files/src/fe_utils/astreamer_gzip.c.md §Potential issues |
| 2026-06-04 | astreamer_lz4.c:313 | question | nit | lz4 decompressor caps resident memory (~256 KB) but no cumulative output cap | open | knowledge/files/src/fe_utils/astreamer_lz4.c.md §Potential issues |
| 2026-06-04 | astreamer_zstd.c:296 | question | nit | zstd decompressor caps resident memory (`ZSTD_DStreamOutSize()`) but no cumulative output cap | open | knowledge/files/src/fe_utils/astreamer_zstd.c.md §Potential issues |
| 2026-06-04 | recovery_gen.c:57 | undocumented-invariant | maybe | conninfo skip-list omits `password`, so a base-backup password is written (escaped, cleartext) into `primary_conninfo` in `postgresql.auto.conf` and left unscrubbed in freed heap — canonical "secret to disk" site | open | knowledge/files/src/fe_utils/recovery_gen.c.md §Potential issues |
| 2026-06-04 | connect_utils.c:44 | undocumented-invariant | maybe | cached plaintext prompted `password` is `free()`d without zeroing on reuse-reset and retry; consistent with frontend/libpq (cluster-wide secret-scrub property, not a local regression) | open | knowledge/files/src/fe_utils/connect_utils.c.md §Potential issues |
| 2026-06-04 | parallel_slot.c:333 | leak | maybe | `connect_slot` stores the conn in the slot before `executeCommand` runs `initcmd`; no live leak today (`executeCommand` exits on failure) but a future non-exiting error path would orphan the conn | open | knowledge/files/src/fe_utils/parallel_slot.c.md §Potential issues |
| 2026-06-04 | parallel_slot.c:43 | undocumented-invariant | nit | "free the `PGresult` yourself on NULL/false return" contract lives only in a comment; a non-conforming `ParallelSlotResultHandler` leaks every failed result | open | knowledge/files/src/fe_utils/parallel_slot.c.md §Potential issues |
| 2026-06-04 | version.c:64 | correctness | maybe | `memcpy(*version_str, buf, st.st_size)` copies file-length bytes from a `%63s`-filled buffer → copies uninitialized trailing bytes and does not guarantee NUL-termination; bounded by 64-byte dest (no overflow), harmless on well-formed `PG_VERSION` | open | knowledge/files/src/fe_utils/version.c.md §Potential issues |
| 2026-06-04 | print.c:776 | correctness | maybe | `width_total` + per-format border overhead accumulate into a 32-bit `unsigned int`; cell-count overflow is guarded at init (`:3203`) but the display-width sum is not range-checked — could wrap on multi-GB-wide output (practically unreachable) | open | knowledge/files/src/fe_utils/print.c.md §Potential issues |
| 2026-06-04 | print.c:3706 | doc-drift | nit | `PRINT_LATEX_LONGTABLE` vertical case dispatches to the non-longtable `print_latex_vertical` (intentional — longtable only differs horizontally) but is unannotated at the switch site; reads like a copy-paste bug | open | knowledge/files/src/fe_utils/print.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|

## Notes

- **Secret-scrub cluster extension (9th + 10th installments).**
  `recovery_gen.c:57` (password written cleartext into `primary_conninfo`
  in `postgresql.auto.conf`) and `connect_utils.c:44` (prompted password
  `free()`d without zeroing) join the corpus-wide secret-scrub cluster:
  libpq (A2) + psql/streamutil/initdb (A4) + common (A5) + pg_upgrade
  (A6) + walreceiver `primary_conninfo` window (A8). The fe_utils sites
  are *frontend* mirrors — they share the "no `explicit_bzero` on free"
  property that a `SecretBuf` type (proposed hosting site
  `src/include/common/secretbuf.h`, A5) would close in one series.
  `recovery_gen.c` is notable as the canonical **secret-to-disk** anchor
  (the others are secret-in-freed-heap).

- **Backup-stream-trust (A4) confirmed at its source.** `astreamer_tar.c`
  IS the trust boundary A4's pg_basebackup sweep flagged: server-supplied
  tar name/size/mode/uid/gid drive local `mkdir`/`fopen`/`chmod`. The
  mitigations are real and layered — `path_is_safe_for_extraction`,
  non-empty-name rejection, and a hard `pg_fatal` on PAX extended headers
  (closing the classic "PAX long-name overrides safe ustar name"
  traversal vector). The residual is an *invariant* (server is the trust
  root for base backups), not a bug. `astreamer_file.c:248` (absolute
  symlink targets bypass the path check, for tablespace mappings) is the
  one place worth a second look.

- **Decompression-bomb (A5) nuance.** The gzip/lz4/zstd streamers are
  **streaming with a fixed-size output buffer** (~256 KB /
  `ZSTD_DStreamOutSize()`), so — unlike `pg_lzcompress` (A5) — they do
  **not** over-allocate RAM. A5's "no input/output ratio bound" holds for
  *cumulative output / disk*, but the resident-memory bomb is mitigated
  by the streaming design. The disk dimension is shared with
  `astreamer_tar.c:312` (unbounded `member.size`).

- **Identifier-quoting chokepoint (A4 gap closed).** `string_utils.c`
  hosts `fmtId`/`fmtQualifiedId`/`processSQLNamePattern`/`patternToSQLRegex`
  + `appendShellString` — the shared identifier-quoting + name-pattern
  helpers A4 flagged as a corpus gap. Safety rests on the `fmtId`
  shared-static-buffer discipline (`:44`) and the `appendShellString`
  allowlist (`:600`); both are correct-today/implicit-invariant. Worth a
  future `knowledge/idioms/safe-sql-identifiers.md` joining
  `processSQLNamePattern` (A4) + `patternToSQLRegex` (A6) +
  `quoteOneName`/`ri_triggers.c` (A7).

- **Frontend conventions confirmed throughout.** All 18 files use
  `pg_malloc`/`pg_free`/`pstrdup` (not palloc) and `pg_log_error`/
  `pg_fatal`/`exit()` (not ereport/elog) — the A4/A5 frontend-conventions
  theme holds cleanly across `src/fe_utils`.
