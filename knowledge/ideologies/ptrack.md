# ptrack — a lockless shared-memory "changed-block" map fed by smgr write hooks a patched core adds, persisted out-of-band at checkpoint, so incremental backups skip WAL summarization

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `postgrespro/ptrack` @ branch `master` (ptrack 2.4, EXTVERSION 2.4).
> All `file:line` cites below point into THAT repo (not `source/`), since this
> doc characterizes an *external* extension's divergence from core idioms.
> Cites verified against the files fetched on 2026-07-09 (see Sources footer).
> Read alongside `[[knowledge/ideologies/pg_bulkload.md]]` (the corpus's other
> out-of-band-durability / WAL-adjacent extension) and
> `[[knowledge/ideologies/orioledb.md]]` (the other "needs a patched PG core"
> case).

## Domain & purpose

ptrack is "a block-level incremental backup engine for PostgreSQL"
(`README.md:9`) `[from-README]`. It maintains a fixed-size, in-memory **"ptrack
map"** that records, per data block, the LSN at which that block was last
modified. A backup tool — in practice `pg_probackup` — calls the SQL function
`ptrack_get_pagemapset('start_lsn')` to get, for every relation file, a bitmap
of blocks changed since `start_lsn`, and copies only those blocks
(`README.md:88-91`, `ptrack--2.1.sql:16-20`) `[verified-by-code]`. The design
contract is deliberately asymmetric: it "is designed to allow false positives
(i.e. block/page is marked in the `ptrack` map, but actually has not been
changed), but to never allow false negatives (i.e. loosing any `PGDATA`
changes, excepting hint-bits)" (`README.md:11`) `[from-README]`. A false
positive costs one needlessly-copied 8 KB block; a false negative would corrupt
a backup, so the map is engineered to over-approximate.

The reason it earns an ideology entry — and sits beside orioledb rather than
the in-seam extensions — is the sentence in `README.md:13`: "Currently,
`ptrack` codebase is split between small PostgreSQL core patch and extension.
All public SQL API methods and main engine are placed in the `ptrack`
extension, while the core patch contains only certain hooks and modifies binary
utilities to ignore `ptrack.map.*` files" `[from-README]`. Like orioledb,
ptrack cannot be built against stock PostgreSQL: it ships a per-major-version
core patch (`patches/REL_11_STABLE-…` through `patches/REL_18_STABLE-ptrack-core.diff`,
`README.md:15`) `[from-README]` `[verified-by-code]` that adds hook points core
does not expose. Unlike orioledb, the patch is *small* — it adds five hook
call-sites and edits a handful of backup binaries — but it is still a fork
requirement, which is the divergence this doc is about.

Contrast the goal with core's own PG-17 incremental backup
(`WAL_SUMMARIZED` / the WAL summarizer): core answers "which blocks changed?"
by *summarizing the WAL after the fact*; ptrack answers the same question by
*intercepting every block write as it happens* and never reads WAL at all.
Cross-ref `.claude/skills/backup-and-recovery/SKILL.md`,
`[[knowledge/subsystems/replication.md]]`.

## How it hooks into PG

### The extension side: a `shared_preload_libraries` module with no bgworker

ptrack is an ordinary loadable module (`PG_MODULE_MAGIC`, `ptrack.c:56`) that
**must** be preloaded — `_PG_init` hard-errors unless
`process_shared_preload_libraries_in_progress`, telling the user to set
`shared_preload_libraries='ptrack'` (`ptrack.c:97-100`) `[verified-by-code]`.
It registers **no background worker**. Its one GUC, `ptrack.map_size` (in MB,
`PGC_POSTMASTER`, default 0 = disabled, capped at 32 GB on 64-bit / 256 MB on
32-bit), carries an `assign_ptrack_map_size` callback that converts MB to bytes
and refuses to enable when `wal_level` is minimal (`ptrack.c:105-119`,
`engine.c:466-494`) `[verified-by-code]`. `.control` is minimal and
`relocatable = true` (`ptrack.control:1-5`) `[verified-by-code]` — the SQL
surface is schema-relocatable because the *engine* is pinned to the patched
server, not to a schema (the same reasoning orioledb uses).

