# 2026-06-02 — A1 catalog headers sweep (foreground sweep #1)

**Type:** interactive (worktree `ft_corpus_a1_catalog_headers`).
**Outcome:** 72 new per-file docs covering every previously-uncovered
`.h` under `source/src/include/catalog/`; 68 `[ISSUE-*]` tags surfaced
and consolidated into the new `knowledge/issues/catalog.md` register;
coverage bumps 35.8% → 38.6%.

This is the first foreground sweep of Phase A. The setup PR (#33)
landed the infra; this one exercises the parallel pattern and validates
the issue-surfacing flow.

## What this commit did

### New files

| Path | Role |
|---|---|
| `knowledge/files/src/include/catalog/pg_*.h.md` × 70 + non-catalog 2 | 72 per-file docs (FormData + column tables + on-disk-char enums + cross-refs + per-file `## Potential issues`) |
| `knowledge/issues/catalog.md` | Consolidated register of all 68 surfaced issues, grouped by severity / pattern |
| `sessions/2026-06-02-a1-catalog-headers.md` | This log |

### Modified files

| Path | Change |
|---|---|
| `progress/files-examined.md` | +72 rows (one per header) |
| `progress/coverage.md` | Doc count 917 → 989; src/include 34.2% → 42.8%; total 35.8% → 38.6% |
| `progress/coverage-gaps.md` | Catalog dir moves from "Big absolute gap" to "Done"; suggested attack order renumbered; foreground sweep #2 (libpq stack) now priority 1 |

## Headers covered (alphabetical)

Standard pg_* catalog headers (70):

binary_upgrade, catversion, pg_aggregate, pg_am, pg_amop, pg_amproc,
pg_attrdef, pg_attribute, pg_auth_members, pg_authid, pg_cast, pg_class,
pg_collation, pg_constraint, pg_control, pg_conversion, pg_database,
pg_db_role_setting, pg_default_acl, pg_depend, pg_description, pg_enum,
pg_event_trigger, pg_extension, pg_foreign_data_wrapper, pg_foreign_server,
pg_foreign_table, pg_index, pg_inherits, pg_init_privs, pg_language,
pg_largeobject, pg_largeobject_metadata, pg_namespace, pg_opclass,
pg_operator, pg_opfamily, pg_parameter_acl, pg_partitioned_table,
pg_policy, pg_proc, pg_propgraph_element, pg_propgraph_element_label,
pg_propgraph_label, pg_propgraph_label_property, pg_propgraph_property,
pg_publication, pg_publication_namespace, pg_publication_rel, pg_range,
pg_replication_origin, pg_rewrite, pg_seclabel, pg_sequence, pg_shdepend,
pg_shdescription, pg_shseclabel, pg_statistic, pg_statistic_ext,
pg_statistic_ext_data, pg_subscription, pg_subscription_rel,
pg_tablespace, pg_transform, pg_trigger, pg_ts_config, pg_ts_config_map,
pg_ts_dict, pg_ts_parser, pg_ts_template, pg_type, pg_user_mapping.

## How it was done

Six general-purpose subagents launched in parallel, each writing 11-13
docs from a coherent family:

| Batch | Theme | Files | Issues |
|---|---|---:|---:|
| 1 | Core entity catalogs | 12 | 13 |
| 2 | Operators + AMs + constraints | 12 | 5 |
| 3 | Privileges + security + dependencies | 11 | 14 |
| 4 | Replication + foreign + extension | 12 | 16 |
| 5 | Statistics + types + sequences + rules | 12 | 9 |
| 6 | Text search + propgraph + infra | 13 | 11 |
| **Total** | | **72** | **68** |

Wall time: ~5 minutes from launch to all 6 completed (the longest batch
was ~4.6 min). Each agent read the existing `dependency.h.md` for tone
calibration, then read each header in its batch and wrote a structured
per-file doc following the established template (frontmatter + Purpose
+ Catalog definition + Columns table + Key declarations + Cross-refs +
optional Potential issues + Tally). Conservative on issue tagging —
default severity `maybe`; only flagged genuine concerns.

Agents returned structured summaries (files-examined rows + issue list +
observations); the orchestrator (this session) appended rows to the
ledger, refreshed coverage docs, and consolidated the 68 issues into
`knowledge/issues/catalog.md` grouped by Phase D data-leak priority /
on-disk char invariants / direct-struct-pun / cross-header coupling /
stale TODO.

## What the sweep surfaced

### Phase D data-leak candidates (likely / confirmed severity)

These are the most concrete starting points for the Phase D
data-leak-hardening project:

- **pg_statistic / pg_statistic_ext_data** — `stavalues1..5` and
  `stxdmcv` / `stxdexpr` arrays hold verbatim sample values from user
  columns. Protection lives at the view layer (`pg_stats`) + catalog
  ACL only; neither header carries a warning.
- **pg_parameter_acl canonicalization** — GUC names are documented as
  case-insensitive, but the unique index uses `text_ops` (case-sensitive).
  If GRANT-time and SET-time canonicalize differently, GRANT on `Foo.Bar`
  could silently fail to apply to `foo.bar` invocations. Worth a focused
  read of `parameterAclLookup` vs `set_config_option`.
- **pg_replication_origin uint16 overflow** — `roident` is a hand-allocated
  uint16 embedded in WAL records. A cluster that accumulates >65535
  origins over its lifetime silently wraps. Not documented.
- **pg_control struct evolution** — `ControlFileData` changes silently
  corrupt clusters unless `PG_CONTROL_VERSION` is bumped. The header
  documents the version macro but not the obligation.

### The on-disk char-code pattern

26 of the 68 issues are variants of the same pattern: catalog columns
store a single ASCII character whose meaning is given by a `#define`
elsewhere, but **only `dependency.h`'s `DependencyType` enum carries
an explicit "the character is the on-disk value; do not change" comment.**
Everything else (RELKIND_*, TYPCATEGORY_*, PROKIND_*, CONSTRAINT_*,
SUBREL_STATE_*, PUBLISH_GENCOLS_*, TRIGGER_FIRES_*, etc.) relies on
implicit knowledge. Renumbering any one of them is an on-disk format
break with no compile-time check.

**This is a candidate for a single small upstream patch** — add a
uniform `/* IMPORTANT: This is the on-disk value; do not change. */`
comment block at each site. Doc-only, low-risk, high clarity.

### Direct C-struct access puns

`pg_proc.proargtypes`, `pg_index.indkey`, `pg_partitioned_table.partattrs`
all rely on a fragile struct-offset invariant (the first varlena column
must sit at a known offset so C code can access it directly). Only
`pg_partitioned_table` explains the rationale. A `StaticAssertStmt` on
each offset would make the invariant compile-time-checked.

### PG18+ propgraph catalogs are documentation-debt

All 5 `pg_propgraph_*` headers have stub file-banner comments (just
filename + copyright + NOTES). Invariants (vertex/edge discriminant,
parallel array lengths, label-uniqueness-per-graph) live only in
`propgraphcmds.c`. Coordinated upstream docs patch candidate.

## Design / process observations (what worked, what to tighten)

### Worked

- **Six-way parallel fan-out** — wall time scaled cleanly. No write
  contention because each agent owned disjoint output paths
  (`knowledge/files/src/include/catalog/<file>.h.md`). Single-file
  bottleneck (`progress/files-examined.md`) sidestepped by having
  agents return rows, orchestrator append.
- **Agents read `dependency.h.md` first** for tone calibration. Results
  were stylistically consistent across batches even though six
  independent agents produced them.
- **Conservative issue-tagging discipline.** Telling agents to default
  severity `maybe`, only flag genuine concerns, no style nits — got a
  clean register that actually triages, not a noise pile.
- **Issue-by-pattern grouping in the register.** Reading the 68 entries
  as one undifferentiated list would be useless; grouped by Phase D
  priority / on-disk char / struct-pun / etc. it's actually actionable.

### To tighten for foreground sweep #2

- **Pre-seed the issue-pattern catalog.** The on-disk char-code pattern
  was so widespread that all 6 agents independently flagged variants of
  it. Telling future batch agents up front "if you see X, just tag
  with type=Y" would have unified the wording (one agent used
  `[ISSUE-ONDISK]`, another `[ISSUE-undocumented-invariant]`, the
  register normalized them all to `undocumented-invariant`).
