# contrib-ltree (hierarchical labeled paths)

- **Source path:** `source/contrib/ltree/`
- **Last verified commit:** `e18b0cb7344` (2026-06-12 anchor)
- **Extension version:** `1.3` (per `ltree.control`)
- **Trusted:** yes
- **Header:** `source/contrib/ltree/ltree.h`

## 1. Purpose

A SQL type for hierarchical labeled paths (e.g. `Top.Science.Astronomy`),
plus query types (`lquery` for path patterns, `ltxtquery` for
full-text-like queries against paths), array operators (`_ltree`),
and indexable operator classes for GiST + GIN. Typical use cases:
tag hierarchies, threaded conversations, taxonomies. Trusted —
non-superuser DBOs can install it.

## 2. Mental model

- **`ltree` is an array of labels.** Each label up to
  `LTREE_LABEL_MAX_CHARS = 1000` characters [verified-by-code
  `ltree.h:18`]. Labels are delimited by `.` in text I/O. Internal
  layout: `ltree_level` records concatenated, each with a `uint16
  len` length prefix.
- **Three indexable types.** `ltree` (the path), `lquery` (a
  glob-like pattern with `*` / `!` / `@`), `ltxtquery` (tsearch-like
  boolean queries against path components).
- **Two index AMs supported.**
  - **GiST** (`ltree_gist.c`, `_ltree_gist.c`) — primary; uses
    signature bitmap inside the `ltree_gist` struct.
  - **GIN** (`ltree_gin.c`) — added later; uses one entry per label
    in the path, fast for `<@`/`@>` ancestor/descendant queries.
- **The `LOWER_NODE` compile flag** (`ltree.h:30`) controls
  case-sensitivity of label comparison. Defined for everything
  except MSVC for historical pg_upgrade compatibility.

## 3. Key files

- `ltree.h` — public type layout: `ltree_level`, `ltree`, `lquery`,
  `ltxtquery` macros (`LEVEL_NEXT`, `LEVEL_HDRSIZE`).
- `ltree_io.c` — input/output for `ltree` + `lquery` + `ltxtquery`.
- `ltree_op.c` — operators: `<`, `<=`, `=`, `~` (matches lquery),
  `<@` / `@>` (ancestor / descendant).
- `lquery_op.c` — lquery-vs-ltree matching engine.
- `_ltree_op.c` — array-of-ltree operators.
- `ltree_gist.c` — GiST opclass: `picksplit`, `compress`, `union`,
  `consistent`, `same`.
- `_ltree_gist.c` — GiST opclass for `_ltree` (arrays).
- `ltree_gin.c` — GIN opclass.
- `ltxtquery_io.c`, `ltxtquery_op.c` — ltxtquery type.
- `crc32.c`, `crc32.h` — used by the GiST signature.

## 4. Key data structures

- **`ltree_level`** (`ltree.h:32-36`):
  ```c
  typedef struct {
      uint16 len;
      char   name[FLEXIBLE_ARRAY_MEMBER];
  } ltree_level;
  ```
  Variable-length labels, MAXALIGN-padded for word alignment.

- **`ltree`** (varlena) — header + `numlevel` uint16 + a sequence
  of `ltree_level` records. Walk with `LEVEL_NEXT`.

- **`lquery`** — same shape but each level is an `lquery_level`
  with flags (`LQL_NOT`, `LQL_ANY`, `LQL_STAR`) and one or more
  `lquery_variant` alternatives.

- **`ltxtquery`** — tree of `ITEM` nodes (operators AND/OR/NOT +
  operand labels), serialized as a postfix tree.

- **`ltree_gistkey`** — GiST internal-page key: signature bitmap
  + leaf-or-inner flag.

## 5. SQL surface (highlights)

- Types: `ltree`, `lquery`, `ltxtquery`.
- Operators: `=`, `<`, `<=` (lex order); `~` (lquery match);
  `?` (lquery array match); `@` (ltxtquery match);
  `<@`, `@>` (ancestor / descendant); `||` (concat).
