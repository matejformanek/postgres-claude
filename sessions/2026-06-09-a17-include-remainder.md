# Session — A17 src/include remainder load-bearing sweep (foreground)

**Date:** 2026-06-09 (continuing after A16)
**Phase:** A — corpus completeness + issue surfacing
**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Branch:** `ft_corpus_a17_include_remainder`

## Scope

The **`src/include/` load-bearing remainder pass** — 7 sub-trees,
93 headers, the executor + parse-tree + access-AM API layer.

| Sub-tree | Pre-A17 | New | Post-A17 | Coverage |
|---|---:|---:|---:|---:|
| `src/include/access` | 63 | 32 | 95 | 101%+ |
| `src/include/commands` | 33 | 10 | 43 | **100%** |
| `src/include/nodes` | 18 | 6 | 24 | **100%** |
| `src/include/parser` | 16 | 7 | 23 | **100%** |
| `src/include/tcop` | 6 | 3 | 9 | **100%** |
| `src/include/rewrite` | 7 | 2 | 9 | **100%** |
| `src/include/executor` (nodeXxx.h) | 28 | 33 | 61 | **100%** |
| **Total** | **171** | **93** | **264** | — |

## Method

Standard A-sweep pattern. **4 parallel agents:**

- **A17-1** access AM API + heap/toast/tuple (16 headers: amapi, amvalidate, tableam, table, genam, relscan, heaptoast, toast_helper, toast_internals, tupconvert, itup, attnum, printsimple, tupmacs, sdir, stratnum)
- **A17-2** access WAL/multixact/visibility/sequence (16 headers: rmgrlist, rmgrdesc_utils, bufmask, timeline, tsmapi, multixact_internal, sequence, visibilitymapdefs, syncscan, sysattr, cmptype, gin_tuple, tidstore, valid, skey, rewriteheap)
- **A17-3** commands + nodes + parser + tcop + rewrite (28 headers: copyapi, dbcommands_xlog, explain_format, explain_state, progress, propgraphcmds, repack, repack_internal, sequence_xlog, wait, miscnodes, multibitmapset, queryjumble, readfuncs, subscripting, supportnodes, kwlist, parse_enr, parse_graphtable, parser, parsetree, scanner, scansup, backend_startup, cmdtaglist, deparse_utility, prs2lock, rewriteGraphTable)
- **A17-4** executor nodeXxx.h (33 headers — completes the directory)

Wall time ~14 min. **Zero misdirection. 17th A-sweep in a row.**

## Output

**Per-file docs** (93 docs / 93 source headers):
- `knowledge/files/src/include/access/*` (+32)
- `knowledge/files/src/include/commands/*` (+10)
- `knowledge/files/src/include/nodes/*` (+6)
- `knowledge/files/src/include/parser/*` (+7)
- `knowledge/files/src/include/tcop/*` (+3)
- `knowledge/files/src/include/rewrite/*` (+2)
- `knowledge/files/src/include/executor/node*.md` (+33)

**Subsystem issue registers** (2 new + 1 extended, ~153 entries):
- `knowledge/issues/include-access.md` — ~70 entries (NEW)
- `knowledge/issues/include-cmds-nodes-parser-tcop-rewrite.md` — ~45 entries (NEW)
- `knowledge/issues/include-executor.md` — extended with A17-4 ~11 entries

**Progress ledgers updated:**

- `progress/files-examined.md` — +93 rows (slugs `include-{access,commands,nodes,parser,tcop,rewrite}-a17` + `include-executor-nodeXxx-a17`)
- `progress/coverage.md` — 1,777→**1,870 docs (69.3%→72.9%)**; src/include 67.3%→**78.3%**
- `progress/coverage-gaps.md` — src/include sub-tree status updated; attack order extended to #17 (this) + #18
- `progress/STATE.md` — last-activity narrative

**Branch note:** branched from `main` pre-A16 PR #103. Merge conflicts on landing will be confined to progress files (top-line numbers + appended rows).

## Confidence rollup

Aggregate ~78% `[verified-by-code]`, ~17% `[from-comment]`, ~5%
`[inferred]`, **0% `[unverified]`**. Discipline holds across all
17 sweeps.