At `_PG_init` time it chains **six** hooks (`ptrack.c:134-148`)
`[verified-by-code]`; three of the underlying hook *variables do not exist in
core PostgreSQL* and are introduced by the core patch (see below):

| Hook installed (`ptrack.c`) | In core? | Role |
|---|---|---|
| `shmem_request_hook` (PG15+) / `RequestAddinShmemSpace` | yes | reserve `PtrackActualSize` shmem for the map (`ptrack.c:122-159`) |
| `shmem_startup_hook` | yes | allocate/attach the map via `ShmemInitStruct`, init on first create (`ptrack.c:165-195`) |
| `copydir_hook` | **no — patch** | mark every block of files copied by `copydir()` (`CREATE DATABASE`, `ALTER TABLESPACE`) that bypass shared buffers (`ptrack.c:202-244`) |
| `mdwrite_hook` | **no — patch** | mark a block each time `md.c` writes it to disk (`ptrack.c:246-254`) |
| `mdextend_hook` | **no — patch** | mark a block each time a relation is extended (`ptrack.c:256-264`) |
| `ProcessSyncRequests_hook` | **no — patch** | run `ptrackCheckpoint()` — persist the map — inside the checkpointer's fsync phase (`ptrack.c:266-273`) |
| `backup_checkpoint_request_hook` (PG17+) | **no — patch** | stamp `init_lsn` when a base backup requests a checkpoint (`ptrack.c:275-284`) |

Every hook install saves and calls the previous handler
(`prev_*_hook`), the standard well-behaved-chaining idiom
(`ptrack.c:62-69, 135-148`) `[verified-by-code]`. Cross-ref
`.claude/skills/extension-development/SKILL.md`,
`.claude/skills/bgworker-and-extensions/SKILL.md`,
`[[knowledge/idioms/process-utility-hook-chain.md]]`.

### The core-patch side: five new hook variables in the write + sync paths

`patches/REL_17_STABLE-ptrack-core.diff` (391 lines) `[verified-by-code]` adds
the hook *declarations* and call-sites core lacks:

- `mdwrite_hook` / `mdextend_hook` — declared in `src/include/storage/md.h`,
  called from `mdwritev()` and `mdextend()` in `src/backend/storage/smgr/md.c`
  with `reln->smgr_rlocator, forknum, blocknum` (patch lines `67-117, 360-377`)
  `[verified-by-code]`. This is the load-bearing seam: **every buffered write
  the storage manager flushes to disk fires `mdwrite_hook`.**
- `copydir_hook` — declared in `src/include/storage/copydir.h`, called at the
  end of `copydir()` with the destination dir (patch `44-66, 346-357`)
  `[verified-by-code]`.
