---
source_url: https://www.postgresql.org/docs/current/generic-wal.html
fetched_at: 2026-06-10T20:50:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Generic WAL Records (internals ch. 64.1)

The lowest-effort way for an extension/index AM to get crash-safe, replayable
page changes without writing a redo routine. Companion to the `wal-and-xlog`
skill and to `docs-distilled/wal-for-extensions.md` (the parent chapter) and
`docs-distilled/custom-rmgr.md` (the heavier sibling).

## Non-obvious claims

- **Four-call lifecycle:** `GenericXLogStart(relation)` →
  `GenericXLogRegisterBuffer(state, buffer, flags)` (returns a *temporary copy*
  to scribble on) → `GenericXLogFinish(state)` (applies, marks dirty, sets LSNs,
  emits the record) — or `GenericXLogAbort(state)` to discard. [from-docs]
- **🔑 You must never touch the real page.** All edits go to the copy returned by
  `GenericXLogRegisterBuffer`; calling `BufferGetPage()` and writing directly
  defeats the delta machinery. The copy *is* the API. [from-docs]
- **Lock discipline:** hold an **exclusive** lock on each buffer from *before*
  `GenericXLogRegisterBuffer` until *after* `GenericXLogFinish`. During redo the
  generic redo function takes exclusive locks **in registration order** and
  releases in the same order — so register buffers in your intended lock order.
  [from-docs]
- **`GENERIC_XLOG_FULL_IMAGE` flag** forces a full-page image instead of a delta —
  set it for brand-new or wholly-rewritten pages. Without it the record carries a
  **byte-by-byte delta** of old vs new page. [from-docs]
- **Delta is dumb about moves.** The diff is literal byte comparison, so shifting
  data within a page produces a large delta ("not very compact … might be improved
  in the future"). Design page mutations to minimize byte movement. [from-docs]
- **Capacity cap:** at most `MAX_GENERIC_XLOG_PAGES` buffers per record; exceeding
  it errors. [from-docs]
- **Assumes standard page layout** — nothing useful may live in the hole between
  `pd_lower` and `pd_upper`; that region is skipped. [from-docs]
- **No critical section before Finish.** `GenericXLogStart` does *not* open a
  critical section, so you may palloc and even `ereport(ERROR)` freely between
  Start and Finish; the critical section is internal to `GenericXLogFinish`.
  [from-docs]
- **Unlogged relations are transparent** — no record is emitted, no special-casing
  needed in your code. [from-docs]
- **🚫 Invisible to logical decoding.** "Generic WAL records are ignored during
  Logical Decoding." If your extension needs its changes decoded, you must write a
  Custom WAL Resource Manager instead. [from-docs] — direct tie to
  `docs-distilled/custom-rmgr.md`.

## Links into corpus

- Parent: `knowledge/docs-distilled/wal-for-extensions.md`; sibling:
  `knowledge/docs-distilled/custom-rmgr.md`.
- Mechanism deep-dive: `knowledge/docs-distilled/wal-internals.md` (FPI / record
  assembly) and the `wal-and-xlog` skill's "Generic WAL vs custom rmgr" decision.
- Code: `source/src/access/transam/generic_xlog.c`, header
  `source/src/include/access/generic_xlog.h` (defines `GENERIC_XLOG_FULL_IMAGE`,
  `MAX_GENERIC_XLOG_PAGES`). [unverified — not line-pinned this run]
