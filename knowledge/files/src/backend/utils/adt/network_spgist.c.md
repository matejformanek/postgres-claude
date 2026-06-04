# network_spgist.c — SP-GiST opclass for `inet`

## Purpose

SP-GiST opclass for `inet`. Uses a radix-tree (trie) structure: each inner-node prefix is the common bits of all descendants, and child labels are the next bit(s). Often much smaller than the equivalent GiST index when addresses share long prefixes.

Source: `source/src/backend/utils/adt/network_spgist.c` (714 lines).

## Key functions

- `inet_spg_config` (50) — declares the opclass config. [verified-by-code]
- `inet_spg_choose` (69) — descend an inner node: match the existing prefix bit-by-bit; if a mismatch, split here. [verified-by-code]
- `inet_spg_picksplit` (166) — choose the longest common prefix of all input leaves as the inner-node prefix. [verified-by-code]
- `inet_spg_inner_consistent` (240) — given a search query, decide which child branches can match. [verified-by-code]
- `inet_spg_leaf_consistent` (324) — final check at leaf. [verified-by-code]

## Phase D notes

- **Trie-based pruning**: very efficient for `<<` ("is contained by") queries because the trie naturally partitions by prefix.
- **Family handling**: family is an explicit attribute of the inet, and inner-consistent prunes children of the wrong family.
- **Iterative descent driven by SP-GiST machinery**, no C-recursion concern.

## Potential issues

- `[ISSUE-dos: pathologically narrow networks all in the same /8 collapse to a long chain (radix trees are unbalanced by construction). Standard SP-GiST tradeoff (low)]`.
- `[ISSUE-correctness: inner_consistent must handle the family-mismatch case; a buggy prune that returned MAYBE for all children would still be correct (slower), but one that returned NO for a matching family would be a wrong-result bug (verified-by-code today)]`.

Confidence: `[verified-by-code]`.
