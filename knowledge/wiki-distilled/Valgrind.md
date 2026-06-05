---
source_url: https://wiki.postgresql.org/wiki/Valgrind
fetched_at: 2026-06-04T18:55:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
primary: false
staleness: tooling page, kept reasonably current; the build-flag and
  suppressions-file facts are stable. Complements the project's ASan profile
  (/setup-pg-asan) — Valgrind and ASan catch overlapping but not identical bugs.
---

# Wiki distilled — Valgrind

How to run a source-built PostgreSQL under Valgrind to catch memory bugs that
`--enable-cassert` alone misses (uninitialized-memory reads, use-after-`pfree`
caught via allocator redzones). The non-obvious part is that PG's memory-context
allocator is *itself* Valgrind-instrumented, so the tool understands palloc/pfree.

## What the wiki page says

- **Build with `CPPFLAGS="-DUSE_VALGRIND"`** (via meson or autoconf). This compiles
  in the Valgrind client-request hooks in the mcxt allocator. [from-wiki]
- **Pair it with `MEMORY_CONTEXT_CHECKING`** — "You should normally use
  MEMORY_CONTEXT_CHECKING with USE_VALGRIND; instrumentation of `repalloc()` is
  inferior without it." (`MEMORY_CONTEXT_CHECKING` is implied by
  `--enable-cassert`.) [from-wiki]
- **The allocator marks memory state for Valgrind.** palloc/pfree wrap
  allocations with access markers (NOACCESS / DEFINED / UNDEFINED) and redzones,
  so Valgrind flags **use-after-pfree** and **reads of uninitialized palloc'd
  memory** that a plain build can't see. [from-wiki]
- **Follow the fork model with `--trace-children=yes`** — the postmaster forks a
  backend per connection, and you must trace children to instrument the backends
  that do the real work. [from-wiki]
- **Typical invocation:** `--leak-check=no --gen-suppressions=all`,
  `--error-markers=VALGRINDERROR-BEGIN,VALGRINDERROR-END` (structures the output
  for parsing), and `--log-file=$HOME/pg-valgrind/%p.log` (per-PID logs). Add
  `--track-origins=yes --read-var-info=yes` for origin tracking (slower).
  [from-wiki]
- **Drive it with the regression suite:** run `make installcheck` against a
  postmaster hosted under Valgrind; narrow with
  `make installcheck-tests TESTS="json combocid"` (dependencies via
  `src/test/regress/parallel_schedule`). [from-wiki]
- **Load the in-tree suppressions: `--suppressions=src/tools/valgrind.supp`** —
  it covers known false positives (e.g. wcstombs/gconv AVX2 optimizations).
  Inlined functions may need the final stack frames stripped from a suppression
  pattern. [from-wiki]
- **Known gotchas:** Valgrind ≤ 3.8.1 crashes autovacuum on x86_64 (set
  `autovacuum = off` while testing); `mmap failed … Invalid argument` means
  nested Valgrind via a wrapper script (fix PATH / `which -a`). [from-wiki]

## How this maps to what Claude does

- This is the **Valgrind sibling of the project's ASan profile** (`/setup-pg-asan`
  / `setup-pg-asan` skill). ASan is faster and catches heap-OOB/UAF/double-free at
  near-native speed; Valgrind is slower but catches **uninitialized-memory reads**
  and understands the *palloc* layer via `-DUSE_VALGRIND`. Reach for Valgrind when
  a bug smells like "read of uninitialized backend memory" that ASan didn't flag.
  [inferred]
- The build-flag inversion from `Reviewing_a_Patch` applies: this is a
  correctness build (cassert ON), never a performance-measurement build.
  [inferred — cross-link knowledge/wiki-distilled/Reviewing_a_Patch.md]

## Links into corpus

- [[knowledge/subsystems/utils-mmgr.md]] — the memory-context allocator that
  `-DUSE_VALGRIND` instruments (palloc/pfree redzones).
- [[knowledge/idioms/memory-contexts.md]] — palloc/pfree discipline whose
  violations Valgrind catches.
- [[knowledge/wiki-distilled/Reviewing_a_Patch.md]] — feature-test build flags
  (cassert/debug) this shares.
- Skill: `setup-pg-asan` — the faster sanitizer profile; pick ASan vs Valgrind by
  bug class.
- Skill: `debugging` — attaching to the right forked backend (same fork-model
  caveat as `--trace-children`).
- Skill: `memory-contexts` — what a clean palloc/pfree lifecycle looks like.

## Confidence note

All substantive claims `[from-wiki]` (page fetched 2026-06-04). The ASan-vs-
Valgrind framing and build-flag note are `[inferred]`. Flag/path strings quoted
verbatim from the page; not re-run this session.
</content>
