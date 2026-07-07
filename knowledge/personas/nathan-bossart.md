# Persona: Nathan Bossart

- **Last verified:** 2026-06-12
- **Source pin:** e18b0cb7344
- **Method:** `git log` mining of `source/` (commit bodies parsed for trailers, subjects scanned for prefix patterns, paths bucketed by subsystem) + cross-cut against `committer-map.md`, `contributor-map.md`, `domain-ownership.md`. No mailing-list archives.

## Role + email(s)

- Role: committer (active 24mo). Comparatively newer committer (lifetime rank #27).
- Primary email: `nathan@postgresql.org` — single identity.
- Lifetime committer rank: **#27** (429 lifetime commits — see `committer-map.md`).
- Identity rollups: none.

## Activity profile (last 24mo: 2024-06-11 .. 2026-06-11)

| Trailer | Count |
|---|---:|
| Commits authored (`%an` as committer) | 315 |
| Commits w/ `Discussion:` URL | 282 (90%) |
| Commits w/ `Backpatch-through:` | 64 (20%) |
| Reviewed-by trailer appearances (any commit) | 78 |
| Reported-by | 8 |
| Author trailer appearances | 17 |
| Co-authored-by | 13 |
| Other (Suggested + Tested + Diagnosed) | 15 |
| **Total trailer appearances** | **118** |

Self-authorship on his pushed commits: 11 explicit `Author: Nathan Bossart`, 205 with no Author trailer, 99 with someone else as Author. So ~68% of his work is his own (combined explicit-self + implicit-self), ~32% is committing others.

Cross-verified against `contributor-map.md` row "Nathan Bossart | 17 | 78 | 8 | 15 | 118".

Note: 12mo vs 24mo split is 162/315 ≈ 51% — very even cadence (per `committer-map.md`). No ramp-up or slow-down trend.

## Domain ownership

From `domain-ownership.md` per-subsystem leadership (24mo):

- `src/port/` — **top committer** (19 commits, narrowly ahead of Tom Lane 16 and John Naylor 16). This is the **arch-specific code home**: CRC32C, popcount, SIMD utilities.
- `src/bin/` — top-4 (86 commits, behind Peter Eisentraut 111, Michael Paquier 96, Tom Lane 92). Heavy on `pg_dump`, `pg_upgrade`, `vacuumdb`.
- `src/backend/postmaster/` — second top (24 commits, behind only Heikki Linnakangas 38).
- `src/include/` — top-5 (87 commits).
- `doc/src/sgml/` — 104 file-touches (highest in his path histogram).

**Read:** Nathan's profile is dual: (1) maintainer of **arch-specific / SIMD / port-layer code** — the popcount AVX-512, CRC32C, x86-64 specifics; (2) maintainer of **`pg_upgrade` and `pg_dump`** — the major server-side bin tools. The `committer-map.md` summary "utils + pg_upgrade + arch-specific (popcount, CRC) + src/port" is accurate.

His path histogram (top-3 files-touched in 24mo) is: `doc/src/sgml` (104), `src/backend/utils` (96), `src/test/regress` (86). The `doc/sgml` lead is unusual — Nathan documents what he ships.

## Style + patterns

### Commit message style

Subject prefix histogram (top 10):

| Prefix | Count |
|---|---:|
| `Add ...` | 58 |
| `Remove ...` | 30 |
| `Fix ...` | 29 |
| `pg_upgrade:` | 20 |
| `Use ...` | 16 |
| `doc:` | 14 |
| `pg_dump:` | 12 |
| `vacuumdb:` | 10 |
| `Rename ...` | 6 |
| `Optimize ...` | 6 |

- **Add-leaning subject prefix** (58 Adds vs only 29 Fixes) — distinct from Tom (113 Fixes) and Michael (157 Fixes). Nathan ships more new features-relative-to-fixes than the older committers.
- Heavy use of **tool prefix** (`pg_upgrade:`, `pg_dump:`, `vacuumdb:`) — like Michael, he tags by tool.
- Subject length: 48.9 chars (close to Michael's 53.6, well under Tom's 56).
- Subjects often end with period (project norm).

### Body conventions

`%B` mean ≈ 13.8 lines / commit, **median = 12 lines** (intermediate between Peter's 9 and Tom's 17).

Reading samples (e.g. `d7965d65fc5` "Add rudimentary table prioritization to autovacuum" Mar 2026): bodies tend toward 3-paragraph form — what, why, key tradeoffs — followed by a tight trailer block. Less narrative than Tom, more substantive than Peter.

### Discussion: URL discipline

**90%** of his commits cite a `Discussion:` URL (282/315). High discipline. The 10% gap is mechanical work (`Switch from tabs to spaces in postgresql.conf.sample`, .gitignore touchups).

### Backpatch behavior

**20% backpatch rate** (64/315). Slightly below Tom (23%) and Michael (25%), well above Peter (0%). Within the norm for an active committer.

### Arch-specific + SIMD focus

The `src/port/` and `src/include/port/` leads matter. Specific examples in 12mo:
- `79e232ca013` (Jan 2026): Move x86-64-specific popcount code to pg_popcount_x86.c.
- `ec8719ccbfc` (Oct 2025): Optimize hex_encode() and hex_decode() using SIMD.
- `bab2f27eaaa` (Mar 2026): Remove bits* typedefs.

Patches involving CPU-feature detection, AVX-512, ARM CRC, or build-time architectural conditionals will likely route through Nathan.

### pg_upgrade ownership

The `pg_upgrade:` subject tag appears 20 times in 24mo. `committer-map.md`'s headline landmark `626d723` "pg_upgrade: Add --swap for faster file transfer" is his. Patches to `src/bin/pg_upgrade/` typically reach him; he is the primary pg_upgrade reviewer/committer.


## Scenarios I'd review
<!-- persona-scenarios:auto -->

*Derived from Domain-ownership paths overlapping each scenario's §Files section. If this persona claims a directory and a scenario mentions any file under it, they're a likely reviewer.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

| Scenario | Via path(s) |
|---|---|
| [`add-new-aggregate-function`](../scenarios/add-new-aggregate-function.md) | `src/include`, `src/backend/utils` (+1) |
| [`add-new-bgworker`](../scenarios/add-new-bgworker.md) | `src/include`, `src/backend/postmaster` (+1) |
| [`add-new-buffer-strategy`](../scenarios/add-new-buffer-strategy.md) | `src/include`, `src/backend/utils` (+1) |
| [`add-new-builtin-function`](../scenarios/add-new-builtin-function.md) | `src/include`, `src/backend/utils` (+1) |
| [`add-new-cast`](../scenarios/add-new-cast.md) | `src/include`, `src/test/regress` |
| [`add-new-cost-model-knob`](../scenarios/add-new-cost-model-knob.md) | `src/include`, `src/backend/utils` (+1) |
| [`add-new-data-type`](../scenarios/add-new-data-type.md) | `src/include`, `src/backend/utils` (+1) |
| [`add-new-error-code`](../scenarios/add-new-error-code.md) | `src/include`, `src/backend/utils` |
| [`add-new-expression-eval-step`](../scenarios/add-new-expression-eval-step.md) | `src/include`, `src/backend/utils` (+1) |
| [`add-new-extension`](../scenarios/add-new-extension.md) | `src/include` |
| [`add-new-guc`](../scenarios/add-new-guc.md) | `src/include`, `src/bin` (+2) |
| [`add-new-hook`](../scenarios/add-new-hook.md) | `src/include` |
| [`add-new-index-am`](../scenarios/add-new-index-am.md) | `src/include`, `src/bin` (+2) |
| [`add-new-lwlock-tranche`](../scenarios/add-new-lwlock-tranche.md) | `src/include`, `src/backend/utils` |
| [`add-new-node-type`](../scenarios/add-new-node-type.md) | `src/include`, `src/backend/utils` |
| [`add-new-operator`](../scenarios/add-new-operator.md) | `src/include`, `src/backend/utils` |
| [`add-new-operator-class`](../scenarios/add-new-operator-class.md) | `src/include`, `src/test/regress` |
| [`add-new-pg-stat-view`](../scenarios/add-new-pg-stat-view.md) | `src/include`, `src/backend/utils` (+1) |
| [`add-new-plan-node`](../scenarios/add-new-plan-node.md) | `src/include`, `src/backend/utils` |
| [`add-new-protocol-message`](../scenarios/add-new-protocol-message.md) | `src/include` |
| [`add-new-replication-message`](../scenarios/add-new-replication-message.md) | `src/include` |
| [`add-new-shared-memory-region`](../scenarios/add-new-shared-memory-region.md) | `src/include`, `src/backend/utils` |
| [`add-new-sql-keyword`](../scenarios/add-new-sql-keyword.md) | `src/include`, `src/bin` (+2) |
| [`add-new-system-catalog-column`](../scenarios/add-new-system-catalog-column.md) | `src/include`, `src/backend/utils` (+1) |
| [`add-new-system-view`](../scenarios/add-new-system-view.md) | `src/include`, `src/bin` (+2) |
| [`add-new-table-am`](../scenarios/add-new-table-am.md) | `src/include`, `src/test/regress` |
| [`add-new-utility-statement`](../scenarios/add-new-utility-statement.md) | `src/include`, `src/bin` |
| [`add-new-wal-record`](../scenarios/add-new-wal-record.md) | `src/include`, `src/bin` |
| [`add-startup-hook`](../scenarios/add-startup-hook.md) | `src/include`, `src/backend/postmaster` (+1) |
| [`bump-catversion`](../scenarios/bump-catversion.md) | `src/include`, `src/bin` |
| [`integrate-with-plpgsql`](../scenarios/integrate-with-plpgsql.md) | `src/test/regress` |
| [`remove-from-catalog`](../scenarios/remove-from-catalog.md) | `src/include`, `src/test/regress` |

<!-- /persona-scenarios:auto -->


## Subsystems I know
<!-- persona-subsystems:auto -->

*Derived from Domain-ownership paths overlapping each subsystem's `## Files owned` block.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

- [`access-heap`](../subsystems/access-heap.md)
- [`access-nbtree`](../subsystems/access-nbtree.md)
- [`access-transam`](../subsystems/access-transam.md)
- [`executor`](../subsystems/executor.md)
- [`foreign`](../subsystems/foreign.md)
- [`jit`](../subsystems/jit.md)
- [`libpq-backend`](../subsystems/libpq-backend.md)
- [`optimizer`](../subsystems/optimizer.md)
- [`parser-and-rewrite`](../subsystems/parser-and-rewrite.md)
- [`partitioning`](../subsystems/partitioning.md)
- [`port`](../subsystems/port.md)
- [`replication`](../subsystems/replication.md)
- [`storage-buffer`](../subsystems/storage-buffer.md)
- [`storage-ipc`](../subsystems/storage-ipc.md)
- [`storage-lmgr`](../subsystems/storage-lmgr.md)
- [`tcop`](../subsystems/tcop.md)
- [`utils-cache`](../subsystems/utils-cache.md)
- [`utils-mmgr`](../subsystems/utils-mmgr.md)

<!-- /persona-subsystems:auto -->

## Common reviewer/collaborator partners

Top reviewers credited on commits Nathan pushed (24mo):

| Reviewer | Count |
|---|---:|
| Tom Lane | 49 |
| Michael Paquier | 35 |
| Daniel Gustafsson | 23 |
| Sami Imseih | 19 |
| John Naylor | 18 |
| Robert Haas | 18 |
| Andres Freund | 17 |
| Chao Li | 16 |
| Jeff Davis | 14 |
| Fujii Masao | 12 |

**Notable:** Tom Lane (49) is Nathan's #1 reviewer. This is consistent with `contributor-map.md`'s note that Tom is credited 59 times by Nathan as Reviewer. The **Nathan ↔ Tom axis** is one of the busiest reviewer pairings in the project.

**John Naylor (18 reviews)** — high for John, who is more focused than broad. Both work on arch-specific / SIMD / encoding code; this pairing makes domain sense.

**No self-credit visible in top 10.** Nathan apparently rarely self-tags as `Reviewed-by: Nathan Bossart` on his own pushed commits. He shares this convention with Heikki.

## What to expect on a patch he would review

1. **He will scrutinize portability.** Confidence: high. Patches touching `src/port/`, CPU-feature checks, SIMD intrinsics, CRC routines, or `#ifdef` blocks for arch detection will get architecture-specific review (x86-64 vs ARM, AVX-512 fallback paths, MSVC build implications).

2. **He will ask about pg_upgrade compatibility.** Confidence: high for any catalog/on-disk change. If your patch adds a new on-disk structure, expect "what does pg_upgrade do here?" If your patch changes a catalog representation, expect "does pg_upgrade handle the old format?"

3. **He prefers tool-prefixed subjects.** Confidence: high. Patches to `pg_dump`, `pg_upgrade`, `vacuumdb`, `pg_amcheck` should arrive with prefix already in place.

4. **He documents what he ships.** Confidence: very high — `doc/src/sgml` is his #1 path. Patches that add user-visible behavior without a doc update will be flagged.

5. **He values benchmarking on perf work.** Confidence: medium. The "Optimize hex_encode() and hex_decode() using SIMD" and "Optimize" series of his recent commits typically include performance numbers in the body. Patches claiming speedups without numbers may be returned for measurement.

6. **He cross-reviews with Tom Lane.** Confidence: very high (49 cited reviews). Expect Tom's review style (subject rewrites, API back-compat questions) to also surface on Nathan-committed patches.

## Landmark commits (last 12mo)

- `79e232ca013` (Jan 2026): Move x86-64-specific popcount code to pg_popcount_x86.c. — Representative arch-split refactor (547-line diff).
- `626d723` (mentioned in committer-map.md, pre-12mo): pg_upgrade: Add --swap for faster file transfer. — Headline pg_upgrade feature.
- `d7965d65fc5` (Mar 2026): Add rudimentary table prioritization to autovacuum. — New autovacuum feature (529 lines).
- `71ea0d67954` (Aug 2025): Restrict psql meta-commands in plain-text dumps. — Security-adjacent change with backpatch.
- `bd09f024a1b` (Jun 2025): Add new OID alias type regdatabase. — Catalog addition (428 lines).
- `ec8719ccbfc` (Oct 2025): Optimize hex_encode() and hex_decode() using SIMD. — Representative SIMD optimization with measurements.
- `1fbe2066dcc` (Jun 2026): refint: Remove plan cache. — Recent contrib cleanup.

## Notes / hedges

- **The "even cadence" finding** (162 commits in 12mo / 315 in 24mo ≈ 51%) makes Nathan the most consistently-paced top committer. No ramp-up, no slow-down. This is predictable behavior — patches submitted to him should land at a steady rate.
- **No striking outlier patterns.** Nathan's profile is broadly the "by-the-book PG committer": good Discussion: discipline (90%), moderate backpatch rate (20%), tool-prefixed subjects, documentation alongside features. Useful as a baseline for what "good PG-style" looks like.
- **The Tom Lane review axis** is worth flagging for Phase D submission planning: a patch likely to land via Nathan should expect Tom Lane review involvement.
- **Cross-references:**
  - `tom-lane.md` — Nathan's #1 reviewer (49 R-by); cross-cutting collaboration on src/port + arch code.
  - `michael-paquier.md` — Nathan's #2 reviewer (35 R-by); both work the tools/utils area.
  - `john-naylor` (no persona doc, see `committer-map.md`) — Nathan's #5 reviewer (18 R-by); SIMD + encoding overlap.
