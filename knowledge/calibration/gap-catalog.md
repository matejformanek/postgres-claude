# Phase C consolidated gap catalog

**Status:** authoritative. Closes Phase C as of 2026-06-12.
**Source:** five per-patch calibrations (CB1, CB7, CB8, SP2, SP6).
**Methodology:** `knowledge/calibration/README.md`.

This file is the single index of every reviewer reflex Phase C surfaced
that the generic review pipeline missed. Each item is sourced (which
patch triggered it, how many times), motivated (which persona-bullet
drives it), and implemented (which skill / per-doc edit landed it). A
future re-run of Phase C against a new set of patches should regress
against this catalog to confirm none of the items decayed.

## Catalog (11 items)

Items grouped by where they landed.

### A. `review-checklist` Phase 0 — Reviewer-reflex gates (HARD gates)

These run before any other phase. They fail the checklist if the
patch is unclear on the gated question.

| # | Item | Trigger | Calibration support | Motivating persona |
|---|---|---|---|---|
| 1 | **`security@` embargo gate** — when COVER mentions DoS / decompression bomb / amplification / integer overflow / buffer overflow / injection / TOCTOU / privilege / REVOKE / GRANT AND patch touches a public-SQL-API path, fail until author confirms `security@` notification OR provides an explicit exemption argument (the SP6 "defense-in-depth + auth-required + DoS-class" shape is the model). | Pattern match on COVER body + path heuristic. | **5/5** (CB1, CB7, CB8, SP2 hard; SP6 exemption) — flagship recommendation. | Noah Misch §2. |
| 2 | **Test-omission skepticism** — when COVER admits "no regression test, fixture would dominate buildfarm / would need N LOC of scaffolding", surface the `PG_TEST_EXTRA=stress` precedent (Daniel Gustafsson's online-checksums work) and push for the test. Don't accept the self-justification. | Phrase match on COVER §X. | **3/3** (CB1, CB8, SP2); pre-empted (SP6 had both SQL+TAP). | Noah Misch §1 + §5. |
| 3 | **Install-script immutability** — when patch modifies a `contrib/*/*--A--B.sql` for an already-released `(A→B)` version, surface "shipped install-scripts are immutable post-release; ship `--B--C.sql` with the new behavior". | Path match + `git log` shipped-version check. | **1/1** (SP6) but flagged in the methodology plan as the install-script reflex to test for. | Tom Lane §2 (API/ABI back-compat reflex applied to install-scripts). |

### B. `pg-patch-review` Critic E — Reviewer-reflex probes

These add to the parallel critic fan-out. Critic E runs alongside A-D
and produces findings of severity `warning` (occasionally `blocking`
for #5-#7-#8 with concrete evidence).

| # | Item | Trigger | Calibration support | Motivating persona |
|---|---|---|---|---|
| 4 | **Cleanup-on-early-return tracing** — when patch adds an early `return` inside a function that owns a `z_stream`, `BufFile`, `FileFd`, `MemoryContext`, or similar resource handle, surface "trace cleanup path under the new error return". | Diff scan for new `return` inside function whose entry block owns a resource handle. | **1/1** (CB1 — compression filter). Generalizes to any IO/resource code. | Daniel Gustafsson §errorhandling discipline. |
| 5 | **Multibyte/encoding interaction check** — when patch walks input byte-by-byte (`*p++`, manual `for` over `varlena`/`text`/`cstring`) OR caps input/output size on a text primitive, surface "enumerate worst-case per encoding (UTF-8, GB18030, EUC_JP, EUC_KR, EUC_CN, EUC_TW); cite Unicode TR / SpecialCasing.txt for any UTF-8-specific bound". | Pattern match on byte-walking parsers + size-cap primitives. | **2/2** (CB7 parser, SP2 text primitive). | Noah Misch §4 + Jeff Davis "Unicode standard fidelity". |
| 6 | **Subsystem-local cap discoverability** — when patch adds a `#define` to a contrib `.c` file, surface "move to `<subsystem>.h` if a public-style cap; cite precedent constant in same area". | Diff scan for new `#define` in `contrib/*/*.c`. | **1/1** (CB7). | Peter Eisentraut style. |
| 7 | **"Third state" cross-check for binary-format changes** — when patch changes how a flag-bit / version-bit / layout-bit is interpreted, surface "enumerate third state — bit set but structure invalid, OR bit unset but structure looks valid". | Pattern match on flag-bit / version-bit interpretation diffs. | **1/1** (CB8 — hstore `HS_FLAG_NEWVERSION`). | Heikki Linnakangas binary-format reflex. |
| 8 | **`injection_points` reproducer for DoS / scratch-allocation claims** — when patch claims "prevents N MB/GB scratch allocation" or "fixes a race", surface "include `src/test/modules/injection_points` measurement at the allocation boundary". | Phrase match on COVER body. | **2/2** (CB7 + CB8). | Noah Misch §5. |
| 9 | **Hot-path branch-prediction / micro-benchmark check** — when patch adds a guard check on a function reachable from `WHERE` / `JOIN` / `GROUP BY` predicates, surface "include micro-benchmark confirming guard is unlikely-branch and adds <1% overhead on typical inputs". | Path match on `src/backend/utils/adt/*` query-evaluator funcs + diff scan for new guard. | **1/1** (SP2 pg_strlower). | Thomas Munro + Heikki Linnakangas perf reflex. |
| 10 | **Symmetric-check refactor for N-entry-point guards** — when patch adds same guard logic to 3+ entry points of the same module, surface "consider a shared inline helper to keep entry points symmetric". | Diff scan for 3+ near-identical added blocks. | **1/1** (SP2 — 4 pg_str* sites). | Peter Eisentraut symmetric-primitives reflex. |
| 11 | **Persona-aware backpatch routing** — when patch claims back-patching AND the predicted top committer's 24mo backpatch rate is <5% (per `committer-map.md`), surface "X has 0-near-0 backpatches in 24mo; the realistic v16/v17/v18 landing committer is Y (per `domain-ownership.md` reviewer column)". | Cross-reference `committer-map.md` + `domain-ownership.md`. | **2/2 fired** (CB7, CB8 — Peter zero-backpatches). 2/2 didn't fire (SP2 Jeff backpatches; SP6 Tom backpatches). Rule needs <5% nuance, not binary check. | Per `committer-map.md` Peter row + Phase B finding. |

## Headline findings worth carrying

**Items 1, 2, 11 fired across multiple patches** — they are the most
load-bearing additions. Item 1 (`security@` embargo gate) is the
flagship: 5-for-5 trigger rate, with SP6 giving the methodology the
exemption-protocol shape it needed.

**Items 3, 4, 6, 7, 9, 10 each fired on exactly one patch.** Pattern:
each is a subsystem-specific reviewer reflex that the generic
pipeline didn't encode. The right shape for these is "add as a
single reusable critic" rather than "wait until they fire on the
same patch twice" — the data is sparse because there are 30+ contrib
subsystems and only 5 patches.

**Items 5, 8 fired on two patches each** — confirms the generalisation
(byte-walking parser → text primitive; DoS-claim → race-claim).

**Persona-aware backpatch routing (item 11) needed nuance refinement
mid-Phase**: a binary check ("does the top committer backpatch?")
under-fires. The <5% rate rule keeps it accurate. Calibration cost
0 turns — caught in the SP2 calibration when Jeff Davis's
backpatch rate forced the question.

## How this feeds back

- **`.claude/skills/review-checklist/SKILL.md`** receives a new
  Phase 0 section "Reviewer-reflex gates" with items 1-3 as hard
  gates.
- **`.claude/skills/pg-patch-review/SKILL.md`** receives a new
  Critic E "Reviewer-reflex probes" with items 4-11 as warning-class
  findings (occasionally blocking when evidence is concrete).
- **Per-subsystem docs** (`knowledge/subsystems/<x>.md`) do NOT
  receive per-item edits in this PR — the reflexes apply across
  subsystem boundaries and adding 20 redundant blocks would be
  duplicating the catalog. The catalog itself + the skill edits is
  the single source.

## Calibration cross-reference

| Patch | Calibration doc | Items it fired |
|---|---|---|
| CB1 pgcrypto-bomb | `cb1-pgcrypto-bomb.md` | 1, 2, 4 |
| CB7 ltree-amplification | `cb7-ltree-amplification.md` | 1, 5, 6, 8, 11 |
| CB8 hstore-forge | `cb8-hstore-forge.md` | 1, 2, 7, 8, 11 |
| SP2 pgstr-maxalloc | `sp2-pgstr-maxalloc.md` | 1, 2, 5, 9, 10 |
| SP6 autoprewarm-revoke | `sp6-autoprewarm-revoke.md` | 1 (exemption), 3 |

## Maintenance protocol

- **When Phase C re-runs against a new set of patches** (e.g. when
  Phase D introduces new patches in a year): regress against this
  catalog. Items that don't trigger on the new set are *not*
  removed — they record that the reflex existed; they're worth
  keeping for future patches in the same shape.
- **When a NEW reviewer reflex surfaces** during a calibration:
  add to this catalog as item 12+, with the same fields. Update
  the skill section that hosts its class (`review-checklist`
  Phase 0 OR `pg-patch-review` Critic E).
- **When a persona is rewritten** (e.g. the 6-month re-mine of
  `chao-li.md`): scan the catalog for items citing that persona;
  refresh the persona-bullet cite if the bullet moved.

## Cross-references

- `knowledge/calibration/README.md` — Phase C methodology.
- `knowledge/calibration/{cb1,cb7,cb8,sp2,sp6}*.md` — per-patch
  source records.
- `knowledge/personas/{noah-misch,daniel-gustafsson,jeff-davis,
  peter-eisentraut,heikki-linnakangas,thomas-munro,tom-lane,
  michael-paquier,chao-li}.md` — motivating personas.
- `knowledge/personas/committer-map.md`,
  `knowledge/personas/domain-ownership.md` — data sources for item
  11's routing rule.
- `.claude/skills/review-checklist/SKILL.md` Phase 0 — items 1-3.
- `.claude/skills/pg-patch-review/SKILL.md` Critic E — items 4-11.
