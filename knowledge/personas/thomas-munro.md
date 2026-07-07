# Persona: Thomas Munro

- Last verified: 2026-06-12
- Source pin: e18b0cb7344
- Method: git log mining of source/ + cross-cut against committer-map.md,
  contributor-map.md, domain-ownership.md.

## Role + email(s)

- Committer.
- Author/committer email: `Thomas Munro <tmunro@postgresql.org>`.
  641 historical author entries, single email. [verified-by-code]

## Activity profile (last 24mo)

| Vector                                              | Count |
|-----------------------------------------------------|------:|
| Commits as author (24mo)                            | 113   |
| `Reviewed-by: Thomas Munro` in others' commits      | 33    |
| Top reviewer of his own work (Heikki Linnakangas)   | 11    |

Counts via `rtk proxy git -C source/ log --since='24 months ago'
--author='Munro' --oneline`. [verified-by-code]

### Subsystem footprint (file touches, 24mo, top areas)

| Path                            | Touches |
|---------------------------------|--------:|
| src/backend/utils               | 54      |
| src/backend/storage             | 41      |
| src/test/regress                | 26      |
| src/backend/jit                 | 21      |
| doc/src/sgml                    | 19      |
| src/include/port                | 18      |
| src/interfaces/ecpg             | 17      |
| src/test/modules                | 16      |
| src/include/storage             | 13      |
| src/include/pg_config.h.in      | 9       |
| src/include/jit                 | 8       |
| src/backend/tsearch             | 7       |

The footprint is unusually broad for a "specialist" — but each
cluster traces back to a coherent platform-portability + I/O
infrastructure mission: storage/AIO, JIT/LLVM compat, encoding
bounds-safety, Windows/BSD/Hurd portability. [verified-by-code]

## Domain ownership

- **Read-stream API (`src/backend/storage/aio/read_stream.c`).** He
  wrote the file (14 commits in 24mo as author). It is the
  foundation under which Andres Freund's AIO work and Melanie
  Plageman's heap/vacuum streaming I/O sit. [verified-by-code]
- **AIO worker tuning.** "aio: Adjust I/O worker pool
  automatically" (2026-04-08), "aio: Simplify
  `pgaio_worker_submit()`" (2026-04-05). He is shipping incremental
  tuning to the AIO worker layer that backs the read-stream.
  [verified-by-code]
- **JIT / LLVM compatibility.** 21 src/backend/jit/ touches in
  24mo, almost all "make it build against LLVM N+1" maintenance:
  LLVM 17 inline pass, LLVM 21 AArch64 codegen, LLVM 22 lifetime.end,
  LLVM 22 SectionMemoryManager. He is the dedicated JIT
  build-bot. [verified-by-code]
- **Multibyte / encoding bounds safety.** 8 encoding-related
  commits in 24mo: "Replace `pg_mblen()` with bounds-checked
  versions", "Fix `mb2wchar` functions on short input", "Fix
  encoding length for EUC_CN", "Remove MULE_INTERNAL encoding",
  "Fix comments for Korean encodings". [verified-by-code]
- **Platform portability cleanup.** Windows MSVCRT float/
  `%I64` removal, GNU/Hurd `PS_USE_CLOBBER_ARGV`, O_CLOEXEC on
  Windows, BSD tar / ZFS quirks in TAP tests, RADIUS removal,
  `test_cloexec.c` fixups. The recurring theme is "kill an
  ancient platform quirk that nobody else owns." [verified-by-code]
- **`file_extend_method=posix_fallocate,write_zeros`** (2025-05-31)
  — feature commit; ties to the broader storage-extend
  performance work. [verified-by-code]

## Style + patterns

- **Title style:** subsystem-prefixed and terse ("jit: …",
  "aio: …", "read_stream: …", "Fix X in Y"). Heavy use of
  colons. [verified-by-code]
- **Commit cadence is bursty by theme.** Several JIT fixups in a
  week (LLVM-N+1 prep), then a quiet stretch, then a burst of
  encoding-safety fixups, then a quiet stretch. The themes don't
  mix in a single week. [verified-by-code, sample of dates]
- **Upstream-of-others.** This is the key persona signal:
  - `read_stream.c` is his; in the same 24mo window, Andres Freund
    has 38 commits *grepping for* `read_stream` (extensions and
    fixes), and Melanie Plageman has further streaming-I/O work
    that consumes it.
  - Counting commits to `src/backend/storage/aio/read_stream.c`
    itself: Munro 14, Andres Freund 8, Noah Misch 3, others ≤1.
    Munro is the file's primary author; Andres is the heaviest
    consumer-and-extender. [verified-by-code]
- **Doc + commit-message clarity.** His JIT fixups are dense
  with comments about the upstream LLVM API change. Treat his
  commit bodies as the canonical reference for what changed in
  each LLVM bump.


## Scenarios I'd review
<!-- persona-scenarios:auto -->

*Derived from Domain-ownership paths overlapping each scenario's §Files section. If this persona claims a directory and a scenario mentions any file under it, they're a likely reviewer.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

