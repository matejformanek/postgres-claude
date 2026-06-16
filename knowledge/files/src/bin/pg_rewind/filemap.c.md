# filemap.c

**Source:** `source/src/bin/pg_rewind/filemap.c` (956 lines)

## Purpose

The central diff algorithm of pg_rewind. Collects per-file metadata
from both source and target into a hash table keyed by relative path,
overlays the set of WAL-touched blocks on the target, then runs
`decide_file_action()` per entry to choose one of seven
`file_action_t` outcomes (NONE / CREATE / COPY / COPY_TAIL / TRUNCATE
/ REMOVE / UNDECIDED-fatal). Sorts the result so directory creation
precedes file population and child removals precede their parents.
[verified-by-code]

Header: `filemap.h` (124 lines).

## Role in pg_rewind

This is the brain of pg_rewind. `pg_rewind.c:main()` populates the
hash via three callbacks:

- `process_source_file()` — once per file in the source datadir (via
  `source->traverse_files`, filemap.c:280).
- `process_target_file()` — once per file in the target datadir
  (via `traverse_datadir()` in `file_ops.c`, filemap.c:316).
- `process_target_wal_block_change()` — once per block modified in
  target WAL between the divergence checkpoint and end-of-target-WAL
  (via `extractPageMap()` in `parsexlog.c`, filemap.c:353).

Then `decide_file_actions(last_common_segno)` (filemap.c:923) loops
over the hash, calls `decide_file_action()` per entry, copies pointers
into a `filemap_t.entries[]` array, and `qsort()`s them with
`final_filemap_cmp`. The sorted array is returned to `pg_rewind.c`
for execution.

## Key functions

- `filehash_init()` — creates the simplehash with initial size 1000
  (filemap.c:197-200). [verified-by-code]
- `insert_filehash_entry(path)` / `lookup_filehash_entry(path)` —
  thin wrappers over the simplehash macros instantiated at lines
  42-52. Path is the hash key, `strcmp` is the equality function.
  [verified-by-code]
- `keepwal_init()` + `keepwal_add_entry(path)` + static
  `keepwal_entry_exists(path)` — a second hash table to mark WAL
  segment files that must NOT be removed even if they don't exist
  on the source. Populated from `parsexlog.c` when reading WAL.
  (filemap.c:243-270). [verified-by-code]
- `process_source_file(path, type, size, link_target)` —
  filemap.c:280-308. Treats `pg_wal` as a directory even when it's a
  symlink (lines 290-291). Fatals if a path that looks like a
  relation file isn't `FILE_TYPE_REGULAR` (line 297-298). Fatals on
  duplicate source entries (line 303). [verified-by-code]
- `process_target_file(path, type, size, link_target)` —
  filemap.c:316-341. Mirror of process_source_file. Note: it does
  **not** filter via `check_file_excluded()` — that's deliberate so
  excluded files present on the target end up with `target_exists=1`
  and `source_exists=0`, then decide_file_action turns them into
  REMOVE for files inside the excluded set on the source side
  (filemap.c:321-325 comment). [from-comment]
- `process_target_wal_block_change(forknum, rlocator, blkno)` —
  filemap.c:353-404. Looks up the segment file the block belongs to;
  if the file is regular in target and exists in source, and the
  block offset is within both file sizes, adds the block to
  `entry->target_pages_to_overwrite`. Out-of-range / missing-source
  cases are intentionally ignored: a later TRUNCATE or REMOVE on
  the file is enough. [verified-by-code]
- `check_file_excluded(path, is_source)` — filemap.c:409-471. Two
  passes: (a) substring match on `/pgsql_tmp` prefix or
  `/pgsql_tmp/` (lines 419-423); (b) basename match against
  `excludeFiles[]` (with optional prefix-mode); (c) prefix match
  against `excludeDirContents[]` directory names. [verified-by-code]
- `getFileContentType(path)` — filemap.c:567-661. Classifier:
  WAL (path starts `pg_wal/` + name matches `IsXLogFileName`),
  RELATION (sscanf one of three layouts for `global/`, `base/db/`,
  `pg_tblspc/...`), OTHER otherwise. Cross-checks the parsed
  `RelFileLocator` by calling `relpathperm()` and `strcmp`ing the
  result — defends against a path like `base/1/12345.foo` matching
  the `%u.%u` sscanf. [verified-by-code]
- `decide_wal_file_action(fname, last_common_segno, source_size,
  target_size)` — filemap.c:718-743. WAL segments strictly before
  the last common segment and with matching size → NONE; otherwise
  → COPY. [verified-by-code]
- `decide_file_action(entry, last_common_segno)` — filemap.c:748-915.
  The main per-file decision tree:
  - `XLOG_CONTROL_FILE` → NONE (handled specially after the loop).
  - Paths containing `.DS_Store` → NONE (macOS junk skip).
  - Excluded-by-filter + present-on-target → REMOVE; excluded +
    absent on target → NONE.
  - Source-only → CREATE (dir/symlink) or COPY (regular).
  - Target-only → REMOVE, **unless** present in `keepwal` hash.
  - Both-exist + different types → fatal.
  - Path ending `PG_VERSION` → NONE (paranoia).
  - Both-exist + both directory or both symlink → NONE (symlinks
    NOT checked for target equality — XXX comment line 846-847).
  - Both-exist + regular + WAL → delegate to
    `decide_wal_file_action`.
  - Both-exist + regular + non-relation → COPY (in toto).
  - Both-exist + regular + relation → COPY_TAIL (if target
    smaller), TRUNCATE (if target larger), or NONE (equal sizes,
    rely on `target_pages_to_overwrite`).
  [verified-by-code]