- `ProcessSyncRequests_hook` — declared in `src/include/storage/sync.h`,
  called from `ProcessSyncRequests()` (the checkpointer's fsync-absorb phase)
  in `src/backend/storage/sync/sync.c` (patch `119-141, 378-390`)
  `[verified-by-code]`.
- `backup_checkpoint_request_hook` — declared in `src/include/access/xlog.h`,
  called from `xlog.c` when a base backup forces a checkpoint (patch
  `1-25, 332-345`) `[verified-by-code]`.

The rest of the patch is **not** hooks — it teaches core's *binary utilities*
about the `ptrack.map*` files so they neither copy transient state nor trip on
them: `basebackup.c`, `miscinit.c` (the `excludeFiles`/`noChecksumFiles`
lists), `pg_checksums.c`, `pg_resetwal.c`, and `pg_rewind/filemap.c` all gain
`ptrack.map` / `ptrack.map.tmp` / `ptrack.map.mmap` entries (patch
`26-43, 142-238, 239-331`) `[verified-by-code]`. `basebackup` is patched to
*copy* `ptrack.map` (it is real state a restored cluster needs) while skipping
the transient `.tmp`/`.mmap` (patch `35-39`) `[verified-by-code]`. This
binary-patching is the cost the README's TODO explicitly flags: "Should we
introduce `ptrack.map_path` … Doing that we will avoid patching PostgreSQL
binary utilities to ignore `ptrack.map.*` files" (`README.md:244`)
`[from-README]`.

## Where it diverges from core idioms

### 1. The map is a lockless shared hash table updated with bare atomic CAS — no LWLock, no buffer, no WAL

Core's shared structures are guarded by LWLocks or spinlocks. ptrack's map is
"completely lockless during the normal PostgreSQL operation" (`README.md:173`)
`[from-README]`: the map is an array of `pg_atomic_uint64` LSN entries
(`PtrackMapHdr.entries[FLEXIBLE_ARRAY_MEMBER]`, `engine.h:50-74`)
`[verified-by-code]`, and both the writer (`ptrack_mark_block`) and the reader
(`ptrack_get_pagemapset`) touch entries with `pg_atomic_read_u64` /
`pg_atomic_compare_exchange_u64` only (`engine.c:602-656`, `ptrack.c:643-676`)
`[verified-by-code]`. `ptrack_mark_block` hashes the block id
(`BID_HASH_FUNC` = `hash_any_extended`, `engine.h:87-90`), derives **two** slots
(`hash % N` and a rotated `((hash<<32)|(hash>>32)) % N`), and for each slot does
a monotone CAS loop that only ever raises the stored LSN — `ptrack_atomic_increase`
spins `while (old < new && !CAS(...))` (`engine.c:602-617, 638-655`)
`[verified-by-code]`. The only lock in the whole engine is `AddinShmemInitLock`
around the one-time `ShmemInitStruct` (`ptrack.c:176-194`) `[verified-by-code]`.

The two-slot scheme is a Bloom-filter-style trick: a block is reported changed
only if **both** its slots hold an LSN `>= start_lsn` (`ptrack.c:656-673`)
`[verified-by-code]`, halving the false-positive rate from hash collisions
while preserving the no-false-negative guarantee (a real write always raises
both slots). The fixed map size is what makes false positives possible at all;
the README recommends `map_size ≈ PGDATA/1000` to keep them rare
(`README.md:82, 171`) `[from-README]`. Contrast core's exact WAL-summary
approach, which never collides. Cross-ref `[[knowledge/subsystems/storage-buffer.md]]`
(the buffer manager whose write-out ptrack shadows via `mdwrite`),
`.claude/skills/locking/SKILL.md`.

### 2. Durability is out-of-band: the map lives only in RAM until checkpoint, then is rewritten atomically to `global/ptrack.map` — it is NOT WAL-logged

This is the sharp divergence, and it directly parallels
`[[knowledge/ideologies/pg_bulkload.md]]`'s "re-implement durability outside
WAL." The map is **never** WAL-logged. Marks accumulate in shared memory and
are flushed to disk exactly once per checkpoint, by `ptrackCheckpoint()` running
on the `ProcessSyncRequests_hook` (`ptrack.c:266-273`, `engine.c:293-464`)
`[verified-by-code]`. The persist path is a hand-rolled atomic-file-replace:

- open `global/ptrack.map.tmp` `O_CREAT|O_TRUNC|O_WRONLY`
  (`PTRACK_PATH_TMP`, `engine.h:28-30`, `engine.c:332-338`) `[verified-by-code]`;
- stream the header + every entry through `ptrack_write_chunk`, which folds each
  chunk into a running `pg_crc32c` (`engine.c:77-92, 357-429`)
  `[verified-by-code]`, buffering `PTRACK_BUF_SIZE == 8000` atomics (64 KB
  writes, tuned for NVMe, `engine.h:32-41`) `[verified-by-code]`;
- append the CRC, `pg_fsync`, `close`, then `durable_rename` the tmp over the
  real file (`engine.c:431-454`) `[verified-by-code]`.

Each entry is read with `pg_atomic_read_u64` while backends may be concurrently
CAS-ing it — the write is a *fuzzy snapshot*, which is safe precisely because a
too-low LSN can only cause a false positive, never a miss (the `TODO: is it
safe and can we do any better?` comment at `engine.c:395` acknowledges the
hand-waving) `[verified-by-code]`. On restart the map is re-read and
CRC-checked by `ptrackMapReadFromFile` (`engine.c:123-223`); a bad magic,
version, size, or CRC is non-fatal — the file is `durable_unlink`'d and a fresh
zeroed map is initialized (`engine.c:176-192, 243-288`) `[verified-by-code]`.
The extra `map_size` of temp-file disk is Limitation #4 in the README
(`README.md:163`) `[from-README]`. Cross-ref
`[[knowledge/idioms/checkpoint-coordination.md]]`,
`[[knowledge/idioms/crash-recovery-startup.md]]`,
`.claude/skills/wal-and-xlog/SKILL.md`.

### 3. Because the map is only checkpoint-durable, correctness leans on `wal_level >= replica` and on `init_lsn`

Not WAL-logging the map creates a crash-recovery gap: writes marked in RAM
since the last checkpoint are lost on a crash. ptrack closes the gap with an
**`init_lsn`** — the LSN of the last map (re)initialization, stored in the map
header (`PtrackMapHdr.init_lsn`, `engine.h:63-64`) `[verified-by-code]` and
exposed as `ptrack_init_lsn()` (`ptrack.c:507-522`). Any backup whose
`start_lsn` predates `init_lsn` must be treated as unreliable by the caller —
the map cannot vouch for changes before it was initialized. `init_lsn` is
stamped lazily: `ptrack_set_init_lsn` sets it (under recovery,
`GetXLogReplayRecPtr`; else `GetXLogInsertRecPtr`) the first time any block is
marked, or at checkpoint if still unset (`engine.c:360-374, 658-680`)
`[verified-by-code]`.

The residual hole is unlogged operations. README Limitation #1: "You can only
use `ptrack` safely with `wal_level >= 'replica'`. Otherwise, you can lose
tracking of some changes if crash-recovery occurs, since certain commands are
designed not to write WAL at all if `wal_level` is minimal, but we only durably
flush `ptrack` map at checkpoint time" (`README.md:157`) `[from-README]` — which
is exactly why `assign_ptrack_map_size` hard-refuses to enable when
`!XLogIsNeeded()` (`engine.c:479-482`) `[verified-by-code]`. This is the same
class of bargain pg_bulkload makes and the mirror image of it: pg_bulkload
*writes* data outside WAL and reconstructs safety with an out-of-band log;
ptrack *observes* data and relies on WAL being on so that crash recovery
re-drives the `mdwrite`/`mdextend` hooks that re-mark the blocks. Cross-ref
`[[knowledge/idioms/hint-bits-setbufferdirty.md]]` (hint-bit writes are the one
documented exception the map deliberately does not guarantee, `README.md:11`).

### 4. The reader walks the physical PGDATA tree by hand, not the catalog

`ptrack_get_pagemapset` does not consult `pg_class`. It re-derives the set of
data files by directly walking `global/`, `base/`, and `pg_tblspc/` on disk
(`ptrack_gather_filelist`, recursively via `AllocateDir`/`ReadDirExtended`,
`ptrack.c:288-411, 569-581`) `[verified-by-code]`, parsing OIDs out of path
components, skipping temp rels (`looks_like_temp_rel_name`) and calling
`parse_filename_for_nontemp_relation` to validate each candidate
(`ptrack.c:307-359`) `[verified-by-code]`. For every block of every segment it
recomputes the two hash slots and probes the map, emitting a `datapagemap_t`
bitmap per file (`ptrack.c:597-677`). This "walk the physical layout, ignore
the catalog" stance is what lets the backup tool run without a normal SQL
session over the relations, and it mirrors the file-oriented world of
`basebackup` / `pg_rewind` rather than the executor. Cross-ref
`.claude/skills/backup-and-recovery/SKILL.md`,
`[[knowledge/subsystems/storage-buffer.md]]`.

### 5. It vendors `datapagemap.c` verbatim from core's `pg_rewind`

The changed-block bitmap type (`datapagemap_t`, `datapagemap_add`,
`datapagemap_iterate/next`) is a **copy of core's `src/bin/pg_rewind/datapagemap.c`**,
carrying the original "Copyright (c) 2013-2020, PostgreSQL Global Development
Group" header (`datapagemap.c:1-12`) `[verified-by-code]`. It is a plain
byte-array bitmap grown with `repalloc` + 10-byte headroom
(`datapagemap.c:27-64`) `[verified-by-code]`. This is the same
source-coupling smell catalogued for pg_bulkload's vendored `nbtsort-NN.c`
(`[[knowledge/ideologies/pg_bulkload.md]]` §5): the useful helper is `static`
frontend code with no public API, so the extension copies it and re-links it
into the backend. Cheaper than pg_bulkload's case (one small stable file, not a
seventeen-arm version ladder), but the same class of dependency.