## Headlines

### 🚨 `amapi.h` + `tableam.h` extension contract Assert-only

`amapi.h:233` + `tableam.h:312` — required callbacks (`ambuild`,
`amgettuple`, table-scan begin/end/getnext, etc.) validated only
via Assert in `GetIndexAmRoutine` / `GetTableAmRoutine`. In a
cassert-disabled production build, a malformed handler reaches the
call site as a NULL function pointer. Load-bearing for "load
arbitrary AM" Phase D thread parallel to A8 output_plugin.

### 🚨 `heaptoast.h` trusts caller valueid (A12 cross-table read API host)

`heaptoast.h:145` — `heap_fetch_toast_slice(rel, valueid, ...)`
trusts caller-supplied `valueid` against `toastrel`. The API surface
for A12's `tuple_data_split(do_detoast=true)` cross-table read
primitive. No cross-check that valueid belongs to toastrel at
header layer.

### 🚨 A11 cleartext-password 3-header cluster

- `queryjumble.h:93-97` — utility statements EXCLUDED from
  normalization; `CREATE USER ... PASSWORD '...'` stored verbatim
  in the jumble path
- `tcop/cmdtaglist.h:53-94` — dispatch table for event triggers
  that see the raw parsetree
- `tcop/deparse_utility.h:44-49` — `CollectedCommand.parsetree`
  retains the PASSWORD node

Cross-link as one cluster. Phase D pitch: centralized utility-
statement PASSWORD redaction layer.

### 🚨 `readfuncs.h` is the hostile-input deserializer never named

`readfuncs.h:36` — `stringToNode` is called from pg_rewrite,
pg_proc, pg_class.relpartbound, plan-cache, parallel-worker DSM
(at least 7 catalog/IPC sources). Not all fully sanitized at write.
Phase D pitch: hardened-deserializer that rejects unknown nodes by
default + explicit catalog-column cross-reference.

### 🚨 PG18 SQL/PGQ new attack surface

`propgraphcmds.h:20-21`, `parse_graphtable.h:20`,
`rewriteGraphTable.h:19`, `cmdtaglist.h` entries — entirely new
attack surface introduced in PG18. ACL/RLS propagation from
constituent tables to graph references undocumented.

### 🚨 `subscripting.h` + `supportnodes.h` self-asserted leakproof

`subscripting.h:39-48` + `supportnodes.h:114-116` — extension-set
`leakproof` / `stable` flags as self-asserted truths. RLS qual
ordering depends on these flags. Mis-flagged extension silently
breaks RLS guarantees. No runtime cross-check exists.

### `nodeCustom.h` unsandboxed extension RCE surface

`nodeCustom.h:21` — `CustomExecMethods` vtable runs with full
backend privilege. Third-party scan providers (Citus, Timescale,
Hydra, pg_strom) are load-bearing for many deployments;
supply-chain compromise of any such extension yields backend RCE.

### `nodeTableFuncscan.h` XMLTABLE→libxml2

`nodeTableFuncscan.h:19` — XMLTABLE drives libxml2 on user input.
XXE / DTD-bomb / billion-laughs surface; A7 xml.c XXE custom-
defense echo at executor layer.

### 4-site X-macro cluster confirmed

- `storage/lwlocklist.h` (A15)
- `access/rmgrlist.h` (A17)
- `tcop/cmdtaglist.h` (A17)
- `parser/kwlist.h` (A17)

All use no-include-guard X-macro pattern. A future shared-style
guide would unify them.

### `syncscan.h` is a NEW monitoring-as-extraction echo

`syncscan.h:25` — shared start-block hash leaks another session's
seq-scan position at 128-block granularity, observable cross-
database. Fresh "monitoring access = data extraction" surface
joining A7+A11+A12+A14 cluster (now 8+ sites).

### `rewriteheap.h` filename + DoS

`rewriteheap.h:43,55` — `pg_logical/mappings/<filename>` leaks
dboid + xid + LSN; stalled logical slot + heavy CLUSTER load fills
disk unboundedly. A8 echo at API layer.

