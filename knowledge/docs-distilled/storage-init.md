---
source_url: https://www.postgresql.org/docs/current/storage-init.html
fetched_at: 2026-06-11T00:00:00Z
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — §66.5: The Initialization Fork

Short but load-bearing: the `_init` fork is the entire mechanism by which an
**unlogged** relation gets reset to empty after a crash. Completes the fork picture
alongside `_fsm` and `_vm`.

## What it is [from-docs]

- *"Each unlogged table, and each index on an unlogged table, has an
  initialization fork."* It holds *"an empty table or index of the appropriate
  type"* — a pristine zero-row image of the relation. [from-docs]
  [verified-by-code, source/src/common/relpath.c — `INIT_FORKNUM` → "init"
  in `forkNames[]`; via knowledge/files/src/common/relpath.c.md]

## Why it exists [from-docs, inferred]

- Unlogged relations are **not WAL-logged**, so after an unclean shutdown their
  main fork cannot be trusted (changes may be torn / lost). Rather than recover
  them, PG **resets them to empty** — and the init fork is the empty template to
  reset *from*. [from-docs]

## How crash recovery uses it [from-docs]

On restart, for each unlogged relation:
1. **The init fork is copied over the main fork** (instant reset to empty).
2. **All other forks (`_fsm`, `_vm`, segments) are erased** — they are recreated
   automatically as needed. [from-docs]

This is why unlogged tables survive a clean shutdown but are emptied by a crash:
the reset is unconditional on crash recovery, driven entirely by the presence of
the init fork. [inferred, from-docs]

## Links into corpus

- [[knowledge/files/src/common/relpath.c.md]] — the `forkNames[]` table that
  names this fork on disk.
- [[knowledge/docs-distilled/storage-file-layout.md]] — where `_init` sits among
  the forks/segments.
- [[knowledge/docs-distilled/storage-fsm.md]] /
  [[knowledge/docs-distilled/storage-vm.md]] — the sibling forks erased during the
  reset.

## Gaps / follow-ups

- The exact recovery-time copy is implemented in `reinit.c`
  (`ResetUnloggedRelations`); no per-file corpus doc for it yet. The "copied over
  main fork" claim is `[from-docs]`; a read of `reinit.c` would pin the
  `[verified-by-code]` mechanics (and the `smgrimmedsync` durability of the copy).