_(none — persona has no owned paths that overlap any scenario's files)_

<!-- /persona-scenarios:auto -->


## Subsystems I know
<!-- persona-subsystems:auto -->

*Derived from Domain-ownership paths overlapping each subsystem's `## Files owned` block.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

_(none)_

<!-- /persona-subsystems:auto -->

## Common reviewer/collaborator partners

`Reviewed-by:` trailers inside his own commits (24mo):

| Reviewer            | Count |
|---------------------|------:|
| Heikki Linnakangas  | 11    |
| Tom Lane            | 10    |
| Peter Eisentraut    | 8     |
| Andres Freund       | 5+    |
| Robert Haas         | 3     |
| Noah Misch          | 3     |
| Nazir Bilal Yavuz   | 3     |
| Michael Paquier     | 3     |
| Matheus Alcantara   | 3     |
| Nathan Bossart      | 2     |

The Heikki / Tom Lane / Andres / Peter Eisentraut quartet is the
storage + portability + executor brain trust; he is embedded in
it. Notably, Andres Freund both reviews him and is the largest
*consumer* of his read-stream API — they are tightly coupled.
[verified-by-code]

Going outward: 33 commits across the tree cite
`Reviewed-by: Thomas Munro`, mostly from Andres, Plageman,
Heikki, Nathan Bossart, Jacob Champion — i.e. the storage / AIO
adjacency. [verified-by-code]

## What to expect on a patch he would review

- He'll review patches that touch **read_stream, AIO worker pool,
  buffer manager I/O paths, JIT, encoding bounds, or platform
  portability** (BSD, Windows, Hurd, illumos).
- Strong attention to **bounds safety in multibyte handling**.
  Anything calling `pg_mblen()` (or its replacements) will get
  scrutinized for short-input cases.
- For **read-stream callers**, expect questions about distance
  decay, lookahead, batch mode, and pin lifetime. He has been
  iterating on these heuristics through 2025-2026 — assume the
  caller-side contract is in flux.
- **Build-bot reflex** — he routinely fixes builds against
  not-yet-released LLVM major versions; patches that introduce
  new LLVM-API uses should pre-check against LLVM HEAD.
- For **platform-portability** changes, he is the natural reviewer
  for anything that adds a `#ifdef` for an obscure platform; he
  prefers removing dead platform support to adding more `#ifdef`s
  (RADIUS removal, MULE_INTERNAL removal, MSVCRT float / %I64
  removal pattern).

## Landmark commits (last 12mo)

- **read_stream maintenance series** (2025-2026): a quiet but
  steady stream of `read_stream: …` commits hardening the API
  while Andres builds on top. Examples in the visible window:
  "read_stream: Remove obsolete comment" (2026-04-11), plus
  earlier work consumed by Andres's "Add `read_stream_{pause,resume}`"
  (38229cb9051) and "Reduce scope of heap vacuum per_buffer_data"
  (c623e8593ec). [verified-by-code]
- **`aio: Adjust I/O worker pool automatically`** (2026-04-08).
  Auto-tuning the AIO worker pool — operational improvement to the
  AIO subsystem he co-owns with Andres. [verified-by-code]
- **`Remove RADIUS support`** (2026-04-08) and **`Remove
  MULE_INTERNAL encoding`** (2026-04-08). Same-day cleanups
  removing dead surface area. [verified-by-code]
- **`Replace pg_mblen() with bounds-checked versions`**
  (2026-01-07) and the surrounding mb2wchar / encoding-length
  fixes. Multi-commit encoding-bounds-safety pass.
  [verified-by-code]
- **JIT LLVM 17 / 21 / 22 series** (2025-11 through 2026-04). Six+
  commits keeping JIT building across LLVM majors. This is
  unglamorous but a single-point-of-failure if it stopped.
  [verified-by-code]
- **`file_extend_method=posix_fallocate,write_zeros`**
  (2025-05-31). Storage extend-method GUC; one of his rare
  recent user-visible feature commits.
  [verified-by-code]

## Notes / hedges

- **Upstream-of-others-work technologist.** The read-stream
  API is the clearest case: he wrote it, then sat back while
  Andres (and Plageman, Noah Misch) consumed it for AIO, vacuum,
  and heap streaming. Per the file `read_stream.c`'s commit log,
  Munro 14 / Andres 8 / Noah 3 / others ≤1. Counting *callers
  using read_stream* (commits that grep for `read_stream`) over
  24mo: Andres 38, Munro 21, Paquier 11, Eisentraut 8 — i.e.
  Andres extends it nearly 2× as fast as Munro maintains it.
  [verified-by-code]
- This pattern (build the infrastructure, hand it off,
  maintain) means his **commit cadence understates his
  leverage**. A commit-count comparison to a feature committer
  is misleading.
- **JIT bus-factor.** Of the 21 JIT/include-jit touches over
  24mo, the overwhelming majority are his. Andres Freund is the
  only other recent JIT contributor with meaningful frequency.
  If both stepped back, JIT-build maintenance through future
  LLVM majors is at risk. [inferred from file-touch counts;
  flagged for follow-up]
- His sub-domains (encoding, JIT, AIO worker, read_stream,
  portability) don't share a single subsystem label — committer-
  map.md flagging him as "storage (read stream) + JIT + AIO worker
  tuning + encoding" is accurate. Treat the union of those areas
  as his beat for review routing.
- No personality / availability claims here; commit cadence is
  the only signal, and it remains steady through 2026-04.
  [verified-by-code]
