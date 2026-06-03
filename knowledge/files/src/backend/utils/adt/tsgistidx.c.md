# `src/backend/utils/adt/tsgistidx.c`

## Purpose

GiST opclass for `tsvector_ops`. Signature-based index: each indexed
tsvector becomes a bit signature (Bloom filter) of fixed length; an
opclass-option `siglen` controls the bit-vector size (default
31*4 = 124 bytes, max `GISTMaxIndexKeySize`). Internal pages store
the OR of child signatures; lossy by design. 811 lines.

## Key functions

- `SignTSVector` struct — `:63`. Two key flavors via flag bits:
  `ARRKEY` (literal lexeme array, used for small leaves) and
  `SIGNKEY` (bit signature). `ALLISTRUE` marks "all bits set"
  shortcut.
- `gtsvector_compress` — Build signature from a tsvector;
  `HASH(sign, val, siglen)` macro sets bit `crc % siglen`.
- `gtsvector_consistent` — Match a tsquery against a signature.
  Tri-state logic: signature bit set → maybe match;
  signature bit unset → definitely no match.
- `gtsvector_union` — OR of children's signatures.
- `gtsvector_picksplit` — Linear bucket-split heuristic; Guttman-
  style.
- `gtsvector_penalty` — Cost of adding a child to a key.
- `tsvectorops_options` — Reloption handler for `siglen`.

## Phase D notes

Signature-based search is **lossy** — recheck at heap level is
mandatory and provided by `gtsvector_consistent` returning
`recheck = true`. Forgetting the recheck flag is a classic GiST bug
pattern.

The `ALLISTRUE` shortcut handles the saturation case where all bits
in the signature are set: the consistent function then must return
"maybe match" for everything; behavior is documented at the
opclass level. `[from-comment]`

`siglen` is user-tunable per index. Larger sig → fewer false
positives, more disk. Min documented in `tsvectorops_options`.

## Potential issues

- [ISSUE-correctness: All consistent/recheck paths must set
  `recheck = true` because signature search is lossy. Any
  refactor that flips this to false silently produces wrong
  results (missing rows OR phantom rows depending on direction).
  (medium)] — applies throughout `gtsvector_consistent`
- [ISSUE-dos: A user-set `siglen = GISTMaxIndexKeySize` consumes
  ~8KB per leaf signature. Tables with many indexed tsvectors
  amplify index size 100x vs default. Bounded by GIST page size
  but worth a warning in CREATE INDEX docs. (low)]
- [ISSUE-undocumented-invariant: `ALLISTRUE` is a 3-state shortcut
  conflated with `ARRKEY`/`SIGNKEY` via flag bitmask. Combining
  flags incorrectly (`ARRKEY | ALLISTRUE`) is undefined behavior
  not asserted. (low)]