## Notable design decisions (cited)

- **Two hash slots per block, both-must-match on read.** Writer sets both
  (`engine.c:642-655`); reader only counts a block if slot1 *and* slot2 are
  `>= start_lsn`, and short-circuits slot2 when slot1 misses (`ptrack.c:643-673`)
  `[verified-by-code]`. Halves collision-driven false positives while keeping
  the no-false-negative invariant.
- **Monotone-increase CAS, never decrement.** `ptrack_atomic_increase` only
  ever raises a slot's LSN (`engine.c:602-617`) `[verified-by-code]` — so a
  concurrent fuzzy checkpoint read can lag but never fabricate a
  lower-than-truth value that would drop a change.
- **Temp relations are never tracked.** `ptrack_mark_block` early-returns when
  `smgr_rnode.backend != InvalidBackendId` (`engine.c:632-636`); the file
  walker and `ptrack_mark_file` skip `looks_like_temp_rel_name`
  (`ptrack.c:309`, `engine.c:518`) `[verified-by-code]`.
- **`copydir` path is tracked block-by-block by hand.** Operations that copy
  files bypassing shared buffers (e.g. `CREATE DATABASE`) don't fire
  `mdwrite`, so `ptrack_copydir_hook` → `ptrack_walkdir` → `ptrack_mark_file`
  stats each file and marks all `st_size/BLCKSZ` blocks
  (`ptrack.c:202-244`, `engine.c:500-600`) `[verified-by-code]`. This is the
  buffer-bypass analogue of the smgr hook.
