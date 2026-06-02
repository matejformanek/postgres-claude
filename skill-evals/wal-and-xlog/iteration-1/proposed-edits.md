# Proposed Edits — Iteration 1

Not applied. Recorded here for triage on the next pass.

## P1 — Resolve `MAX_GENERIC_XLOG_PAGES` `[unverified]`

The Generic WAL section says "Up to `MAX_GENERIC_XLOG_PAGES` pages per call (a small constant in `generic_xlog.h`). [unverified value — check at use site]" and the open-questions block repeats it. This is trivially checkable — `grep -RIn MAX_GENERIC_XLOG_PAGES source/src/include/access/generic_xlog.h` — and the constant should be inlined. Likely value: 4. Removes one `[unverified]` and gives the reader a concrete budget without a detour.

## P2 — Make the LSN-for-redo argument explicit

In `## 5. Write the redo function`, the example uses `PageSetLSN(page, record->EndRecPtr)` but the surrounding prose doesn't call out *why* it must be `EndRecPtr` rather than the start. Add a one-liner: "Use `record->EndRecPtr` (end of the record being replayed) so the page LSN advances past the record once it's fully applied — the start LSN would falsely re-admit BLK_NEEDS_REDO on a re-scan that starts exactly at this record." This was a baseline-vs-skill gap on E3.

## P3 — Surface the `XLogReadBufferForRedo` return-value triad

The redo example only branches on `BLK_NEEDS_REDO`. Add a short table covering the three return values someone will hit in practice:

| return | meaning | what to do |
|---|---|---|
| `BLK_NEEDS_REDO` | page LSN < record LSN; apply the change | apply, PageSetLSN, MarkBufferDirty |
| `BLK_DONE` | page LSN ≥ record LSN; already applied | skip body, but still unlock if valid |
| `BLK_RESTORED` | FPI was just applied | skip body, page already at correct LSN |
| `BLK_NOTFOUND` | block doesn't exist (e.g. truncated) | nothing to do |

This is the single most common point of confusion in writing redo functions.

## P4 — Add a "writer ↔ redo symmetry" check item

Add to the pre-commit checklist: `[ ] For every field the writer reads from the in-memory state, the corresponding bytes are written into the record via XLogRegisterData / XLogRegisterBufData and read back via XLogRecGetData / XLogRecGetBlockData in redo.` This is the bug class that survives `wal_consistency_checking = 'all'` because the writer never produces a diverging on-disk page — only crash recovery exposes it.

## P5 — Note that `rm_decode` mandatoryness is resolved by recent code

The open-questions block asks "Whether `rm_decode` is mandatory for `wal_level=logical`". Worth a 5-minute check in `xlog_internal.h` / `rmgr.c` to retire this `[unverified]`. From memory: optional, only required if you want records visible to logical decoding plugins — but verify.

## P6 — Cross-link from the description to companion skills

The `description:` frontmatter could mention that for the locking around shared state the buffer touches, the `locking` skill is the companion, and `error-handling` for the `ereport(PANIC, …)` inside redo. Currently the skill is self-contained but a real WAL patch frequently triggers the other two.

## P7 — Tiny: example block `_PG_init` is incomplete

The `_PG_init` snippet has `ereport(ERROR, ...)` with literal `...`. Replace with a real ereport using `errmsg("must be loaded via shared_preload_libraries")` so a junior dev can copy-paste without guessing.
