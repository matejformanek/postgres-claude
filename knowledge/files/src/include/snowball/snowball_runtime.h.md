---
path: src/include/snowball/snowball_runtime.h
anchor_sha: e18b0cb7344
loc: 67
depth: read
---

# src/include/snowball/snowball_runtime.h

## Purpose

PostgreSQL's wrapper around the upstream Snowball runtime header. Every
vendored stemmer `.c` does `#include "snowball_runtime.h"`, expecting to
get `snowball/libstemmer/snowball_runtime.h`. The backend's CPPFLAGS are
arranged so this PG-authored shim is found **first** instead. The shim
then includes the real upstream header after doing three PG-specific
fix-ups (`source/src/include/snowball/snowball_runtime.h:5-12`).

Three jobs:

1. **Force `postgres.h` first.** Header rules normally forbid including
   `postgres.h` from another header, but the alternative would be
   patching every machine-generated `.c` Snowball ships. Including
   `postgres.h` here ensures pg_config.h's largefile flags reach the
   system headers (`<stdio.h>`, …) before they get pulled in indirectly
   — otherwise mixed largefile settings across translation units cause
   silent ABI breakage (`snowball_runtime.h:25-30`).
2. **Strip `MAXINT` / `MININT`.** Some platform headers define these as
   macros, which then collide with Snowball's identifiers of the same
   name (`snowball_runtime.h:32-38`).
3. **Re-bind allocation to PG memory contexts.** After including the
   upstream runtime header, `#undef` and redefine `malloc / calloc /
   realloc / free` to expand to `palloc / palloc0 / repalloc / pfree`.
   This is what makes Snowball-allocated `SN_env` storage live inside
   the dictionary's memory context and get freed automatically on
   context reset, rather than leaking process heap
   (`snowball_runtime.h:43-65`).

## Public symbols

This file declares no new symbols of its own; everything it exposes is
either `#define`s or transitively re-exported from
`snowball/libstemmer/snowball_runtime.h` (which in turn pulls in
`api.h`). The shape Snowball stemmers actually call into:

| Symbol | Defined in | Role |
| --- | --- | --- |
| `SN_env` (struct) | `libstemmer/api.h` | The per-stem state — slice cursors (`c`, `l`, `lb`, `bra`, `ket`), the working buffer `p`, and integer/symbol register banks (`I[]`, `S[]`). One per dictionary instance. |
| `sb_symbol` / `symbol` | `libstemmer/api.h` | Underlying byte type for the working buffer (`unsigned char`). |
| `create_env(int S_size, int I_size)` | `libstemmer/api.c` (via header in `api.h`) | Allocate and zero-init an `SN_env`. Backs every `*_create_env` thin wrapper in the `stem_*.h` files. |
| `close_env(struct SN_env *)` | `libstemmer/api.c` | Free an `SN_env` (now via `pfree` thanks to the macro re-bind). |
| `SN_set_current(struct SN_env *, int, const symbol *)` | `libstemmer/api.c` | Load a new input word into `z->p` before calling `*_stem`. |
| `slice_from_s` / `slice_from_v` / `slice_del` / `insert_s` / `insert_v` / `replace_s` | `libstemmer/snowball_runtime.h` | Slice-edit primitives used by the generated stemmer bodies; mutate `z->p` between `z->bra` and `z->ket`. |
| `find_among` / `find_among_b` | `libstemmer/snowball_runtime.h` | Trie lookup against an `among` table — the core branching primitive in compiled Snowball algorithms. |
| `eq_s` / `eq_s_b` / `eq_v` / `eq_v_b` | `libstemmer/snowball_runtime.h` | Suffix/prefix string equality at the cursor. |
| `in_grouping[_U,_b]` / `out_grouping[_U,_b]` | `libstemmer/snowball_runtime.h` | Character-class membership tests against bitmap groups. |
| `skip_utf8` / `skip_b_utf8` / `len_utf8` | `libstemmer/snowball_runtime.h` | UTF-8 cursor stepping for the `stem_UTF_8_*` algorithms. |
| `HEAD`, `SIZE(p)`, `SET_SIZE(p,n)`, `CAPACITY(p)` | `libstemmer/snowball_runtime.h:6-17` | Header-bookkeeping macros for Snowball's variable-length symbol buffers (capacity + size stored at `((int *)p)[-2..-1]`). |

The PG wrapper does not add any symbols of its own — its contribution
is the macro environment around the include.

## Invariants & gotchas

- **Snowball-only header.** The leading comment is explicit: "this file
  should not be included into any non-snowball sources!"
  (`snowball_runtime.h:14`). Including it elsewhere would silently
  re-bind every `malloc/free` call in that translation unit to palloc,
  which would tear holes in lifetime assumptions wherever PG code
  expected real heap.
- **No separate shared library.** Snowball is statically linked into the
  backend; there is no `libpostgres-snowball.so`. The stemmer `.c`
  files compile straight into `dict_snowball.o` linkage via
  `src/backend/snowball/Makefile`.
- **PG does not modify these symbols.** Everything the macros override
  (`malloc`, `MAXINT`, …) is restored to nothing PG-visible; the rest
  is upstream Snowball's API verbatim. When Snowball cuts a new
  release, `src/tools/snowball/` re-imports the entire tree and this
  shim stays put.
- **`#include "postgres.h"` from a header is intentional.** The file
  comment calls out the coding-standard violation
  (`snowball_runtime.h:25-30`); reviewers spotting it in a grep should
  not "fix" it.

## Cross-refs

- `knowledge/files/src/include/snowball/README.md` — the directory tour.
- `knowledge/files/src/backend/snowball/dict_snowball.c.md` — the
  consumer; calls `create_env`, `SN_set_current`, `*_stem`, `close_env`
  per dictionary lookup.
- `source/src/include/snowball/libstemmer/snowball_runtime.h` — the
  upstream file this shim wraps (`HEAD/SIZE/CAPACITY` macros, slice
  primitives, `among` struct).
- `source/src/include/snowball/libstemmer/api.h` — the `SN_env` /
  `symbol` typedefs.
