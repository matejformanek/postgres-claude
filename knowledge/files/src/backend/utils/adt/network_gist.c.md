# network_gist.c — GiST opclass for `inet`

## Purpose

GiST opclass for `inet` (and `cidr`, via implicit cast). Inner-node key is `GistInetKey { minaddr, maxaddr, family, commonbits }` — the largest network that contains all leaves of the subtree, plus a "common bits" count to accelerate consistency checks.

Source: `source/src/backend/utils/adt/network_gist.c` (811 lines).

## Key functions

- `inet_gist_consistent` (114) — given a search query and an inner-node key, decide if any descendant could match (`@>`, `<@`, `>>`, `<<`, `=`, etc.). [verified-by-code]
- `inet_gist_union` (505) — union of N keys: pick the lowest min and highest max within a shared family. [verified-by-code]
- `inet_gist_compress` (542) — converts an `inet` leaf into a GistInetKey. [verified-by-code]
- `inet_gist_fetch` (590) — index-only-scan support: reconstruct the original inet from the key. [verified-by-code]
- `inet_gist_penalty` (620) — penalty for inserting a new entry into a given subtree (based on bit-extension cost). [verified-by-code]
- `inet_gist_picksplit` (663) — Guttman-style split: pick two seeds, distribute rest by penalty. [verified-by-code]
- `inet_gist_same` (797) — keys equal? [verified-by-code]

## Phase D notes

- **commonbits invariant**: `commonbits = number of leading bits identical across all addresses in the subtree`. Used to short-circuit consistency for queries narrower than commonbits. [from-comment]
- **Family-aware union**: a single index can mix IPv4 and IPv6, but inner keys are family-tagged; union of mixed-family children sets commonbits=0. [verified-by-code, comment block at 470-510]
- **No stack-depth concern**: GiST infrastructure manages recursion via heap-allocated stacks, not C stack.

## Potential issues

- `[ISSUE-dos: inserting many tiny networks that share no prefix degrades commonbits to 0 and forces full-leaf scans; standard GiST behavior, no cap (low — design)]`.
- `[ISSUE-correctness: inet_gist_fetch reconstructs the original inet from minaddr; if a future change makes the inner-key compression lossy, fetch would silently return wrong data on index-only scans (verified clean today)]`.

Confidence: `[verified-by-code]`.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
