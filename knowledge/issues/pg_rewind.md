# Issues — `pg_rewind` (src/bin/pg_rewind/)

Per-subsystem issue register for pg_rewind — the **divergent-cluster
rewind tool** that overwrites a target data dir with bytes fetched from
a source (libpq or local).

**Parent docs:** `knowledge/files/src/bin/pg_rewind/*` (13 docs).

**Source:** 53 entries surfaced 2026-06-03 by the A6 foreground sweep
(batches B3 + B4).

pg_rewind's trust posture mirrors A4's pg_basebackup — the source is
authenticated but **not validated**. Unique to pg_rewind: the source
controls **which files exist on the target** (a null bytea response →
unlink the target file), and **symlink targets** flow from source to
`symlink(2)` without validation.

---

## P0 — Phase D candidates

### Symlink + path-traversal cluster (the headline)

**pg_rewind uses zero `O_NOFOLLOW` anywhere.** Combined with the source's
ability to supply arbitrary `symlink()` targets, this is a real
escape-the-data-dir primitive.

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | file_ops.c:65,225,201,285,302,268 | trust-boundary | likely | **NO `O_NOFOLLOW` ANYWHERE** — `open_target_file`, `truncate_target_file`, `remove_target_file`, `create_target_symlink`, `remove_target_symlink`, `remove_target_dir` all dereference pre-existing symlinks at the resolved location | open | knowledge/files/src/bin/pg_rewind/file_ops.c.md |
| 2026-06-03 | file_ops.c:285 | trust-boundary | likely | **`create_target_symlink` writes attacker-influenced link target** — `entry->source_link_target` flows straight into `symlink(link, dstpath)` with no validation; combined with no-`O_NOFOLLOW`, a malicious source can plant arbitrary symlinks the next pg_rewind run dereferences | open | knowledge/files/src/bin/pg_rewind/file_ops.c.md |
| 2026-06-03 | file_ops.c:478 | path-traversal | likely | `recurse_dir` follows symlinks recursively in `pg_tblspc` and `pg_wal` — combined with above = traverse out of data directory across repeated rewinds | open | knowledge/files/src/bin/pg_rewind/file_ops.c.md |
| 2026-06-03 | filemap.h | trust-boundary | likely | `file_entry_t.source_link_target` is opaque server-supplied bytes used as `symlink()` target — no abs-path/length/`..` validation beyond `MAXPGPATH` | open | knowledge/files/src/bin/pg_rewind/filemap.h.md |
| 2026-06-03 | pg_rewind.c | trust-boundary | likely | Server-controlled `source_link_target` flows into `symlink(2)` at `file_ops.c:285` — duplicate of above for orchestration layer | open | knowledge/files/src/bin/pg_rewind/pg_rewind.c.md |
| 2026-06-03 | filemap.c | trust-boundary | maybe | Server-controlled paths flow into filehash and through `getFileContentType`'s `sscanf` without rejection of leading `/` or `..` segments; path safety relies entirely on file_ops.c writer functions | open | knowledge/files/src/bin/pg_rewind/filemap.c.md |
| 2026-06-03 | parsexlog.c:324 | trust-boundary | maybe | `SimpleXLogPageRead` opens WAL segments without `O_NOFOLLOW`; symlink at `<datadir>/pg_wal/<segname>` silently dereferenced; blast radius limited by `XLogReadRecord` content validation | open | knowledge/files/src/bin/pg_rewind/parsexlog.c.md |
| 2026-06-03 | local_source.c | trust-boundary | nit | Source `open()` lacks `O_NOFOLLOW` — same gap on the read side | open | knowledge/files/src/bin/pg_rewind/local_source.c.md |
| 2026-06-03 | filemap.c:846 | stale-todo | nit | XXX "Should we check if [an existing symlink] points to the same target?" — currently no; symlink target equality is not verified | open | knowledge/files/src/bin/pg_rewind/filemap.c.md |

**Phase D pitch — pg_rewind symlink hardening:**
1. Add `O_NOFOLLOW` to every `open(target)` in `file_ops.c` (6 sites).
2. Validate `source_link_target` before `symlink(2)`: reject absolute paths outside data dir; reject `..` traversal; cap length.
3. Reject any source-claimed file path containing `..` or leading `/` at filemap-build time, not at write time.
4. Add an explicit check that existing symlinks point where source claims (close the 2010-era XXX).