### `multixact_internal.h` pg_upgrade silent contract

`multixact_internal.h:6` — group layout hardcoded into on-disk
format. Any change must coordinate with `multixact_read_v18.c`
shim, otherwise silent corruption.

### `visibilitymapdefs.h` is A14 pg_truncate_visibility_map anchor

`visibilitymapdefs.h:20` — header could carry a guarding comment;
trust model lives only in `pg_visibility.c` (A14 finding).

### `sequence.h` cross-tenant `nextval()` side-channel

`sequence.h:20` — monotonic + observable + shared = write-traffic
inference vector. A11 echo at access layer.

### `nodeForeignscan.h` async credentials reuse

`nodeForeignscan.h:34` — A11 echo; postgres_fdw connection-cache
invalidation on SET ROLE / SECURITY DEFINER boundaries needs
scrutiny in async path.

## New cross-corpus connections from A17

- **A8 output_plugin "load arbitrary code"** + **A17 amapi.h / tableam.h
  required-callbacks Assert-only** = **"load arbitrary extension code"
  Phase D thread** at 3+ sites now (output_plugin + IndexAmRoutine +
  TableAmRoutine).
- **A11 cleartext-password capture** → **3-header concentration**
  (queryjumble + cmdtaglist + deparse_utility) suggests centralized
  redaction patch.
- **A15 lwlocklist.h** + **A17 rmgrlist.h + cmdtaglist.h + kwlist.h**
  = **4-site X-macro cluster**; idiom doc candidate.
- **A11/A12/A14 monitoring-as-extraction** + **A17 syncscan.h +
  sequence.h + sysattr.h + progress.h + wait.h** = **8+ site cluster**.
- **A7 xml.c XXE** + **A17 nodeTableFuncscan.h** = **executor-layer
  XMLTABLE/JSON_TABLE confirmation**.
- **A15 execParallel security-envelope** + **A17 nodeGather +
  nodeGatherMerge** = **parallel-worker auth inheritance confirmation**.
- **A12 tuple_data_split cross-table read** + **A17 heaptoast.h
  no-toastrel-check** = **API host of the A12 finding**.

## Phase D pitch candidates surfaced

1. **Amcheck-style runtime contract verification hook** —
   `amselfcheck` on `IndexAmRoutine` + `TableAmRoutine`.
2. **Version/magic field on extension routine structs** —
   IndexAmRoutine + TableAmRoutine + CustomExecMethods + TsmRoutine.
3. **Runtime cross-check for `leakproof`/`stable` flags** on
   extension support functions (RLS-ordering integrity guard).
4. **`nodeCustom` provider attestation** — supply-chain hardening
   for third-party scan providers.
5. **Centralized utility-statement PASSWORD redaction layer** —
   closes 3-header A11 cluster (queryjumble + cmdtaglist +
   deparse_utility).
6. **Hardened `readfuncs.h` deserializer** — rejects unknown nodes
   by default; explicit catalog-column cross-reference list.
7. **`heap_fetch_toast_slice` toastrel cross-check** — closes A12
   cross-table read primitive at the API layer.

## What this sweep did NOT do

- No new docs for the 25 `src/include/port` subdirectory files
  (atomics/*.h, win32/*.h, win32_msvc/*.h) — carryover from A16,
  deferred to cloud.
- No new docs for `src/include/{partitioning,jit,backup,statistics,
  tsearch,regex,bootstrap,foreign,mb,archive,pch,datatype,portability}`
  remaining headers — small subdirs, cloud-fillable.
- Did NOT refresh source anchor (`4b0bf0788b0` is ~10 days stale).

## Position

**~72.9% coverage; gap ~694 files.** Cumulative since 2026-06-02:
17 A-sweeps shipped, +953 docs, +~2,568 issues. **17 sweeps in a
row with zero misdirection.**

Next foreground candidates: **refresh source anchor** (first-class
candidate — ~10 days stale) OR pivot toward **Phase B** (developer
personas mined from pgsql-hackers + commits) OR `src/test` regress
framework selectively OR finish remaining mid-priority `src/include`
subdirs via cloud.
