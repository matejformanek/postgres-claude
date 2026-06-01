# nbtpreprocesskeys.c

- **Source path:** `source/src/backend/access/nbtree/nbtpreprocesskeys.c` (2857 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `nbtsearch.c` and `nbtreadpage.c` (the consumers of the preprocessed scan keys), `nbtree.h` (`BTArrayKeyInfo`, the `SK_BT_*` private flag bits).

## Purpose

Preprocess the user-visible scan keys (a `ScanKey[]` of comparison-operator scan keys passed via `btrescan`) into a more efficient form for the scan: deduplicate redundant clauses, contradictions become `qual_ok = false`, ScalarArrayOpExpr (`= ANY (array)`) clauses become `BTArrayKeyInfo` entries, **skip-array** keys (introduced more recently for efficient skip scans) are constructed from leading-column inequalities, scan-direction "required to continue scan" flags (`SK_BT_REQFWD`, `SK_BT_REQBKWD`) are set, and DESC/NULLS-FIRST handling is baked in via the `SK_BT_INDOPTION_SHIFT` byte. [from-comment, nbtpreprocesskeys.c:1-13; verified-by-code]

## Key entry point

- `_bt_preprocess_keys(IndexScanDesc scan)` — invoked once per `btrescan` (before `_bt_first` does anything). Reads `scan->keyData[]`, writes `so->keyData[]` (sized at most `scan->numberOfKeys`), populates `so->arrayKeys[]`, sets `so->qual_ok`/`so->numberOfKeys`/`so->numArrayKeys`/`so->skipScan`.

## What it produces

- A *required-key*-marked, sorted, deduplicated, contradiction-checked, possibly-array-expanded `ScanKey[]` ready for `_bt_first` to use both for *positioning* (the leading equality keys + the first non-equality bound) and for *continuation* (the per-attribute "still in range?" check inside `_bt_checkkeys`).
- For each SAOP, a `BTArrayKeyInfo` with the materialized `Datum[]` (sorted by the type's `BTORDER_PROC`, so we can binary-search the array during scan).
- For each skip array (column without an equality input), an entry marked with `SK_BT_SKIP` whose `sk_argument` is invalid; the actual value is advanced via the opclass's `BTSKIPSUPPORT_PROC` during scan.

## Key invariants

- Contradictions → `qual_ok = false`. The whole scan returns zero rows without ever descending. [verified-by-code]
- "Required to continue" flags (`SK_BT_REQFWD`/`REQBKWD`) are set on the keys that determine when the scan can stop in each direction. These are the keys consulted by `_bt_checkkeys` to short-circuit the page-walk. [verified-by-code]
- Skip arrays exist only for indexes whose opclasses provide `BTSKIPSUPPORT_PROC`; otherwise the optimizer plans differently. [from-comment, nbtree.h:712-714]

## Cross-references

- **Called by:** `nbtsearch.c:_bt_first` (indirectly via the scan state being already preprocessed at rescan time).
- **Calls into:** opclass `BTORDER_PROC` and `BTSKIPSUPPORT_PROC`, `access/skey.c` for `ScanKey` manipulation, `utils/array.c` to expand SAOP arrays.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