- **Wall-time was ~5 min for 72 files** — call it 4 sec/file. For
  libpq stack (~157 files), allocate 12-15 min wall + plan for ~8
  agents instead of 6.
- **The `dev/` symlink missing in worktrees** — not a blocker (used
  absolute paths to `source/` via meta-repo symlink) but worth a
  README note for future agents.

## What this commit explicitly does NOT do

- **No subsystem doc.** A new `knowledge/subsystems/catalog.md` spine
  doc would synthesize across these 72 headers + the existing
  `_catalog_headers_overview.md`. Queued as a Phase A follow-up.
- **No upstream patches for the issues found.** The corpus side is
  done; turning any of the 68 issues into a CF patch is separate
  Phase D work (or its own `/pg-brainstorm`).
- **No changes to `dev/` or other knowledge/ trees.**
- **No catalog.md mirror into `knowledge/issues/_index`** — there's no
  index yet; flag for a future commit.

## Repository state after this commit

- 72 new files in `knowledge/files/src/include/catalog/`.
- 1 new file in `knowledge/issues/` (catalog.md, 68 rows).
- 1 session log.
- 3 progress files updated (coverage.md, coverage-gaps.md, files-examined.md).

Total: 77 files changed, ~3 800 lines added.

## Followup candidates surfaced