- `decide_file_actions(last_common_segno)` — filemap.c:923-955.
  Iterates hash, calls decide_file_action, dumps into
  `filemap_t.entries[]`, qsorts. [verified-by-code]
- `final_filemap_cmp(a, b)` — filemap.c:694-709. Sort key is
  `(action, path)` with REMOVE sorted by **reverse** path so
  children remove before parents. [verified-by-code]
- `calculate_totals(filemap)` — filemap.c:499-538. Sum source_size
  per regular file → `total_size`; sum bytes that will actually be
  copied (whole COPY + tail of COPY_TAIL + BLCKSZ per dirty block in
  target_pages_to_overwrite) → `fetch_size`. [verified-by-code]
- `print_filemap(filemap)` — debug dump. [verified-by-code]

## State / globals

- `filehash` (static `filehash_hash *`) — main hash. Created in
  `filehash_init`. [verified-by-code]
- `keepwal` (static `keepwal_hash *`) — secondary hash for WAL
  preservation. Created in `keepwal_init`. [verified-by-code]
- `excludeDirContents[]` (filemap.c:117-152) — `pg_stat_tmp`,
  `pg_replslot`, `pg_dynshmem`, `pg_notify`, `pg_serial`,
  `pg_snapshots`, `pg_subtrans`. Best-effort kept-in-sync with
  `basebackup.c`. [from-comment]
- `excludeFiles[]` (filemap.c:158-191) — `postgresql.auto.conf.tmp`,
  `current_logfiles.tmp`, `pg_internal.init*`, `backup_label`,
  `tablespace_map`, `backup_manifest`, `postmaster.pid`,
  `postmaster.opts`. [verified-by-code]

## Phase D notes

**The decide_file_action algorithm is the core trust gate.** It runs
on every path the source listed, plus every path the target had.
There is no integrity check on file *contents*: if the source says
"replace base/1/12345 with these 8192 bytes" the target gets those
bytes. The action decision protects against (a) wrong file *types*
(fatal), (b) accidentally removing required WAL (keepwal hash), and
(c) misidentifying a non-relation file as a relation file
(`getFileContentType` cross-check at line 650-658).

**Path safety is NOT checked here.** All `path_is_safe_for_extraction`
calls live in `file_ops.c` (open_target_file, create_target_dir,
create_target_symlink, remove_target_file, remove_target_dir,
remove_target_symlink). filemap.c trusts the path strings the source
hands it. A malicious source that returned a path containing `../`
would be caught at write time but pollutes the in-memory hash with
attacker-controlled keys.

**Symlinks are not cross-checked.** Line 846-847 XXX:
"Should we check if it points to the same target?" — the answer
today is "no". If source `pg_tblspc/16384` points to `/tmp/A` and
target's already points to `/tmp/B`, pg_rewind silently leaves
target pointing at `/tmp/B`. Two consequences:
1. After rewind, the target may reference a tablespace path that no
   longer matches the source's catalog state — likely caught at WAL
   replay or first query, but undocumented.
2. A target previously compromised by adversary-controlled tablespace
   symlink will NOT be cleaned up by pg_rewind.

**`backup_label` exclusion is asymmetric vs reality.** The exclusion
list (line 175) suppresses `backup_label` from the file diff, but
`createBackupLabel` in pg_rewind.c always creates a fresh
`backup_label` for the rewind. The TODO at pg_rewind.c:746 ("Check
that there's no backup_label in either cluster") is unimplemented.

**`.DS_Store` skip is macOS-specific dead-ish code** (line 761-762)
— this is the kind of "skip junk" code that should arguably live in
the same excludeFiles[] table.

## Potential issues

- `[ISSUE-trust-boundary: server-controlled paths flow into the filehash and through getFileContentType's sscanf without rejection of leading "/" or ".." segments; path safety relies entirely on the writer functions in file_ops.c (medium)]`
- `[ISSUE-undocumented-invariant: excludeDirContents and excludeFiles are hand-maintained copies of basebackup.c's exclusion lists per the comment at filemap.c:112-115; drift can leak files into a rewind that basebackup would skip (low)]`
- `[ISSUE-stale-todo: filemap.c:846-847 "XXX: Should we check if it points to the same target?" for symlinks at decide_file_action — symlink target equality is not verified (low)]`
- `[ISSUE-trust-boundary: process_target_wal_block_change ignores blocks where end_offset > source_size; a malicious source claiming source_size=0 for a relation file would cause every WAL-touched block to be dropped from target_pages_to_overwrite, then TRUNCATE would shrink the file to 0 (low — requires malicious source that already controls bytes)]`
- `[ISSUE-undocumented-invariant: final_filemap_cmp relies on file_action_t enum value ordering being CREATE < COPY < COPY_TAIL < NONE < TRUNCATE < REMOVE; a future refactor of the enum would silently break action ordering (low)]`
- `[ISSUE-dead-code: filemap.c:761 hardcodes ".DS_Store" substring skip outside excludeFiles[]; either move to the list or document why this is special (low)]`
- `[ISSUE-undocumented-invariant: getFileContentType only treats main fork as RELATION (comment line 588-591); FSM/VM forks are FILE_CONTENT_TYPE_OTHER and always full-copied, which is correct but worth a static check (low)]`

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_rewind`](../../../../issues/pg_rewind.md)
<!-- issues:auto:end -->
