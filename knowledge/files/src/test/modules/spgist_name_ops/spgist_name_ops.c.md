# src/test/modules/spgist_name_ops/spgist_name_ops.c

**Pin:** `b78cd2bda5b1a306e2877059011933de1d0fb735`
**LOC:** 504
**Verification depth:** full read

## Role

A test SP-GiST operator class that indexes values of type `name` but stores them internally as `text`, mirroring the choices of the core `text_ops` SP-GiST opclass in `spgtextproc.c` but without collation-aware logic. [from-comment] `source/src/test/modules/spgist_name_ops/spgist_name_ops.c:4-12`. It serves as a worked reference for the SP-GiST opclass support-function contract (config / choose / inner_consistent / leaf_consistent / compress), reusing the core picksplit and exercising the leaf-type != input-type case. [verified-by-code] `source/src/test/modules/spgist_name_ops/spgist_name_ops.c:32-503`

## Public API

- `spgist_name_config` — SP-GiST config support function (proc 1): sets prefixType=TEXT, labelType=INT2, leafType=TEXT, canReturnData=true, longValuesOK=true. [verified-by-code] `source/src/test/modules/spgist_name_ops/spgist_name_ops.c:32-47`
- `spgist_name_choose` — choose support function (proc 2): decides descend / split / add-node for an inserted `name` value. [verified-by-code] `source/src/test/modules/spgist_name_ops/spgist_name_ops.c:124-262`
- `spgist_name_inner_consistent` — inner_consistent support function (proc 4): reconstructs prefix path and filters child nodes against scan keys. [verified-by-code] `source/src/test/modules/spgist_name_ops/spgist_name_ops.c:266-397`
- `spgist_name_leaf_consistent` — leaf_consistent support function (proc 5): reconstructs the full `name` and applies B-tree strategy comparisons. [verified-by-code] `source/src/test/modules/spgist_name_ops/spgist_name_ops.c:399-494`
- `spgist_name_compress` — compress support function (proc 6): converts a `name` input into the leaf `text` datum. [verified-by-code] `source/src/test/modules/spgist_name_ops/spgist_name_ops.c:496-503`
- `PG_MODULE_MAGIC` — loadable-module marker. [verified-by-code] `source/src/test/modules/spgist_name_ops/spgist_name_ops.c:29`

## Invariants

- INV-1: The picksplit support function (proc 3) is deliberately omitted; the opclass reuses the core text_ops picksplit. [from-comment] `source/src/test/modules/spgist_name_ops/spgist_name_ops.c:264`
- INV-2: Reconstructed values are always `text` (the leaf type), never `name`, and are always emitted in long varlena format (no short header, not toasted) so later invocations can assume that. [from-comment] `source/src/test/modules/spgist_name_ops/spgist_name_ops.c:285-291,418`
- INV-3: `in->level` equals `VARSIZE_ANY_EXHDR(reconstructedValue)` whenever a reconstructed value exists (level 0 iff NULL). Enforced by Assert in both consistent functions. [verified-by-code] `source/src/test/modules/spgist_name_ops/spgist_name_ops.c:294-295,422-423`
- INV-4: The reconstructed full `name` length stays within `NAMEDATALEN`; the leaf buffer is `palloc0(NAMEDATALEN)` and `Assert(fullLen < NAMEDATALEN)`. [verified-by-code] `source/src/test/modules/spgist_name_ops/spgist_name_ops.c:426-428`
- INV-5: Comparisons are non-collation-aware byte comparisons (`memcmp`), with tie-breaking by length, matching B-tree strategy semantics. [from-comment][verified-by-code] `source/src/test/modules/spgist_name_ops/spgist_name_ops.c:454-463`

## Notable internals

- SP-GiST opclass support-function set realized here: config (`spgist_name_config`), choose (`spgist_name_choose`), inner_consistent (`spgist_name_inner_consistent`), leaf_consistent (`spgist_name_leaf_consistent`), compress (`spgist_name_compress`); picksplit borrowed from core. [verified-by-code] `source/src/test/modules/spgist_name_ops/spgist_name_ops.c:32,124,266,399,496` + `:264`
- `formTextDatum` builds a text datum using short varlena header when it fits (`<= VARATT_SHORT_MAX`), else the full header — the same space optimization as core text_ops. [verified-by-code] `source/src/test/modules/spgist_name_ops/spgist_name_ops.c:53-73`
- `commonPrefix` / `searchChar` helpers: prefix-length scan and binary search over the int16 node-label array. [verified-by-code] `source/src/test/modules/spgist_name_ops/spgist_name_ops.c:78-122`
- `choose` result types: `spgMatchNode` (descend), `spgSplitTuple` (prefix mismatch or allTheSame collision), `spgAddNode` (new label). Uses dummy label `-1` for end-of-string and `-2` for the allTheSame split's lower tuple. [verified-by-code] `source/src/test/modules/spgist_name_ops/spgist_name_ops.c:157,162,203,217,244-251,256`
- Strategy numbers handled are the B-tree set (`BTLess/LessEqual/Equal/GreaterEqual/Greater StrategyNumber`); an unrecognized strategy raises `elog(ERROR, "unrecognized strategy number")`. [verified-by-code] `source/src/test/modules/spgist_name_ops/spgist_name_ops.c:359-379,465-487`
- Scan keys carry `name` arguments (`DatumGetName` / `NameStr`), while stored/reconstructed data is `text` — the input-type vs leaf-type distinction is the whole point of the module. [verified-by-code] `source/src/test/modules/spgist_name_ops/spgist_name_ops.c:347-354,449-451`

## Cross-refs

- `source/src/backend/access/spgist/spgtextproc.c` — the core text_ops opclass this is derived from (more detailed header comment lives there).
- `source/src/include/access/spgist.h` — `spgConfigIn/Out`, `spgChooseIn/Out`, `spgInnerConsistentIn/Out`, `spgLeafConsistentIn/Out` struct definitions and the `spgMatchNode`/`spgSplitTuple`/`spgAddNode` result-type enum.
- `source/src/backend/access/spgist/` — SP-GiST access method core driving these support-function callbacks.
- `source/src/include/varatt.h` — `SET_VARSIZE_SHORT` / `VARATT_SHORT_MAX` / `VARDATA_ANY` short-varlena macros.
- `source/src/include/access/stratnum.h` — `BTLessStrategyNumber` etc.
- `source/src/test/modules/spgist_name_ops/` — the `.sql`/`.out` regression tests and the opclass DDL (`CREATE OPERATOR CLASS ... USING spgist`).

## Potential issues

None.
