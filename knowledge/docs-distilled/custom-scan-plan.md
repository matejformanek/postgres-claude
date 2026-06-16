---
source_url: https://www.postgresql.org/docs/current/custom-scan-plan.html
chapter: "60.2 Creating Custom Scan Plans"
fetched_at: 2026-06-15
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
---

# Custom scan plan node — §60.2

Distilled from §60.2. Parent: [[knowledge/docs-distilled/custom-scan.md]].
This leaf covers the `CustomScan` *plan* node (the planning→execution
handoff); the execution-side `CustomScanState` is §60.3 (separate doc
this run).

## Non-obvious claims

- `CustomScan` embeds a plain `Scan` as its first field, then adds
  `flags`, `custom_plans` (child `Plan` nodes), `custom_exprs`,
  `custom_private`, `custom_scan_tlist`, `custom_relids` (a `Bitmapset`),
  and a `methods` pointer to a (statically allocated) `CustomScanMethods`.
  [from-docs §60.2]
- **The "custom" lists have asymmetric fixup rules:** `custom_exprs` is
  the list that `setrefs.c` and `subselect.c` post-process (so put
  anything containing Vars/SubPlans there); `custom_private` is opaque
  and never touched by core. [from-docs §60.2]
- **`CustomScan` is the one provider-pluggable node that you may NOT
  embed in a larger struct.** Unlike `CustomPath` and `CustomScanState`,
  every field of a `CustomScan` must be `copyObject`-able, because the
  planner copies plan trees — so a provider cannot hang extra C fields
  off the end of it. State that needs richer typing must round-trip
  through `custom_private` as copyable nodes. [from-docs §60.2]
- `scan.scanrelid` semantics mirror ForeignScan: the RT index for a
  single-relation scan, **zero when the custom scan replaces a join**.
  [from-docs §60.2]
- `custom_scan_tlist` is NIL for a base-relation scan (output matches the
  relation row type) but **must be supplied when the node replaces a
  join** — same rule as FDW `fdw_scan_tlist`. `custom_relids` lists the
  RT indexes the node stands in for (one member normally, several for a
  join replacement). [from-docs §60.2]
- The only mandatory `CustomScanMethods` callback documented here is
  `CreateCustomScanState(CustomScan *cscan)` → returns a `Node *`. It may
  allocate a struct *larger* than `CustomScanState` (embedding it as the
  first member); it must set the node tag and `methods` field and leave
  the rest zeroed. `BeginCustomScan` runs afterward, once
  `ExecInitCustomScan` has done the standard init. [from-docs §60.2]
- `flags` here has the same bit meaning as in `CustomPath` /
  `CustomScanState` (e.g. the mark/restore support bit consumed in
  §60.3); it is carried through unchanged from path to plan to state.
  [from-docs §60.2, inferred]

## Links into corpus

- Parent chapter: [[knowledge/docs-distilled/custom-scan.md]].
- Execution-side companion (this run): [[knowledge/docs-distilled/custom-scan-execution.md]].
- Source structs: [[knowledge/files/src/include/nodes/extensible.h.md]]
  (`CustomScan`, `CustomScanMethods`, `CustomExecMethods`,
  `CustomPathMethods`).
- The FDW analogue (the other planner-pluggable scan provider):
  [[knowledge/docs-distilled/fdw-planning.md]],
  [[knowledge/docs-distilled/fdw-callbacks.md]].
- Path→Plan machinery: [[knowledge/subsystems/optimizer.md]].

## Caveats / verification

- `[from-docs §60.2]`. The WebFetch of this page truncated the
  `CustomScanMethods` member list and the `CUSTOMPATH_*` flag table;
  the `CreateCustomScanState` callback and struct layout above are what
  the page reliably yielded. Re-verify the full method set and flag bits
  against `source/src/include/nodes/extensible.h` at anchor
  `b78cd2bda5b1a306e2877059011933de1d0fb735`.
