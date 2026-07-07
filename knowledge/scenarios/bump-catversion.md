---
scenario: bump-catversion
when_to_use: You touched a catalog header/.dat, parsetree node struct, tuple-header layout, or anything else that invalidates an existing data directory — bump `CATALOG_VERSION_NO` so `initdb` is forced.
companion_skills: [catalog-conventions]
related_scenarios: [add-new-builtin-function, add-new-data-type, add-new-system-catalog-column]
canonical_commit: df6949ccf7a
last_verified_commit: e18b0cb7344
---

# Scenario — Bump CATALOG_VERSION_NO

## Scope — what's in / out

**In scope:**
- The one-line edit to `src/include/catalog/catversion.h`.
- The decision rule: "did my change require initdb?" — the full
  list of triggers (catalog `.h`/`.dat` edits, parsetree node-struct
  edits, tuple-header layout, stored-rule serialization).
- The verification that the bump took: `initdb` succeeds, old data
  directory refuses to start with the expected `errdetail`.

**Out of scope:**
- The actual catalog change that *necessitated* the bump (covered by
  whichever sibling scenario shipped the change — `add-new-builtin-function`,
  `add-new-data-type`, `add-new-system-catalog-column`, etc.). This
  scenario is the "you forgot to bump" companion; it never travels alone
  in a real feature plan.
- `PG_CONTROL_VERSION` bumps (different number, different file, governs
  the `pg_control` *file format* not the catalog contents) — handled
  ad-hoc when `ControlFileData` layout changes.
- `XLOG_PAGE_MAGIC` bumps (a WAL-format invariant, see
  `add-new-wal-record`).

## Pre-flight

- **Companion skill:** load `.claude/skills/catalog-conventions/SKILL.md`
  (covers genbki, BKI rules, OID conventions, and the catversion bump
  rule in §3).
- **Canonical commit:** `df6949ccf7a` — *"Add tid_block() and tid_offset()
  accessor functions"*. Small, clean example: two new `pg_proc.dat` rows
  + two C functions + catversion bump. Commit message says verbatim
  "Bumps catversion." [verified-by-code](source/src/include/catalog/catversion.h:60)
- **Common pitfalls (one-line each):**
  - Forgot to bump → your locally re-initdb'd cluster works, everyone
    else's cluster refuses to start with a confusing "incompatible"
    error (see Pitfalls below).
  - Picked yesterday's date by mistake (committer-local clock skew) —
    harmless because the value is just an integer compared for equality,
    but breaks the `YYYYMMDDN` convention.
  - Two patches in flight on the same day both want sequence `1` —
    second-to-commit must rebase to `2`, conflict is mechanical.
  - Bumping `PG_CONTROL_VERSION` thinking that's the catalog one —
    different macro, different purpose. [verified-by-code](source/src/include/catalog/pg_control.h:133-134)

## File checklist (the FULL sweep)