- **Map size is immutable at runtime.** `ptrack.map_size` is `PGC_POSTMASTER`
  and resizing loses all tracked changes (README Limitation #3,
  `README.md:161`; GUC context `ptrack.c:115`) `[verified-by-code]` — the
  hash-slot math (`PtrackContentNblocks`, `engine.h:76-78`) depends on a fixed
  size.
- **`--disable-atomics` safety.** `ptrackCheckpoint` zeroes its write buffer
  first because under spinlock-simulated atomics an uninitialized `sema` field
  could be written to disk and "cause spinlocks to stuck after restart"
  (`engine.c:307-314`) `[verified-by-code]` — a subtle consequence of persisting
  `pg_atomic_uint64` structs byte-for-byte.
- **Map file format is independently versioned.** `PTRACK_MAP_FILE_VERSION_NUM
  == 220` is checked on read and separate from `PTRACK_VERSION_NUM == 240`
  (`ptrack.h:29-34`, `engine.c:184-192`) `[verified-by-code]`; a 2.2 format
  change means older maps are discarded with a WARNING on upgrade
  (`README.md:138`) `[from-README]`.
- **A `paranoia` test mode patches core to disable hint bits.**
  `patches/turn-off-hint-bits.diff` makes `SetHintBits` an immediate `return`
  so per-block checksum comparison in `pg_probackup` tests isn't perturbed by
  hint-bit-only writes (`turn-off-hint-bits.diff`, `Makefile:39-42`)
  `[verified-by-code]` — a concrete acknowledgement that hint-bit writes are the
  one change class ptrack's contract excludes.

