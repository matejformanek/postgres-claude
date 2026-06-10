---
source_url: https://www.postgresql.org/docs/current/custom-rmgr.html
fetched_at: 2026-06-10T20:50:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Custom WAL Resource Managers (internals ch. 64.2)

The full-power alternative to Generic WAL: an extension supplies its own `RmgrData`
with a real redo routine, optionally decode support. Heavier than generic WAL but
the only path if you need logical decoding of your records. Companion to the
`wal-and-xlog` skill, `gucs-bgworker-parallel` (preload), and
`docs-distilled/generic-wal.md`.

## Non-obvious claims

- **`RmgrData` callback set:** `rm_name`, `rm_redo`, `rm_desc`, `rm_identify`,
  `rm_startup`, `rm_cleanup`, `rm_mask`, `rm_decode`. [from-docs]
  - `rm_redo` — replay during recovery/streaming.
  - `rm_desc` / `rm_identify` — pg_waldump text; `rm_identify` (returns a name for
    a given `xl_info`) is effectively required for tooling.
  - `rm_mask` — zero out bits that `wal_consistency_checking` must not compare
    (hint bits etc.).
  - `rm_decode` — *opt-in* logical-decoding hook; this is what generic WAL lacks.
  - `rm_startup` / `rm_cleanup` — bracketing init/teardown.
- **Register from `_PG_init` only**, via
  `RegisterCustomRmgr(RmgrId rmid, const RmgrData *rmgr)`, and the module **must**
  be in `shared_preload_libraries`. Registering later (e.g. on `CREATE EXTENSION`)
  is too late for recovery. [from-docs]
- **ID allocation is a two-phase social contract:** use `RM_EXPERIMENTAL_ID`
  during development; for a release, **reserve a unique `RmgrId`** on the wiki page
  *CustomWALResourceManagers*. IDs must be **globally unique across all
  extensions** — there is no runtime arbitration, collisions silently corrupt
  replay. [from-docs]
- **🔑 Permanent dependency / un-removability.** "The extension must remain in
  `shared_preload_libraries` as long as any custom WAL records may exist in the
  system." Drop it while such records are still in the WAL stream (or unreplayed on
  a standby) and **the server may fail to start**. This makes a custom rmgr a
  one-way door operationally. [from-docs]
- Contrast with generic WAL: generic WAL needs no ID, no redo routine, no preload
  — but is invisible to logical decoding and can't be replayed by custom logic.
  Choose custom rmgr precisely when you need `rm_decode` or a compact
  application-specific redo. [inferred from both pages]

## Links into corpus

- Sibling: `knowledge/docs-distilled/generic-wal.md` (the lighter option, with the
  "ignored during logical decoding" caveat that motivates this chapter).
- Decoding context: `knowledge/docs-distilled/protocol-logical-replication.md` and
  the A8 output-plugin thread — `rm_decode` is where a custom AM would surface
  changes to an output plugin.
- Preload mechanics: `gucs-bgworker-parallel` skill (`shared_preload_libraries`,
  `_PG_init`).
- Code: `source/src/include/access/xlog_internal.h` (`RmgrData`,
  `RM_CUSTOM_MIN_ID`/`RM_CUSTOM_MAX_ID`, `RM_EXPERIMENTAL_ID`),
  `source/src/backend/access/transam/rmgr.c` (`RegisterCustomRmgr`).
  [unverified — not line-pinned this run]