This scenario is unusual: it touches **exactly one file**. The
load-bearing question is *when*, not *how*. The table below is the file
list this bump interacts with — only the first row is edited; the rest
are read-only consumers you should know exist so you understand the
invariant.

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/include/catalog/catversion.h` | **EDIT.** Increment the `CATALOG_VERSION_NO` macro to `YYYYMMDDN` where `YYYYMMDD` is today (UTC convention informally) and `N` is the sequence-on-that-day (start at `1`, bump to `2` if rebasing onto a same-day commit). Single-line change. [verified-by-code](source/src/include/catalog/catversion.h:59-60) | [catversion.h.md](../files/src/include/catalog/catversion.h.md) | catalog-conventions |
| 2 | `src/include/catalog/pg_control.h` | (read-only) Defines `ControlFileData.catalog_version_no` — the on-disk slot the bumped value gets written into by `initdb` and re-checked by every backend startup. [verified-by-code](source/src/include/catalog/pg_control.h:127,134) | [pg_control.h.md](../files/src/include/catalog/pg_control.h.md) | catalog-conventions |
| 3 | `src/backend/access/transam/xlog.c` | (read-only) `WriteControlFile()` stamps `CATALOG_VERSION_NO` into the fresh control file at bootstrap. `ReadControlFile()` re-checks at every backend start; mismatch → `FATAL` with errhint *"It looks like you need to initdb."* [verified-by-code](source/src/backend/access/transam/xlog.c:4305,4486-4495) | — | catalog-conventions |
| 4 | `src/include/common/relpath.h` | (read-only) `TABLESPACE_VERSION_DIRECTORY` macro embeds the catversion into the per-tablespace subdir name (`PG_<major>_<catversion>`). Bumping shifts where new relations land in non-default tablespaces. [verified-by-code](source/src/include/common/relpath.h:33-34) | [relpath.h.md](../files/src/include/common/relpath.h.md) | — |
| 5 | `src/bin/pg_resetwal/pg_resetwal.c` | (read-only) When forcibly rewriting a corrupt control file, stamps in the compiled-in `CATALOG_VERSION_NO`. Means `pg_resetwal` from a newer binary will silently "upgrade" the catversion field of an old `pg_control` — so it's not a recovery path for a missed bump. [verified-by-code](source/src/bin/pg_resetwal/pg_resetwal.c:682) | — | — |
| 6 | `src/bin/pg_rewind/pg_rewind.c` | (read-only) Refuses to rewind between a source/target with mismatched `catalog_version_no` vs the compiled-in value (cross-cluster safety check). [verified-by-code](source/src/bin/pg_rewind/pg_rewind.c:755-756) | — | — |
| 7 | `src/bin/initdb/initdb.c` | (no direct reference) initdb itself does not name `CATALOG_VERSION_NO`; it runs the backend in bootstrap mode, which calls `BootStrapXLOG()` → `WriteControlFile()` to stamp the value. Mentioned for completeness because the per-file doc on `catversion.h` cites initdb as the producer. [verified-by-code](source/src/include/catalog/catversion.h:11) [inferred] | — | — |

That's it. There is no `.dat` change, no test fixture, no docs file. The
gravity of this scenario is the *trigger rule*, not the file count.

## Phases — suggested split for `pg-feature-plan`

When this scenario is unioned with a sibling (the normal case), it
becomes the *final* phase of the sibling's plan. Standalone, it's three
short phases.

1. **Phase 1 — Decide whether a bump is required.** Files: [—].
   Apply the trigger checklist from `catversion.h:26-38` and
   `idioms/catalog-conventions.md` §3:
   - Any edit under `src/include/catalog/*.h` or `*.dat` that changes a
     row's shape, content, or seeded rows? → bump.
     [from-comment](source/src/include/catalog/catversion.h:31-33)
   - Any edit to `primnodes.h` or `parsenodes.h` (parsetree node
     layout)? → almost always bump, because parsetrees appear in stored
     rules and new-style SQL function bodies.
     [from-comment](source/src/include/catalog/catversion.h:35-38)
   - Any change to tuple-header layout (`HeapTupleHeaderData`,
     `IndexTupleData`)? → bump.
     [from-comment](source/src/include/catalog/catversion.h:33-34)
   - `genbki.pl` codegen change that alters `postgres.bki`? → bump.
   - Pure backend-internal C refactor with no on-disk effect? → no bump.
   Phase-end check: a one-line written justification ("change requires
   initdb because <reason>") attached to the commit message.

2. **Phase 2 — Edit `catversion.h`.** Files: [1]. Increment the
   `YYYYMMDDN` macro. Use today's date in the form `YYYYMMDD`, sequence
   `1` unless another patch already landed today (then `2`, `3`, …).
   Phase-end check: `git diff src/include/catalog/catversion.h` shows
   exactly one changed line, the new value parses as a fresh `YYYYMMDDN`,
   and is *strictly greater* than the prior value.

3. **Phase 3 — Verify the invalidation cycle.** Files: [—].
   Build, run `initdb` against a fresh data dir, then start the server.
   Old data dir from before the bump must refuse to start with
   `FATAL: database files are incompatible with server`. There is no
   regression test for this — the verification *is* the failing-old /
   succeeding-new initdb pair. Phase-end check: see Verification below.

## Idioms invoked
<!-- idioms-invoked:auto -->

*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

| Idiom | Evidence |
|---|---|
| [`catalog-conventions`](../idioms/catalog-conventions.md) | direct reference |
| [`checkpoint-coordination`](../idioms/checkpoint-coordination.md) | shares files: `src/backend/access/transam/xlog.c` |
| [`crash-recovery-startup`](../idioms/crash-recovery-startup.md) | shares files: `src/backend/access/transam/xlog.c` |
| [`wal-buffer-state`](../idioms/wal-buffer-state.md) | shares files: `src/backend/access/transam/xlog.c` |
| [`wal-page-write-flush`](../idioms/wal-page-write-flush.md) | shares files: `src/backend/access/transam/xlog.c` |
| [`xloginsertlock-partitioning`](../idioms/xloginsertlock-partitioning.md) | shares files: `src/backend/access/transam/xlog.c` |

<!-- /idioms-invoked:auto -->
## Pitfalls

- **Silent self-test** — your local dev loop typically runs `initdb`
  on every rebuild (via `/pg-restart` or `make check` semantics), so
  *your* cluster keeps working whether or not you bumped. The bug only
  surfaces on a teammate's machine or a buildfarm animal that re-uses
  its data directory. Mitigation: assume the bump is required unless
  you can articulate why it isn't. [from-comment](source/src/include/catalog/catversion.h:18-29)
- **Non-monotonic edits** — manually picking a smaller number (e.g.
  copy-pasting an older value) compiles and runs, but breaks the
  informal `YYYYMMDDN` ordering and surfaces as a baffling "newer
  binary, older catversion" git-blame later. Use today's date.
  [from-comment](source/src/include/catalog/catversion.h:51-57)
- **Bumping when you shouldn't** — a pure-C refactor with no on-disk
  effect that bumps catversion forces every developer's cluster to be
  re-initdb'd for no reason. Annoying but not wrong; reviewers will
  push back during patch review.
- **`primnodes.h` / `parsenodes.h` blind spot** — these files don't
  look like "catalog changes" but they almost always need a bump,
  because stored rules and new-style SQL function bodies serialize
  parsetrees via `pg_node_tree`. Treat any node-struct field add/remove
  as a catversion trigger. [from-comment](source/src/include/catalog/catversion.h:35-38)
- **`pg_resetwal` is not a fix** — running `pg_resetwal` on a
  catversion-mismatched cluster will silently overwrite the field with
  the newer binary's value (`src/bin/pg_resetwal/pg_resetwal.c:682`),
  not detect the mismatch. The catalog *contents* on disk remain stale,
  so the cluster will then crash at runtime on the first reference to
  the missing/changed catalog row. Tell users to `initdb`, not
  `pg_resetwal`. [verified-by-code](source/src/bin/pg_resetwal/pg_resetwal.c:682)
- **Tablespace-dir shift** — bumping catversion changes the path of
  the per-tablespace subdirectory because `TABLESPACE_VERSION_DIRECTORY`
  interpolates it. A fresh `initdb` will allocate the new path; old
  tablespace contents remain under the old `PG_<major>_<oldcatversion>`
  dir and look orphaned. Not normally a problem during dev, but worth
  knowing when debugging tablespace lookups across catversion changes.
  [verified-by-code](source/src/include/common/relpath.h:33-34)
- **Synchronization trap (the only one):** if you edit any of the
  trigger files in §Phase 1, you MUST also edit `catversion.h`. There
  is no lint that catches a missed bump — it's a discipline rule
  enforced by reviewers and the buildfarm. [from-comment](source/src/include/catalog/catversion.h:26-29)

## Verification (exact test invocations)

There is **no regression test** for this bump; the verification is
operational.

```bash
# 1. Rebuild after the bump.
meson compile -C dev/build-debug

# 2. Fresh initdb succeeds and stamps the new value into pg_control.
rm -rf dev/data-debug
dev/install-debug/bin/initdb -D dev/data-debug
dev/install-debug/bin/pg_controldata dev/data-debug | grep -i 'catalog version'
# Expected: prints the new YYYYMMDDN value.

# 3. Start the server against the fresh dir — must succeed.
dev/install-debug/bin/pg_ctl -D dev/data-debug -l /tmp/pg.log start
dev/install-debug/bin/pg_ctl -D dev/data-debug stop

# 4. Negative test: any preserved data directory from BEFORE the bump
#    must now refuse to start with the catversion-mismatch FATAL.
#    (Skip if you don't keep an old data dir around.)
dev/install-debug/bin/pg_ctl -D /path/to/preserved/old/data start 2>&1 | \
    grep -E 'database files are incompatible|CATALOG_VERSION_NO'
# Expected: FATAL: database files are incompatible with server
#           DETAIL: The database cluster was initialized with CATALOG_VERSION_NO N,
#                   but the server was compiled with CATALOG_VERSION_NO M.
#           HINT:  It looks like you need to initdb.
```

The error message and hint are produced by `ReadControlFile()` in
`xlog.c:4486-4495` [verified-by-code](source/src/backend/access/transam/xlog.c:4486-4495).

Regression suite invocation, for completeness (these run after every
catalog change anyway, and will catch any *content* breakage the bump
implies — but they do not test the bump itself):

```bash
meson test -C dev/build-debug --suite regress
meson test -C dev/build-debug --suite isolation
```

## Cross-refs

- Companion skill: [.claude/skills/catalog-conventions/SKILL.md](../../.claude/skills/catalog-conventions/SKILL.md)
- Related scenarios:
  [scenarios/add-new-builtin-function.md](add-new-builtin-function.md),
  [scenarios/add-new-data-type.md](add-new-data-type.md),
  [scenarios/add-new-system-catalog-column.md](add-new-system-catalog-column.md).
  (Each one ends its file checklist with row "bump catversion" pointing
  here. Every other catalog-touching scenario does the same.)
- Idioms: [knowledge/idioms/catalog-conventions.md §3](../idioms/catalog-conventions.md)
  — the "Bump rule" section is the authoritative trigger list.
- Subsystem: [knowledge/subsystems/access-transam.md](../subsystems/access-transam.md)
  — `xlog.c` control-file machinery (where the check fires).
- Per-file docs:
  [catversion.h.md](../files/src/include/catalog/catversion.h.md),
  [pg_control.h.md](../files/src/include/catalog/pg_control.h.md),
  [relpath.h.md](../files/src/include/common/relpath.h.md).
- Reference patch (canonical_commit):
  `git -C source show df6949ccf7a` — minimal example of a feature that
  bumps catversion alongside two new `pg_proc.dat` entries.
- Pre-release housekeeping example: `c7cb8e5b73c` ("Do pre-release
  housekeeping on catalog data") — bundles `renumber_oids.pl` with a
  catversion bump; not a typical bump but useful to read for the
  end-of-cycle pattern.