### Server-controlled file delete + truncate primitives

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | libpq_source.c:562 | trust-boundary | likely | **`pg_read_binary_file()` returning null bytea = `remove_target_file(filename, missing_ok=true)`** — server-controlled delete primitive; guarded only by `path_is_safe_for_extraction` inside unlink helper | open | knowledge/files/src/bin/pg_rewind/libpq_source.c.md |
| 2026-06-03 | rewind_source.h | trust-boundary | likely | Vtable comment for `queue_fetch_file` admits source may report wrong size — no protection against source claiming size=0 for large file so target gets truncated to 0 | open | knowledge/files/src/bin/pg_rewind/rewind_source.h.md |
| 2026-06-03 | filemap.c | trust-boundary | maybe | `process_target_wal_block_change` ignores blocks where `end_offset > source_size`; malicious source claiming `source_size=0` for a relation file would cause every WAL-touched block to be dropped from `target_pages_to_overwrite`, then TRUNCATE shrinks the file to 0 | open | knowledge/files/src/bin/pg_rewind/filemap.c.md |
| 2026-06-03 | libpq_source.c:583 | trust-boundary | maybe | Source can serve truncated tail (chunksize < requested length); pg_rewind writes only truncated bytes, leaving target file shorter than source claimed | open | knowledge/files/src/bin/pg_rewind/libpq_source.c.md |
| 2026-06-03 | rewind_source.h | trust-boundary | maybe | No integrity check (checksum/HMAC) at vtable layer — correctness relies entirely on transport security and source role privileges | open | knowledge/files/src/bin/pg_rewind/rewind_source.h.md |

### State-transition: no atomicity

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | pg_rewind.c:529 | state-transition | likely | **No marker file or atomic switch** — "point of no return" comment explicit; crash between first overwrite and final `update_controlfile()` leaves target with arbitrary mix of source/target bytes while `pg_control.state` still claims clean shutdown; no way to detect partial rewind on re-run | open | knowledge/files/src/bin/pg_rewind/pg_rewind.c.md |
| 2026-06-03 | pg_rewind.c | trust-boundary | maybe | Local-source pg_control change is fatal, but mid-run modification of any other local-source file is silently tolerated (filemap was built from stale snapshot); XXX at line 656-659 acknowledges | open | knowledge/files/src/bin/pg_rewind/pg_rewind.c.md |
| 2026-06-03 | pg_rewind.c:746 | stale-todo | nit | "TODO Check that there's no backup_label in either cluster" — sanityChecks does not check despite comment | open | knowledge/files/src/bin/pg_rewind/pg_rewind.c.md |
| 2026-06-03 | parsexlog.c | state-transition | maybe | Any unrecognized WAL record with attacker-influenced rmgr → `pg_fatal` rather than safe-skip | open | knowledge/files/src/bin/pg_rewind/parsexlog.c.md |

