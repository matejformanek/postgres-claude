# Eval 1 — baseline (no skill)

## Top of a new backend .c file

PostgreSQL convention for any backend `.c` file:

1. **Copyright / identification header** — a `/*---...---*/` block at the
   very top with filename, one-line description, the dual copyright lines
   ("Portions Copyright (c) 1996-YYYY, PostgreSQL Global Development Group"
   and "Portions Copyright (c) 1994, Regents of the University of California"),
   and an `IDENTIFICATION` field with the path.

2. **`#include "postgres.h"` first.** This is non-negotiable in the backend.
   It must come before any system header because it sets up feature-test
   macros and platform definitions.

3. **System headers next**, in their own group: `<stdio.h>`, `<unistd.h>`,
   `<sys/...>`, etc. Don't sprinkle these into the project-header block;
   they form a distinct group separated by a blank line.

4. **Project headers** (`"access/heapam.h"`, `"utils/rel.h"`, ...) in a
   third group, separated by a blank line from the system headers. Usually
   alphabetized within the group.

5. **Static prototypes block.** After all the includes (and any file-scope
   macros / typedefs / static globals), put a forward-declaration block of
   `static` prototypes for the helper functions defined later in the file.
   This lets you define the helpers in any order and keeps a clear "table
   of contents" near the top.

## "Both OK in C99, right?" — No.

PostgreSQL uses a **restricted subset of C99**. Two things are *not*
allowed even though the C99 standard permits them:

- **Mid-block declarations.** All locals must be declared at the top of
  the enclosing block, before any statement. A `int tmp = ...;` halfway
  down a function body is a style violation.

- **`for (int i = 0; ...)`.** Same reason — that's a declaration inside
  a statement. You declare `int i;` at the top of the enclosing block,
  then write `for (i = 0; ...; i++)`.

Other things banned in PG's C subset: `//` single-line comments (use
`/* ... */`), variable-length arrays, designated initializers that
some old compilers don't like, etc.

Why? Historically PG supported some compilers that didn't implement
all of C99. The policy has eased over time but the mid-block-decl and
`//` rules are still enforced because there's a lot of existing code
that depends on the convention and pgindent expects it.
