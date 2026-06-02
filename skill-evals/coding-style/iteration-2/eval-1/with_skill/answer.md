# Eval 1 — with skill

For a new `.c` file under `src/backend/access/heap/`, the top of the file
needs four things, in this order:

## 1. The mandatory file-header block (lines 1-N)

```c
/*-------------------------------------------------------------------------
 *
 * myfile.c
 *	  one-line description
 *
 * Portions Copyright (c) 1996-2026, PostgreSQL Global Development Group
 * Portions Copyright (c) 1994, Regents of the University of California
 *
 *
 * IDENTIFICATION
 *	  src/backend/access/heap/myfile.c
 *
 *-------------------------------------------------------------------------
 */
```

Both copyright lines verbatim. The `/*-------` opener tells pgindent to leave
the block alone.

## 2. Includes — `#include "postgres.h"` is line 1

```c
#include "postgres.h"

#include <stdio.h>
#include <unistd.h>

#include "access/heapam.h"
#include "access/xlog.h"
#include "utils/rel.h"
```

Three groups, blank line between each:
1. `"postgres.h"` first, on its own — **before any system header**. (For a
   frontend file it'd be `"postgres_fe.h"`; for shared code `"c.h"`.)
2. System headers (`<stdio.h>`, `<unistd.h>`, etc.) — yes, they get their own
   group. **You do not sprinkle `<stdio.h>` in with your project headers.**
3. Project headers, grouped, roughly alphabetical.

If you ever add a public header under `src/include/`, it must also compile
standalone (`make headerscheck`) and as C++ (`make cpluspluscheck`).

## 3. Static helper prototypes — forward-declaration block after includes

After the includes, before any function definition, put a block of
`static` prototypes for the helpers defined later in the file. This lets
you order the function bodies naturally without worrying about who calls
whom.

```c
static void my_helper(Relation rel, BlockNumber blkno);
static bool my_other_helper(HeapTuple tup);
```

## 4. Your "both OK in C99, right?" question — NO on both counts

PG uses a **C99 subset** that bans two things you're asking about, even
though plain C99 allows them:

- **`for (int i = 0; …)`** — banned. Declare `i` at the top of the
  enclosing block, then write `for (i = 0; …)`.
- **A temporary `int` halfway down the function body** — banned. All
  locals are declared at the top of the block, before any statement.
  This is the same "no mid-block decls" rule.

Other C99 features also banned: `//` line comments (use `/* … */`),
variable-length arrays, `\uXXXX` universal character names. Newer
features like `_Static_assert` need a fallback.
