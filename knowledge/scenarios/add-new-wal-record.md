---
scenario: add-new-wal-record
when_to_use: I want to add a new WAL record type — either a brand-new RmgrId or a new info-byte opcode on an existing rmgr — plus the redo function, rmgrdesc / identify pair, and the `XLOG_PAGE_MAGIC` bump.
companion_skills: ["wal-and-xlog"]
related_scenarios: ["add-new-index-am","add-new-table-am"]
canonical_commit: 5c279a6d350
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new WAL record

## Scope — what's in / out

**In scope:** two flavors that share most of the file checklist.

- **Flavor (a) — new RmgrId.** Add `RM_<FOO>_ID` to `rmgrlist.h`,
  implement the `RmgrData` struct (`rm_redo` / `rm_desc` /
  `rm_identify` / optional `rm_startup` / `rm_cleanup` / `rm_mask` /
  `rm_decode`) in the owning `src/backend/access/<area>/` directory, and
  add the matching `<foo>desc.c` to `src/backend/access/rmgrdesc/`.
  `[verified-by-code]` (`src/include/access/rmgrlist.h:27-50`,
  `src/include/access/xlog_internal.h:336-361`).
- **Flavor (b) — new info-byte (opcode) on an existing rmgr.** Define
  `XLOG_<RMGR>_<OP>` constant in the rmgr's `*_xlog.h` header, extend
  the existing `<rmgr>_redo` switch, extend `<rmgr>_desc` /
  `<rmgr>_identify` in `src/backend/access/rmgrdesc/`. No new rmgr
  entry; `RM_MAX_BUILTIN_ID` does not change.
  `[verified-by-code]` (`src/include/access/heapam_xlog.h:32-67`,
  `src/backend/access/heap/heapam_xlog.c:1199-1241`,
  `src/backend/access/rmgrdesc/heapdesc.c:397-440`).
- The `XLOG_PAGE_MAGIC` bump in `src/include/access/xlog_internal.h` —
  unconditional whenever the on-disk WAL format changes (new record,
  new opcode, new field). `[verified-by-code]`
  (`src/include/access/xlog_internal.h:35`,
  `src/include/access/rmgrlist.h:24`).
- The emit site(s) — at least one `XLogBeginInsert` /
  `XLogRegisterData` / `XLogInsert(RM_<FOO>_ID, info)` call somewhere
  in the backend that actually produces the new record. An
  unreachable redo is dead weight. `[verified-by-code]`
  (`src/include/access/xloginsert.h:44-49`).

**Out of scope:**

- **Custom WAL rmgrs loaded from `shared_preload_libraries`** — they
  use `RegisterCustomRmgr(RM_<id>, ...)` from `_PG_init` and live in
  the `RM_MIN_CUSTOM_ID..RM_MAX_CUSTOM_ID` range, not `rmgrlist.h`.
  Treat as a sub-case of `add-new-extension` (the canonical_commit
  `5c279a6d350` covers the framework; the in-tree example is
  `src/test/modules/test_custom_rmgrs/`). `[verified-by-code]`
  (`src/include/access/rmgr.h:36-58`,
  `src/test/modules/test_custom_rmgrs/test_custom_rmgrs.c:67-73`).
- The cross-cutting "build the record from page state, register block
  refs, flush at right LSN" choreography — covered by the
  `wal-and-xlog` companion skill, not duplicated here.
- New logical-decoding output-plugin callbacks — separate scenario
  `add-new-replication-message`.
- The actual subsystem semantics (what the new operation _does_ to a
  page) — that belongs to the index-AM / table-AM / heap scenario
  this composes with.

## Pre-flight

- **Companion skill:** load `.claude/skills/wal-and-xlog/SKILL.md`. It
  covers `XLogBeginInsert` / `XLogRegisterBuffer` /
  `XLogRegisterData` / `XLogInsert` discipline, the FPI vs
  block-data split, and the cardinal rule that **redo must produce
  byte-identical pages to the original modification** under
  `wal_consistency_checking`. `[verified-by-code]`
  (`.claude/skills/wal-and-xlog/SKILL.md`,
  `src/backend/access/transam/xlogrecovery.c:2524-2527`).
