# ltree_gist.h

## One-line summary

**This file does not exist in the source tree.** The ltree GiST opaque types (`ltree_gist` struct, `LTG_*` flags, `LtreeGistOptions`, signature-bit `BITVECP` macros) live inside `ltree.h:256-313` alongside the scalar `ltree`/`lquery`/`ltxtquery` declarations. There is no separate GiST header.

## Why no separate header?

Historical — Teodor Sigaev's original contrib layout colocated the GiST opaque types with the scalar varlena types in a single header. The two opclasses (`gist_ltree_ops` in `ltree_gist.c` and `gist__ltree_ops` in `_ltree_gist.c`) both `#include "ltree.h"` and pull in everything via the single header.

## What lives where (the "would-be ltree_gist.h" contents)

In `source/contrib/ltree/ltree.h`:

- Line 232-254: GiST signature bit macros (`BITBYTE`, `SIGLENBIT`, `LTREE_SIGLEN_DEFAULT`, `LTREE_SIGLEN_MAX`, `LTREE_GET_SIGLEN`, `BITVECP`, `LOOPBYTE`, `GETBYTE`, `GETBITBYTE`, `CLRBIT`, `SETBIT`, `GETBIT`, `HASHVAL`, `HASH`).
- Line 267-293: `ltree_gist` struct + `LTG_*` flags + accessor macros (`LTG_ONENODE`, `LTG_ALLTRUE`, `LTG_NORIGHT`, `LTG_SIGN`, `LTG_NODE`, `LTG_LNODE`, `LTG_RNODE`, `LTG_GETLNODE`, `LTG_GETRNODE`).
- Line 291-292: `ltree_gist_alloc` declaration.
- Line 296-314: `LTREE_ASIGLEN_*` constants for the array opclass + `LtreeGistOptions` struct.

## Cross-references

- `knowledge/files/contrib/ltree/ltree.h.md` — covers all of the above.
- `knowledge/files/contrib/ltree/ltree_gist.c.md` — opclass implementation for scalar `ltree`.
- `knowledge/files/contrib/ltree/_ltree_gist.c.md` — opclass implementation for `ltree[]`.

<!-- issues:auto:begin -->
- [Issue register — `ltree`](../../../issues/ltree.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-organization: combining ~80 lines of GiST-only structure definitions into `ltree.h` (used by every operator file) means every `.c` file that just wants `ltree` / `lquery` types must also pull in `access/gist.h` indirectly (via the use of `GISTMaxIndexKeySize` at `ltree.h:237`). A split into `ltree_gist.h` would reduce header coupling, but would be on-disk-compatible. (nit — historical organization)] — `source/contrib/ltree/ltree.h:232-314`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-ltree.md](../../../subsystems/contrib-ltree.md)