### Secret-scrub (A2/A4/A5/A6 echo)

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | pg_rewind.c | secret-scrub | maybe | `connstr_source` (may contain `password=...`) held in memory entire run; passed verbatim to `GetDbnameFromConnectionOptions`; may end up in `primary_conninfo` via `GenerateRecoveryConfig` if `--write-recovery-conf` used. No explicit scrub or warn-on-cleartext | open | knowledge/files/src/bin/pg_rewind/pg_rewind.c.md |
| 2026-06-03 | libpq_source.c | secret-scrub | maybe | No scrub of `connstr_source` memory; pg_rewind has NO `simple_prompt` callsite (uses libpq's pgpass/env path) but the connstring itself is exposed | open | knowledge/files/src/bin/pg_rewind/libpq_source.c.md |

---

## P1 — Correctness, undocumented invariants, DoS

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | datapagemap.c | dos | maybe | Malicious WAL with absurd block numbers can drive `pg_realloc` of the bitmap to bound size | open | knowledge/files/src/bin/pg_rewind/datapagemap.c.md |
| 2026-06-03 | datapagemap.c | undocumented-invariant | nit | Signed int offset / bitmapsize encodes ~2 GiB relation cap | open | knowledge/files/src/bin/pg_rewind/datapagemap.c.md |
| 2026-06-03 | datapagemap.c | correctness | nit | `datapagemap_next` is O(MaxBlock) per relation — slow for sparse maps | open | knowledge/files/src/bin/pg_rewind/datapagemap.c.md |
| 2026-06-03 | datapagemap.h | undocumented-invariant | nit | Bitmapsize as signed int caps relation size | open | knowledge/files/src/bin/pg_rewind/datapagemap.h.md |
| 2026-06-03 | file_ops.c | stale-todo | nit | "TODO: But complain if we're processing the wrong dir" preserved | open | knowledge/files/src/bin/pg_rewind/file_ops.c.md |
| 2026-06-03 | file_ops.c | undocumented-invariant | nit | `dstfd` cache key compares paths — pointer-vs-string ambiguity | open | knowledge/files/src/bin/pg_rewind/file_ops.c.md |
| 2026-06-03 | file_ops.c | correctness | nit | `write_target_range` fabricates ENOSPC when actual error is different | open | knowledge/files/src/bin/pg_rewind/file_ops.c.md |
| 2026-06-03 | file_ops.h | undocumented-invariant | nit | Every write function silently goes through dstfd cache — caller-side invariant | open | knowledge/files/src/bin/pg_rewind/file_ops.h.md |
| 2026-06-03 | filemap.c:112 | undocumented-invariant | maybe | `excludeDirContents` and `excludeFiles` are hand-maintained copies of basebackup.c's exclusion lists — drift leaks files into rewind that basebackup would skip | open | knowledge/files/src/bin/pg_rewind/filemap.c.md |
| 2026-06-03 | filemap.c | undocumented-invariant | nit | `final_filemap_cmp` relies on `file_action_t` enum ordering: `CREATE < COPY < COPY_TAIL < NONE < TRUNCATE < REMOVE` — refactor risk | open | knowledge/files/src/bin/pg_rewind/filemap.c.md |
| 2026-06-03 | filemap.c:761 | dead-code | nit | `.DS_Store` substring skip hardcoded outside `excludeFiles[]` | open | knowledge/files/src/bin/pg_rewind/filemap.c.md |
| 2026-06-03 | filemap.c:588 | undocumented-invariant | nit | `getFileContentType` only treats main fork as RELATION; FSM/VM are FILE_CONTENT_TYPE_OTHER (always full-copied) | open | knowledge/files/src/bin/pg_rewind/filemap.c.md |
| 2026-06-03 | filemap.h | undocumented-invariant | nit | `file_action_t` enum ordering is load-bearing for `final_filemap_cmp`; `static_assert` would help | open | knowledge/files/src/bin/pg_rewind/filemap.h.md |
| 2026-06-03 | filemap.h | undocumented-invariant | nit | `target_pages_to_overwrite` meaningful only when `content_type == FILE_CONTENT_TYPE_RELATION`; not enforced at type level | open | knowledge/files/src/bin/pg_rewind/filemap.h.md |
| 2026-06-03 | libpq_source.c | wire-protocol | maybe | `libpq_traverse_files` uses single non-snapshot `WITH RECURSIVE pg_ls_dir()` walk; not transaction-snapshot consistent | open | knowledge/files/src/bin/pg_rewind/libpq_source.c.md |
| 2026-06-03 | libpq_source.c:363 | undocumented-invariant | nit | `queue_fetch_range` coalesces requests by pointer equality of path strings, not strcmp | open | knowledge/files/src/bin/pg_rewind/libpq_source.c.md |
| 2026-06-03 | libpq_source.c | dos | nit | `MAX_CHUNK_SIZE = 1 MiB`, `MAX_CHUNKS_PER_QUERY = 1000` → up to ~1 GiB bytea per call; slow client + large source could OOM server | open | knowledge/files/src/bin/pg_rewind/libpq_source.c.md |
| 2026-06-03 | libpq_source.c | undocumented-invariant | nit | `init_libpq_conn` requires `full_page_writes=on` but doesn't check `wal_level` | open | knowledge/files/src/bin/pg_rewind/libpq_source.c.md |
| 2026-06-03 | local_source.c | correctness | nit | Same-size mid-run mutation of source not detected | open | knowledge/files/src/bin/pg_rewind/local_source.c.md |
| 2026-06-03 | local_source.c | dos | nit | `local_queue_fetch_file` allocates one `PGIOAlignedBlock` per call | open | knowledge/files/src/bin/pg_rewind/local_source.c.md |
| 2026-06-03 | parsexlog.c | correctness | maybe | Checkpoint record payload `memcpy(&checkPoint, XLogRecGetData(...), sizeof(CheckPoint))` lacks explicit length assert; depends on `XLogReader` upstream validation | open | knowledge/files/src/bin/pg_rewind/parsexlog.c.md |
| 2026-06-03 | parsexlog.c | stale-todo | nit | "consider also switching timeline accordingly" preserved | open | knowledge/files/src/bin/pg_rewind/parsexlog.c.md |
| 2026-06-03 | parsexlog.c | dos | nit | `pg_fatal`-on-first-bad-record gives no diagnostic context | open | knowledge/files/src/bin/pg_rewind/parsexlog.c.md |
| 2026-06-03 | pg_rewind.c | undocumented-invariant | nit | `ensureCleanShutdown` invokes postgres in single-user mode by passing `template1` on stdin via `/dev/null` | open | knowledge/files/src/bin/pg_rewind/pg_rewind.c.md |
| 2026-06-03 | pg_rewind.c | wire-protocol | nit | `pg_current_wal_insert_lsn()` read after copying files for live primary | open | knowledge/files/src/bin/pg_rewind/pg_rewind.c.md |
| 2026-06-03 | pg_rewind.c:998 | dead-code | nit | `createBackupLabel` deliberately omits LABEL: line — may confuse tools | open | knowledge/files/src/bin/pg_rewind/pg_rewind.c.md |
| 2026-06-03 | pg_rewind.h | undocumented-invariant | nit | `WalSegSz` read before set by `digestControlFile()` — order is currently fine but invariant implicit | open | knowledge/files/src/bin/pg_rewind/pg_rewind.h.md |
| 2026-06-03 | pg_rewind.h | undocumented-invariant | nit | Progress counters are uint64 globals with no atomicity; single-threaded so works | open | knowledge/files/src/bin/pg_rewind/pg_rewind.h.md |
| 2026-06-03 | rewind_source.h | undocumented-invariant | nit | `destroy()` comment says it doesn't close PGconn but only libpq impl; future caller swapping impls could leak | open | knowledge/files/src/bin/pg_rewind/rewind_source.h.md |
| 2026-06-03 | timeline.c | dos | nit | `pg_realloc_array` per parsed line is O(n²) | open | knowledge/files/src/bin/pg_rewind/timeline.c.md |
| 2026-06-03 | timeline.c | correctness | maybe | Hand-maintained copy of similar code in `src/backend/access/transam/timeline.c` — drift risk | open | knowledge/files/src/bin/pg_rewind/timeline.c.md |
| 2026-06-03 | timeline.c | correctness | nit | Line termination handling drops final partial line | open | knowledge/files/src/bin/pg_rewind/timeline.c.md |
| 2026-06-03 | timeline.c | undocumented-invariant | nit | In-place mutation of caller's buffer | open | knowledge/files/src/bin/pg_rewind/timeline.c.md |

---

## Cross-corpus pattern reinforcement

### pg_rewind is the mirror image of pg_basebackup (A4) — different from pg_dump (A3)

| Aspect | pg_basebackup (A4) | pg_rewind (A6) |
|---|---|---|
| Source bytes | Server-controlled tar stream | Server-controlled `pg_read_binary_file()` bytea |
| File modes | Server-supplied `data_directory_mode` honored | **Local-only** `pg_mode_mask` (better posture) |
| Paths | `spclocation` accepted; `archive_name` sanitized but inner-tar delegated to astreamer_tar.c | `source_link_target` accepted unchecked; path-traversal not blocked at filemap-build |
| Symlinks | Not analyzed (out of scope) | **`O_NOFOLLOW` absent everywhere** — worse than basebackup |
| Atomicity | Backup is single-shot, no in-place writes | **No marker file** — partial rewind = inconsistent target |
| Delete primitive | None | **Yes** — null bytea = unlink |

pg_rewind's posture is **worse than pg_basebackup** because it writes in-place into the target's data dir.

### Secret-scrub (no `simple_prompt`, but connstr lifetime)

Unlike A2/A4/A5/A6-pg_upgrade, pg_rewind has **no `simple_prompt` callsite** — credentials come from `libpq` via pgpass/env. But the `connstr_source` (which may contain `password=...`) is held for the whole run and can end up in `primary_conninfo` via `GenerateRecoveryConfig` if `--write-recovery-conf` is used. Different shape, same class.

---

## Summary by tag type

| Type | Count |
|---|---:|
| trust-boundary | 16 |
| undocumented-invariant | 17 |
| correctness | 6 |
| dos | 5 |
| state-transition | 3 |
| stale-todo | 3 |
| secret-scrub | 2 |
| path-traversal | 1 |
| dead-code | 2 |
| wire-protocol | 2 |
| **Total** | **57** (some entries double-tagged) |

Severity headline: ~8 `likely`, ~12 `maybe`, rest `nit`. THE Phase D
pitch in order of impact: (1) **`O_NOFOLLOW` on every file_ops.c
open**, (2) **validate `source_link_target` before `symlink(2)`**, (3)
**atomicity marker file** to detect partial rewinds on retry, (4)
**reject null-bytea-means-delete** or require explicit deletion list.