- **Canonical commit:** `5c279a6d350` — *"Custom WAL Resource
  Managers"* (Jeff Davis, 2022). Reads as a complete reference
  example of an rmgr-shaped change: it adds the `RegisterCustomRmgr`
  hook, the `RM_MIN_CUSTOM_ID` partitioning, and (in
  `src/test/modules/test_custom_rmgrs/`) a textbook self-contained
  rmgr with redo / desc / identify. Read it before flavor (a). For
  flavor (b), the better near-historical reference is
  `4a8fb58671d` ("Bump XLOG_PAGE_MAGIC after xl_heap_prune change")
  paired with the preceding `add323da40a6` that did the format
  edit. `[verified-by-code]` (`git -C source show 5c279a6d350`,
  `git -C source show 4a8fb58671d`).
- **Common pitfalls (one-line each):**
  - Forgetting to bump `XLOG_PAGE_MAGIC`: replay against an older WAL
    stream silently succeeds, mismatched records corrupt the cluster.
    Class-of-bug demonstrated by `4a8fb58671d`. `[verified-by-code]`
    (`src/include/access/xlog_internal.h:35`).
  - Putting a new `PG_RMGR` line in the middle of `rmgrlist.h` —
    changes the numeric `RmgrId` of every entry after it, breaks WAL
    replay across the upgrade boundary. New entries go at the end.
    `[from-comment]` (`src/include/access/rmgrlist.h:19-24`).
  - Redo function that decodes record state but then bails when
    `XLogReadBufferForRedoExtended` returns `BLK_DONE` /
    `BLK_RESTORED` — must still consume the variable-length payload
    or `wal_consistency_checking` will diverge.
    `[verified-by-code]` (`src/backend/access/heap/heapam_xlog.c:91-93`).
  - Missing `ResolveRecoveryConflictWithSnapshot` for records that
    remove tuples still visible on a standby — the redo replays but
    Hot Standby queries get wrong answers. Pattern at
    `src/backend/access/heap/heapam_xlog.c:73-86`. `[verified-by-code]`
    (`src/backend/access/heap/heapam_xlog.c:73-86`).
  - Forgetting to extend `<rmgr>_identify` / `<rmgr>_desc` —
    `pg_waldump` prints "UNKNOWN (0xNN)" and the WAL is no longer
    debuggable. `[verified-by-code]`
    (`src/bin/pg_waldump/pg_waldump.c`,
    `src/backend/access/rmgrdesc/heapdesc.c:397-440`).

## File checklist (the FULL sweep)

