# `src/bin/scripts/common.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~27
- **Source:** `source/src/bin/scripts/common.h`

Public header for `common.c`. Pulls in
`common/username.h`, `fe_utils/connect_utils.h`,
`getopt_long.h`, `libpq-fe.h`, `pqexpbuffer.h` — so a consumer
`.c` only needs `#include "common.h"` to get the standard set of
includes shared across all `bin/scripts` programs. [verified-by-code]

## API / entry points

- `splitTableColumnsSpec`, `appendQualifiedRelation`,
  `yesno_prompt` — see `common.c.md`. [verified-by-code]

## Notable invariants / details

- This is a convenience grab-bag header: callers in
  `createdb.c`, `dropdb.c`, etc. typically do `#include
  "common.h"` and inherit libpq + getopt_long.
  [verified-by-code]

## Potential issues

- None notable.