- Functions: `nlevel(ltree)`, `subpath(ltree, offset, len)`,
  `index(ltree, ltree)`, `lca(ltree[, ltree, ...])` (lowest common
  ancestor), `text2ltree`, `ltree2text`.
- Opclasses: `gist_ltree_ops`, `gist__ltree_ops`, `gin__ltree_ops`,
  `gist_ltxtquery_ops`.

## 6. Invariants and gotchas

- **[INV-1]** Per-label length is bytes, not characters, in
  `uint16 len` — but the documented max is *characters* (1000).
  Multi-byte encodings can therefore use up to 4000 bytes per label.
  Don't conflate the two when validating input.
- **[INV-2]** `LOWER_NODE` *must* be uniform across pg_upgrade
  boundaries on the same cluster. The historical MSVC-vs-Unix
  divergence is the only documented exception; new code must not
  add another.
- **[INV-3]** GiST signature size is compiled in. Changing it
  invalidates existing indexes.
- The query types (`lquery`, `ltxtquery`) are designed as
  fixed-grammar mini-languages — extending them is a parser change.

## 7. Owners (as of 2026-06-12)

Historical author: Oleg Bartunov + Teodor Sigaev (the same duo as
tsearch / GiST). Recent commits are typically maintenance-class —
bug fixes around input validation, encoding edge cases.

## 8. Local reviewer reflexes

- Any input-parser change: enumerate worst-case per encoding
  (UTF-8 / GB18030 / EUC-JP) — character-vs-byte caps recur.
  Driver persona: `noah-misch.md` §4.
- Any new GiST signature change: check pg_upgrade story; the
  signature is on-disk.
- Any new operator: confirm correct strategy number assignment in
  `pg_amop.dat` (or the `ltree--*.sql` install script if it's an
  extension-defined opclass).


## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**12 files.**

| File |
|---|
| [`contrib/ltree/_ltree_gist.c`](../files/contrib/ltree/_ltree_gist.c.md) |
| [`contrib/ltree/_ltree_op.c`](../files/contrib/ltree/_ltree_op.c.md) |
| [`contrib/ltree/crc32.c`](../files/contrib/ltree/crc32.c.md) |
| [`contrib/ltree/crc32.h`](../files/contrib/ltree/crc32.h.md) |
| [`contrib/ltree/lquery_op.c`](../files/contrib/ltree/lquery_op.c.md) |
| [`contrib/ltree/ltree.h`](../files/contrib/ltree/ltree.h.md) |
| [`contrib/ltree/ltree_gist.c`](../files/contrib/ltree/ltree_gist.c.md) |
| [`contrib/ltree/ltree_gist.h`](../files/contrib/ltree/ltree_gist.h.md) |
| [`contrib/ltree/ltree_io.c`](../files/contrib/ltree/ltree_io.c.md) |
| [`contrib/ltree/ltree_op.c`](../files/contrib/ltree/ltree_op.c.md) |
| [`contrib/ltree/ltxtquery_io.c`](../files/contrib/ltree/ltxtquery_io.c.md) |
| [`contrib/ltree/ltxtquery_op.c`](../files/contrib/ltree/ltxtquery_op.c.md) |

<!-- /files-owned:auto -->

## Cross-references

- `.claude/skills/access-method-apis/SKILL.md` — GiST `picksplit` / `consistent` / `union` contracts.
- `.claude/skills/parser-and-nodes/SKILL.md` — lquery / ltxtquery mini-grammar implementations.
- `.claude/skills/fmgr-and-spi/SKILL.md` — operator implementations as fmgr functions.
- `.claude/skills/catalog-conventions/SKILL.md` — opclass / strategy / support-function registration via install SQL.
- `doc/src/sgml/ltree.sgml` — user-facing reference.
- `knowledge/subsystems/access-nbtree.md` — counterpart in-core AM (operator-class shape comparison).