- **Foreground sweep #2 — libpq stack** (157 files, 0% coverage). Next
  Phase A active item.
- **Upstream doc-only patch** — add "this is on-disk; do not change"
  comments to the ~26 character-encoded catalog columns. Single
  coordinated patch; could land via `/pg-brainstorm → /pg-plan →
  /pg-implement` as a calibration target.
- **Upstream doc patch — propgraph headers.** Move invariants from
  `propgraphcmds.c` comments into the header banners.
- **StaticAssertStmt for struct-pun offsets** (pg_proc.proargtypes,
  pg_index.indkey, pg_partitioned_table.partattrs) — small C-only
  patch.
- **Phase D brainstorms** from the 5 likely-severity entries:
  pg_parameter_acl canonicalization; pg_replication_origin uint16
  overflow; pg_statistic info-leak surface; pg_authid no-TOAST cap;
  pg_largeobject_metadata acl-without-TOAST anomaly.

## Commit message for this work

```
ft(corpus): document 72 catalog headers (A1 sweep) + 68 issues to register

First foreground sweep of Phase A: cover every previously-undocumented
.h under src/include/catalog/ via 6 parallel general-purpose agents.
Wall time ~5 min; 72 per-file docs landed; 68 [ISSUE-*] tags surfaced
and consolidated into the new knowledge/issues/catalog.md register
grouped by Phase D data-leak priority / on-disk char invariants /
struct-pun / cross-header coupling / stale TODO.

Coverage bumps: 917 -> 989 docs (35.8% -> 38.6%); src/include
34.2% -> 42.8%; the catalog dir moves to "Done" in coverage-gaps.md;
foreground sweep #2 (libpq stack) promoted to priority 1.

The headline finding is the on-disk char-code pattern: 26 of the 68
issues flag catalog columns storing a single ASCII character whose
"the letter is the on-disk value; do not change it" invariant is only
documented at one site (dependency.h's DependencyType). A single
upstream doc-only patch could close the cluster.

Other Phase D data-leak candidates surfaced: pg_statistic / pg_statistic_ext_data
verbatim-sample leak surface, pg_parameter_acl GUC-name canonicalization
mismatch (case-insensitive name vs case-sensitive index), pg_replication_origin
uint16 overflow embedded in WAL, pg_control struct-version obligation
not documented in the header.

Session: sessions/2026-06-02-a1-catalog-headers.md
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```