## Links into corpus

- `[[knowledge/ideologies/pg_bulkload.md]]` — the closest sibling: also
  re-implements durability *outside* WAL and *vendors a static core file*
  (`nbtsort-NN.c` there, `datapagemap.c` here). pg_bulkload writes data past
  WAL and undoes it on crash with an out-of-band log; ptrack observes writes and
  relies on WAL being enabled so recovery re-fires its hooks. Mirror images of
  the same "step outside the redo contract" move.
- `[[knowledge/ideologies/orioledb.md]]` — the other "requires a patched PG
  core" case. orioledb's patch adds a large hook surface for a whole storage
  engine; ptrack's patch adds five small hooks plus binary-utility edits. Both
  prove where the sanctioned extension seams run out for storage-adjacent work.
- `[[knowledge/ideologies/pg_squeeze.md]]`, `[[knowledge/ideologies/pg_repack.md]]`,
  `[[knowledge/ideologies/pg_tde.md]]` — neighbors that also operate at the
  physical file / smgr / checksum layer rather than the SQL layer.
- `[[knowledge/subsystems/storage-buffer.md]]` — the buffer manager + smgr
  write-out path (`mdwritev`/`mdextend`) whose flush events ptrack piggybacks on
  via the patched `mdwrite_hook`/`mdextend_hook`.
- `[[knowledge/subsystems/replication.md]]` — the backup/replication world
  ptrack feeds; contrast core PG-17 WAL-summarizer incremental backup, which
  answers the same "changed blocks" question by reading WAL instead of hooking
  writes.
- `[[knowledge/idioms/checkpoint-coordination.md]]` — ptrack persists its map on
  the checkpointer's `ProcessSyncRequests` fsync phase via a patched hook.
- `[[knowledge/idioms/crash-recovery-startup.md]]` — the recovery path that
  re-drives `mdwrite`/`mdextend` (and thus re-marks blocks) after a crash, which
  is why the map need not be WAL-logged as long as `wal_level >= replica`.
- `[[knowledge/idioms/hint-bits-setbufferdirty.md]]` — hint-bit writes are the
  documented exception to ptrack's no-false-negative guarantee.
- `.claude/skills/backup-and-recovery/SKILL.md`,
  `.claude/skills/extension-development/SKILL.md`,
  `.claude/skills/wal-and-xlog/SKILL.md`,
  `.claude/skills/bgworker-and-extensions/SKILL.md`.

## Anthropology takeaway

