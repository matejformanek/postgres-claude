---
path: src/include/snowball/libstemmer/snowball_runtime.h
anchor_sha: e18b0cb7344
loc: 109
depth: stub
---

# src/include/snowball/libstemmer/snowball_runtime.h

The upstream Snowball runtime API header, vendored verbatim. Declares
the slice/cursor primitives every generated stemmer calls:
`find_among` / `find_among_b`, `slice_from_s` / `slice_from_v` /
`slice_del`, `insert_s` / `insert_v`, `replace_s`, `eq_s` / `eq_v`,
`in_grouping` / `out_grouping`, `skip_utf8` / `len_utf8`, plus the
`struct among` lookup-table type and the `HEAD` / `SIZE` / `CAPACITY`
buffer-header macros.

Reached indirectly: backend `.c` stemmers `#include
"snowball_runtime.h"` which resolves to the PG wrapper at
`src/include/snowball/snowball_runtime.h` (see
[snowball_runtime.h.md](../snowball_runtime.h.md)); that wrapper then
includes this file after re-binding `malloc/free` to `palloc/pfree`.

No PG-specific content; ships unmodified from snowballstem.org. See
[snowball/README.md](../README.md).