Every row applies unless marked "flavor (a) only" or "flavor (b)
only". `pg-feature-plan` will refuse to drop these without an
explicit override.

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/include/access/xlog_internal.h` | Bump `XLOG_PAGE_MAGIC` (line 35) by one. Mandatory for **both** flavors any time the on-disk WAL format changes. The `RmgrData` struct (lines 336-361) lives here; if you add `rm_decode` / `rm_mask`, this is the contract you must match. `[verified-by-code]` (`src/include/access/xlog_internal.h:35,336-361`). | [xlog_internal.h.md](../files/src/include/access/xlog_internal.h.md) | wal-and-xlog |
| 2 | `src/include/access/rmgrlist.h` *(flavor (a) only)* | Add one new `PG_RMGR(RM_<FOO>_ID, "<Foo>", <foo>_redo, <foo>_desc, <foo>_identify, <foo>_startup_or_NULL, <foo>_cleanup_or_NULL, <foo>_mask_or_NULL, <foo>_decode_or_NULL)` line **at the end** of the list. The enum `RmgrIds` in `rmgr.h` is generated from this; appending preserves on-disk IDs. `[verified-by-code]` (`src/include/access/rmgrlist.h:19-24,27-50`, `src/include/access/rmgr.h:22-29`). | [rmgrlist.h.md](../files/src/include/access/rmgrlist.h.md) | wal-and-xlog |
| 3 | `src/include/access/<rmgr>_xlog.h` | The header that holds (a) the `XLOG_<RMGR>_<OP>` info-byte constants, (b) on-disk struct typedefs (`xl_<rmgr>_<op>`), and (c) prototypes for `<rmgr>_redo` / `<rmgr>_desc` / `<rmgr>_identify`. New file for flavor (a); edited in place for flavor (b). Mind `XLOG_<RMGR>_OPMASK` if you reuse the heap-style 3-bit-opcode + flag-bit layout. `[verified-by-code]` (`src/include/access/heapam_xlog.h:27-67`, `src/include/access/nbtxlog.h`). | [heapam_xlog.h.md](../files/src/include/access/heapam_xlog.h.md) (heap pattern) | wal-and-xlog |
| 4 | `src/backend/access/<area>/<rmgr>_xlog.c` *(flavor (a) usually; flavor (b) extends in place)* | Implements `<rmgr>_redo(XLogReaderState *record)` — the dispatch `switch (info & ~XLR_INFO_MASK)` over opcodes, each case calling a static `<rmgr>_xlog_<op>(record)` that does `XLogReadBufferForRedoExtended` → mutate page → `MarkBufferDirty` → `PageSetLSN` → `UnlockReleaseBuffer`. For flavor (b) you add one new `case` and one new `<rmgr>_xlog_<op>` helper. **Hot Standby:** if the op removes tuples or freezes XIDs, emit `ResolveRecoveryConflictWithSnapshot` BEFORE touching the buffer. `[verified-by-code]` (`src/backend/access/heap/heapam_xlog.c:73-105,1199-1241`). | [heapam_xlog.c.md](../files/src/backend/access/heap/heapam_xlog.c.md) (heap pattern) | wal-and-xlog |
| 5 | `src/backend/access/rmgrdesc/<rmgr>desc.c` | `<rmgr>_desc(StringInfo buf, XLogReaderState *record)` — append a human-readable, key:value, no-leading-`{` description of the record payload (see `src/backend/access/rmgrdesc/README` for the format conventions). `<rmgr>_identify(uint8 info)` — `switch` returning a short string for each opcode, used by `pg_waldump`. New file for flavor (a) (also list it in `meson.build` + `Makefile` — see row 6); extended in place for flavor (b). **Both** the `desc` and the `identify` switch must be kept exhaustive — a missing case yields silent UNKNOWN output. `[verified-by-code]` (`src/backend/access/rmgrdesc/README`, `src/backend/access/rmgrdesc/heapdesc.c:185-470`). | [heapdesc.c.md](../files/src/backend/access/rmgrdesc/heapdesc.c.md) (heap pattern) | wal-and-xlog |
| 6 | `src/backend/access/rmgrdesc/meson.build` + `src/backend/access/rmgrdesc/Makefile` *(flavor (a) only)* | Add the new `<rmgr>desc.c` to `rmgr_desc_sources` (meson) and `OBJS` (make). These objects are linked into both the backend and `pg_waldump`, so an omission gives a link-time undefined reference from `src/bin/pg_waldump`. `[verified-by-code]` (`src/backend/access/rmgrdesc/meson.build:3-27`, `src/backend/access/rmgrdesc/Makefile:11-33`). | — | wal-and-xlog |
| 7 | `src/backend/access/transam/rmgr.c` *(flavor (a), only if you use it)* | The `RmgrTable[]` is statically populated from `rmgrlist.h` (no edit needed). The only reason to touch this file is if your rmgr needs a custom error path; the default `RmgrNotFound` and `GetRmgr` (in `xlog_internal.h:374-385`) cover the lookup. Listed for completeness so the planner doesn't propose spurious edits. `[verified-by-code]` (`src/backend/access/transam/rmgr.c:50-145`, `src/include/access/xlog_internal.h:374-385`). | [rmgr.c.md](../files/src/backend/access/transam/rmgr.c.md) | wal-and-xlog |
| 8 | `src/backend/access/<area>/<owner>.c` (the emit site) | At least one path that builds the record: `XLogBeginInsert()` → optional `XLogRegisterBuffer(N, buf, flags)` → `XLogRegisterData(&xlrec, sizeof(xlrec))` (+ any variable-length tail) → `recptr = XLogInsert(RM_<FOO>_ID, XLOG_<RMGR>_<OP> [| XLOG_<RMGR>_INIT_PAGE])` → `PageSetLSN(page, recptr)`. The emit site MUST mirror the redo function field-for-field, in the same order; a divergence here is undetectable until `wal_consistency_checking=all` runs in CI. `[verified-by-code]` (`src/include/access/xloginsert.h:44-49`). | — | wal-and-xlog |
| 9 | `src/backend/access/transam/xlogrecovery.c` | Read-only dependency. Not edited directly. `xlogrecovery.c:1966` calls `GetRmgr(record->xl_rmid).rm_redo(xlogreader)` — your `rm_redo` is dispatched from here. Listed so the planner understands the call graph; lines 2524-2527 are where `rm_mask` is invoked under `wal_consistency_checking`. `[verified-by-code]` (`src/backend/access/transam/xlogrecovery.c:1966,2524-2527`). | [xlogrecovery.c.md](../files/src/backend/access/transam/xlogrecovery.c.md) | wal-and-xlog |
| 10 | `src/backend/access/transam/xlog.c` | Read-only dependency. `xlog.c:5107-5118` is the `wal_consistency_checking` GUC parser; it walks `RmgrTable[]` looking up rmgr names. If you forget `rm_name` in your `RmgrData`, that lookup silently skips you. Listed so the planner doesn't propose edits here. `[verified-by-code]` (`src/backend/access/transam/xlog.c:5107-5118`). | [xlog.c.md](../files/src/backend/access/transam/xlog.c.md) | wal-and-xlog |
| 11 | `src/test/recovery/t/<NNN>_<feature>.pl` | TAP test that uses `PostgreSQL::Test::Cluster` to start a primary + standby, exercise the emit path, and assert the standby replays cleanly (and, ideally, with `wal_consistency_checking=all` set in `postgresql.conf`). Without a recovery TAP, the only thing exercising your redo is the regress suite under a no-replay setup — which doesn't actually run the new redo. `[verified-by-code]` (`src/test/recovery/t/001_stream_rep.pl`, et al.). | — | wal-and-xlog |
| 12 | `src/test/regress/sql/<existing>.sql` + matching `expected/*.out` | Regression coverage for the user-facing behavior the new record encodes (an `INSERT` / `VACUUM` / index op / etc.). Doesn't exercise redo, but is the easy smoke for the emit path. `[inferred]` from upstream conventions. | — | wal-and-xlog |
| 13 | `src/bin/pg_waldump/` | Read-only dependency. `pg_waldump` links the `rmgr_desc_sources` from row 6 plus the `RmgrTable[]` from row 7. As long as rows 5-6 are correct, `pg_waldump --rmgr=<Foo>` prints your record. Listed so the planner understands the consumer; nothing here needs hand-editing. `[verified-by-code]` (`src/bin/pg_waldump/pg_waldump.c`, `src/bin/pg_waldump/rmgrdesc.c`). | — | wal-and-xlog |

(Rows 7, 9, 10, 13 are read-only dependencies — listed so the
planner doesn't waste a phase searching for "what else must change"
when the answer is "nothing, but here's where your code is consumed".)

## Phases — suggested split for `pg-feature-plan`

1. **Phase 1 — Define the on-disk format and the rmgr surface.**
   Files: [1, 2 (if flavor (a)), 3, 6 (if flavor (a))]. Edits:
   pick the opcode constants, lay out `xl_<rmgr>_<op>` struct, append
   the `PG_RMGR` entry, and bump `XLOG_PAGE_MAGIC`. Phase-end check:
   `meson compile -C dev/build-debug` is clean. `pg_waldump --help`
   lists the new rmgr in `--rmgr=` (flavor (a) only) once row 6 is in.
2. **Phase 2 — Implement redo + desc + identify.** Files: [4, 5].
   Edits: `<rmgr>_redo` switch (with `ResolveRecoveryConflictWithSnapshot`
   if the op drops user-visible tuples), `<rmgr>_desc` payload
   pretty-printer, `<rmgr>_identify` opcode-to-string. Phase-end
   check: `meson compile` clean; a hand-crafted unit test that
   `XLogInsert`s the new record, then `pg_waldump`s it, shows the
   identify string and a sensible desc line.
3. **Phase 3 — Wire emit sites.** Files: [8, 12]. Edits: replace the
   ad-hoc / generic WAL emit (or add the brand-new one) at the
   detection site. Phase-end check: regress passes; running with
   `wal_level=replica` + a streaming standby + `wal_consistency_checking='<rmgr>'`
   shows zero "page consistency check failed" messages in the
   standby log.
4. **Phase 4 — Recovery TAP + crash-recovery smoke.** Files: [11].
   Edits: add `src/test/recovery/t/<NNN>_<feature>.pl` that
   primary→standby streams the new record and asserts replica state.
   Phase-end check: `meson test -C dev/build-debug --suite recovery`
   green; for the paranoia pass, run with `wal_consistency_checking=all`
   set in the cluster's `postgresql.conf`.


## Likely reviewers
<!-- persona-reviewers:auto -->

*Personas whose Domain-ownership paths overlap this scenario's §Files. Reflect who might catch this on hackers-list.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

| Persona | Overlapping path(s) |
|---|---|
| [`heikki-linnakangas`](../personas/heikki-linnakangas.md) | `src/include`, `src/backend/access` |
| [`michael-paquier`](../personas/michael-paquier.md) | `src/test/modules`, `src/backend/access` |
| [`nathan-bossart`](../personas/nathan-bossart.md) | `src/include`, `src/bin` |
| [`peter-eisentraut`](../personas/peter-eisentraut.md) | `src/include`, `src/bin` |

<!-- /persona-reviewers:auto -->

## Idioms invoked
<!-- idioms-invoked:auto -->

*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

| Idiom | Evidence |
|---|---|
| [`checkpoint-coordination`](../idioms/checkpoint-coordination.md) | shares files: `src/backend/access/transam/xlog.c` |
| [`crash-recovery-startup`](../idioms/crash-recovery-startup.md) | direct reference |
| [`vacuum-hot-prune`](../idioms/vacuum-hot-prune.md) | shares files: `src/include/access/heapam_xlog.h` |
| [`wal-buffer-state`](../idioms/wal-buffer-state.md) | shares files: `src/backend/access/transam/xlog.c` |
| [`wal-page-format`](../idioms/wal-page-format.md) | direct reference |
| [`wal-page-write-flush`](../idioms/wal-page-write-flush.md) | shares files: `src/backend/access/transam/xlog.c` |
| [`wal-record-construction`](../idioms/wal-record-construction.md) | direct reference |
| [`xlog-region-replay`](../idioms/xlog-region-replay.md) | direct reference |
| [`xloginsertlock-partitioning`](../idioms/xloginsertlock-partitioning.md) | direct reference |

<!-- /idioms-invoked:auto -->
## Pitfalls

- **`XLOG_PAGE_MAGIC` is not bumped automatically.** Reviewers
  explicitly look for the bump; missing it is the single most common
  WAL patch revision request. The macro is a 16-bit page header field
  that mismatched-version `redo` does NOT detect — replay just
  silently does the wrong thing. `[verified-by-code]`
  (`src/include/access/xlog_internal.h:35`,
  commit message of `4a8fb58671d`).
- **Inserting `PG_RMGR` mid-list shifts every following ID.** WAL
  written by the old binary becomes uninterpretable by the new
  binary (and vice versa). The header comment at
  `src/include/access/rmgrlist.h:19-24` `[from-comment]` says
  it explicitly: **new entries at the end**.
- **The redo path must reproduce bytes, not just semantics.** Under
  `wal_consistency_checking`, the recovery code masks both pages
  with `rm_mask` and compares. If `rm_mask` is missing or your redo
  sets a hint bit the original didn't, the comparison fails. The
  mask hook is the escape valve for legitimately-unstable bits (LSN,
  hint bits) — use it sparingly. `[verified-by-code]`
  (`src/backend/access/transam/xlogrecovery.c:2524-2527`).
- **Hot-Standby conflict generation is the easiest thing to forget.**
  Heap's pattern: any record that prunes / freezes / deletes
  user-visible tuples emits the snapshot_conflict_horizon in the
  payload and calls `ResolveRecoveryConflictWithSnapshot(horizon,
  is_catalog, rlocator)` from inside `rm_redo` **before** touching
  the buffer. Forget this and standby queries return wrong rows
  during replay. `[verified-by-code]`
  (`src/backend/access/heap/heapam_xlog.c:73-86`).
- **rmgrdesc output format conventions matter.** The README
  (`src/backend/access/rmgrdesc/README`) lays out the
  `key: value, key: value` style with `array_desc` helpers in
  `rmgrdesc_utils.c` — straying produces hard-to-parse `pg_waldump`
  output. `c03c2eae0ac` ("Refine the guidelines for rmgrdesc
  authors") is the reference. `[verified-by-code]`
  (`src/backend/access/rmgrdesc/README`).
- **The `decode` callback is optional but consequential.** Set
  `rm_decode = NULL` if your rmgr never emits records that logical
  decoding should see; set it to a real function if any of your
  records should appear in a logical replication stream. The
  framework was added in `7a5f6b47488` ("Make logical decoding a
  part of the rmgr"). `[verified-by-code]`
  (`src/include/access/xlog_internal.h:360-361`,
  `git show 7a5f6b47488`).
- **Synchronization traps (must change together):**
  - `rmgrlist.h` ↔ `<rmgr>desc.c` ↔ `rmgrdesc/meson.build` +
    `rmgrdesc/Makefile` ↔ `pg_waldump` link. Adding a `PG_RMGR` line
    without also dropping the desc source into the build will yield
    a clean compile but a broken `pg_waldump` link.
  - Redo function ↔ emit site struct layout. The `xl_<rmgr>_<op>`
    struct is shared on-disk format; if one side mis-reads a field
    the bug is silent until `wal_consistency_checking` catches it
    (or, worse, until a real crash).

## Verification (exact test invocations)

```bash
# Build with assertions and consistency-checking ready.
meson configure dev/build-debug -Dcassert=true
meson compile -C dev/build-debug

# Regress (smoke for the emit path).
meson test -C dev/build-debug --suite regress

# Recovery TAP (the real test for the redo path).
meson test -C dev/build-debug --suite recovery

# Optional: paranoia pass with full consistency checking. Set
# wal_consistency_checking='all' in the cluster's postgresql.conf,
# or per-rmgr like wal_consistency_checking='<Foo>,Heap'.
PG_TEST_EXTRA="wal_consistency_checking" \
  meson test -C dev/build-debug --suite recovery

# Custom-rmgr smoke (only if you went the RegisterCustomRmgr route).
meson test -C dev/build-debug --suite test_custom_rmgrs
```

If you added a brand-new recovery TAP, name it explicitly (e.g.
`src/test/recovery/t/0NN_<feature>_redo.pl`) and ensure it is picked
up by the meson `recovery` suite glob.

## Cross-refs

- Companion skill: `.claude/skills/wal-and-xlog/SKILL.md` — the
  procedural rule set for `XLogBeginInsert` / `XLogRegisterBuffer`
  / `XLogRegisterData` / `XLogInsert`, FPI choices, and the
  byte-identical-redo discipline.
- Related scenarios: `scenarios/add-new-index-am.md` (a new index AM
  always brings a new rmgr or new opcodes — composite),
  `scenarios/add-new-table-am.md` (same, for table AMs).
- Idioms: `knowledge/idioms/wal-record-construction.md`,
  `knowledge/idioms/xlog-region-replay.md`,
  `knowledge/idioms/xloginsertlock-partitioning.md`,
  `knowledge/idioms/wal-page-format.md`,
  `knowledge/idioms/crash-recovery-startup.md`.
- Subsystems: `knowledge/subsystems/access-transam.md` (the redo /
  recovery loop), `knowledge/subsystems/access-rmgrdesc.md` (the
  desc + identify layer), `knowledge/subsystems/access-heap.md` (the
  canonical example of a multi-opcode rmgr).
- Issues: `knowledge/issues/replication.md`,
  `knowledge/issues/pg_waldump.md`,
  `knowledge/issues/pg_walinspect.md` — known traps in the
  downstream consumers your desc / identify code feeds.
- Reference patches:
  `git -C source show 5c279a6d350` — Custom WAL Resource Managers
  (the framework + textbook test_custom_rmgrs example);
  `git -C source show 4a8fb58671d` — clean one-line
  `XLOG_PAGE_MAGIC` bump, the minimal example of "I changed a record
  layout";
  `git -C source show 7a5f6b47488` — adding the `rm_decode`
  callback, the historical anchor for the logical-decoding-on-rmgr
  shape.