ptrack is the corpus's worked example of **"intercept every block write in a
lockless RAM structure, keep it durable only at checkpoint, and let the caller
copy just the marked blocks."** Its central bargain is the inverse of core's WAL
discipline: rather than deriving changed-block information *from* the durable log
after the fact (core's WAL summarizer), it captures the information *at write
time* through hooks a small core patch splices into `md.c`, `copydir.c`, and
`sync.c` — points core does not otherwise expose. The map itself is engineered
around one asymmetry: false positives are cheap (one wasted 8 KB copy) and false
negatives are fatal (a silently incomplete backup), so every design choice —
two hash slots that both must match, monotone-only CAS, fuzzy
read-without-locking at checkpoint, `init_lsn` as a "don't trust me before here"
watermark, and the hard `wal_level >= replica` requirement — biases toward
over-reporting change. For a planner or reviewer, ptrack is the case to weigh
against any "track changed blocks cheaply" proposal: the tracking really is
~1–3% TPS overhead (`README.md:167`) `[from-README]`, but the price is a
per-major-version core patch, an out-of-band durability scheme that is only
checkpoint-consistent, a hard dependency on WAL being enabled, and patched
backup binaries that must special-case the map files — the recurring
"pluggable-enough?" tax that also defines orioledb and pg_bulkload.

## Sources

Fetched 2026-07-09 from `https://raw.githubusercontent.com/postgrespro/ptrack/master/<path>`
(all via `curl`; the GitHub trees API / get_file_contents are 403 for this
external repo in-session, so all fetches are raw-URL):

- `README.md` @ 2026-07-09 → HTTP 200 (246 lines; overview, false-positive
  contract, architecture, limitations, upgrade notes, TODO — the `[from-README]`
  source for purpose + durability narrative).
- `ptrack.h` @ 2026-07-09 → HTTP 200 (88 lines; version macros, `PtBlockId`,
  `PtScanCtx`, `PtrackFileList_i`, PG-version compat `RelFileNode`↔`RelFileLocator`).
- `ptrack.c` @ 2026-07-09 → HTTP 200 (678 lines; deep-read — `_PG_init` hook
  installs, all six hook wrappers, `ptrack_gather_filelist`, the SRF reader
  `ptrack_get_pagemapset` with two-slot probe).
- `engine.c` @ 2026-07-09 → HTTP 200 (680 lines; deep-read — THE engine core:
  `ptrackCheckpoint` atomic-file-replace + CRC, `ptrackMapReadFromFile`,
  `ptrackMapInit`, `assign_ptrack_map_size` (wal_level guard),
  `ptrack_mark_block` / `ptrack_atomic_increase` CAS, `ptrack_set_init_lsn`,
  `ptrack_walkdir`/`ptrack_mark_file`).
- `engine.h` @ 2026-07-09 → HTTP 200 (115 lines; `PtrackMapHdr` struct, size/slot
  macros `PtrackContentNblocks`/`PtrackActualSize`/`BID_HASH_FUNC`, `PTRACK_PATH*`,
  `PTRACK_BUF_SIZE`). *(supplementary fetch, not in original manifest.)*
- `datapagemap.c` @ 2026-07-09 → HTTP 200 (126 lines; vendored pg_rewind bitmap).
- `ptrack.control` @ 2026-07-09 → HTTP 200 (5 lines; relocatable=true, v2.4).
- `ptrack--2.1.sql` @ 2026-07-09 → HTTP 200 (20 lines; the three C-function decls).
- `Makefile` @ 2026-07-09 → HTTP 200 (86 lines; `MODULE_big`, `make patch`,
  paranoia-mode hint-bits patch, TAP + python test wiring against pg_probackup).
- `patches/REL_17_STABLE-ptrack-core.diff` @ 2026-07-09 → HTTP 200 (391 lines;
  deep-read — the five hook declarations + call-sites in xlog.c/basebackup.c/
  copydir.c/md.c/sync.c/miscinit.c, and the binary-utility skip/copy edits in
  pg_checksums/pg_resetwal/pg_rewind). *(supplementary — the core-patch story.)*
- `patches/REL_18_STABLE-ptrack-core.diff` @ 2026-07-09 → HTTP 200 (probed,
  confirms per-major patch ladder through PG 18). *(existence probe only.)*
- `patches/turn-off-hint-bits.diff` @ 2026-07-09 → HTTP 200 (604 bytes;
  `SetHintBits` early-return for paranoia test mode). *(supplementary.)*

**Manifest gaps:** none of the manifest files 404'd (all 8 confirmed 200).
The `patches/` directory could not be *listed* (no trees API), but individual
candidate patches were confirmed present by direct raw fetch (REL_17, REL_18,
turn-off-hint-bits — all HTTP 200), so the "requires a per-major core patch"
claim is `[verified-by-code]` against the fetched REL_17 diff rather than
`[inferred]`. The ~1–3% TPS-overhead and backup-time-scaling benchmark numbers
are `[from-README]` (`README.md:167`) — no benchmark was reproduced. The claim
that crash recovery re-fires the smgr hooks to re-mark post-checkpoint blocks is
`[inferred]` from the hook placement in `md.c` + the `wal_level>=replica`
requirement; no crash-recovery run was performed.
