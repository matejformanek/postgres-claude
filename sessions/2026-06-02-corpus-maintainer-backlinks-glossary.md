# 2026-06-02 — corpus-maintainer: backlinks + glossary

## What I did
- Ran `pg-corpus-maintainer` cloud routine (recipe
  `.claude/cloud/pg-corpus-maintainer.md`) on branch
  `cloud/pg-corpus-maintainer/2026-06-02`.
- Pass 1 (backlinks): added 117 upward backlink lines across 61 per-file docs
  (17 new `## Synthesized by` blocks, 44 augmented). Backlinked docs 635 → 652.
- Pass 2 (glossary): created `knowledge/glossary.md` with 15 entries (the
  top-15 most-frequent internals terms by doc-frequency: backend, buffer,
  catalog, ereport, executor, heap, HeapTuple, palloc, planner, postmaster,
  relation, snapshot, TransactionId, TupleTableSlot, WAL).

## What I learned
- The recipe's Pass-1 signal (`[[...]]` wikilinks) does not exist in the
  corpus — 0 occurrences. The corpus's actual cross-ref convention is
  `source/src/...` path citations in long-form notes. Used that as the signal:
  precise, citation-grounded, no basename-collision risk.
- The earlier (2026-06-01) backlink generation used directory-scope/basename
  matching and left **spurious** backlinks — e.g. `walsender.c.md` and
  `postgres.c.md` both point to `subsystems/optimizer.md`. Logged for a future
  quality-auditor prune; this routine only adds, never edits existing lines.
- `source/` symlink target is absent in the cloud container; glossary entries
  are distilled from per-file docs and carry their verified `file:line` cites
  forward with explicit "— via <doc>" provenance (anchor `ef6a95c7c64`).

## What I'm unsure about
- Whether the recipe should be updated to say "source-path citations" instead
  of `[[...]]`, or whether the corpus should adopt wikilinks. Left the recipe
  untouched (scope discipline).

## Pointers left for next time
- Quality pass: prune spurious `optimizer.md` backlinks (basename-era residue).
- Glossary can grow next run: next-frequent undefined terms include LWLock,
  MemoryContext, MVCC, PGPROC, redo, rmgr, spinlock, TupleDesc, ResourceOwner.
