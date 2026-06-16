# Proposed edits — iteration 1 (NOT applied)

## Summary of gaps found in grading

The skill already saturates the assertion rubric (30/30 with-skill). All
of iter-1's miss pressure shows up as baseline gaps (-12 from with-skill),
not skill misses. That means the right play is small **regression-hardening**
edits (sharpen the cites + close one small operational gap), not big
content additions. Concretely:

1. `[verified-by-code` cite for `MarkGUCPrefixReserved` says
   `guc.c:5178-5228`. The function actually starts at line **5185**; the
   surrounding comment block starts at 5178. Range is honest, but it
   doesn't quite point at the function. Tighten to `guc.c:5178-5228`
   (header comment + body) or `guc.c:5185-5228` (function only).
2. `[from-README` cite for the guc_malloc rule says
   `README:51-60`. The relevant rule actually sits at lines **50-62**
   (50-55 = string-replacement rule; 57-62 = extra-pointer rule). The
   skill's narrower 51-60 cite straddles the two rules but cuts off the
   first line of each — easy to fix.
3. The skill never mentions **`SplitIdentifierString` / `SplitGUCList`**
   as the canonical way to parse a `GUC_LIST_INPUT` GUC inside a
   check_hook. This is the partner API for list-style GUCs and a
   recurring operational question.
4. `guc_realloc` exists alongside `guc_malloc` / `guc_strdup` / `guc_free`
   (`source/src/include/utils/guc.h:473-476`) but the skill mentions only
   three of the four. Resizing an extra-payload is the typical use.
5. `GUC_check_errcode` is named in §6 but never explained — readers may
   not know it overrides the SQLSTATE of the rejection error, defaulting
   to `ERRCODE_INVALID_PARAMETER_VALUE`. One short line would help.
6. The check_hook signature in §6 says `newval *` which is ambiguous for
   the string case (`*newval` is `char *`, so `newval` is `char **`).
   A one-line note that the pointer type varies by GUC type would
   clarify.
7. The `[from-README]` cite for the whole hook trio is `README:25-109`,
   which is an 84-line block. That's a "see the whole section" cite,
   which is fine, but readers benefit from a finer-grained sub-cite for
   the assign-hook contract (README:78-109) and the show-hook contract
   (README:112-117).

## Concrete edits to consider

### 1. Tighten the `MarkGUCPrefixReserved` source cite

Change `[verified-by-code source/src/backend/utils/misc/guc.c:5178-5228]`
to `[verified-by-code source/src/backend/utils/misc/guc.c:5185-5228]`.
The function definition is at 5185; the leading-comment block starts at
5178 and is informative but not the body. Verified by reading
`source/src/backend/utils/misc/guc.c:5180-5228` directly: function header
at 5185, body 5187-5228.

### 2. Tighten the guc_malloc README cite

Change `[from-README source/src/backend/utils/misc/README:51-60]` to
`[from-README source/src/backend/utils/misc/README:50-62]`. The
string-replacement rule sits at lines 50-55 (sentence begins line 50);
the extra-pointer rule sits at 57-62. The current 51-60 cite cuts off
the first line of each. Verified by reading `source/src/backend/utils/misc/README:45-62`.

### 3. Add `SplitIdentifierString` / `SplitGUCList` to §6 or §7

Under §7 right next to `GUC_LIST_INPUT`, or as a sub-bullet at the end of
§6's check_hook description, add:

> **Parsing list-style GUCs:** inside the check_hook, use
> `SplitIdentifierString(rawstring, ',', &elemlist)` for identifier-style
> lists or `SplitGUCList(rawstring, ',', &elemlist)` for the general case.
> Both produce a freshly `pstrdup`'d list you must `pfree` / `list_free`.
> Don't roll your own splitter — these match how the parser handles
> `search_path`, including quoted elements.

Functions verified at `source/src/include/utils/varlena.h` — `SplitIdentifierString`
+ `SplitGUCList` declarations live there; widely used in
`source/src/backend/utils/misc/guc*.c` and `source/src/backend/commands/extension.c`.

### 4. Add `guc_realloc` to the §5 storage-rules paragraph

Currently §5 says "must be allocated with `guc_malloc` / `guc_strdup` —
**never `palloc`**". Add `guc_realloc` to the list and one line:

> Use `guc_realloc` to resize an existing `guc_malloc` allocation (e.g.
> growing a derived `extra` payload). All four live in
> `source/src/include/utils/guc.h:473-476`.

Verified at `source/src/include/utils/guc.h:473-476`:
- `guc_malloc(int elevel, size_t size)` — line 473
- `guc_realloc(int elevel, void *old, size_t size)` — line 474
- `guc_strdup(int elevel, const char *src)` — line 475
- `guc_free(void *ptr)` — line 476

### 5. Explain `GUC_check_errcode` in §6

Currently the four `GUC_check_err*` macros are listed inline without
explanation. Add one sentence:

> `GUC_check_errcode(sqlerrcode)` overrides the SQLSTATE; the default is
> `ERRCODE_INVALID_PARAMETER_VALUE` (22023), which is usually correct, so
> only override when you have a more specific code (e.g.
> `ERRCODE_INVALID_NAME` for typo-style rejections).

Defaults verified by reading guc.c's `set_config_with_handle` ereport
paths — the standard rejection SQLSTATE is `ERRCODE_INVALID_PARAMETER_VALUE`.

### 6. Clarify check_hook signature by GUC type

In §6 under `check_hook`, replace the first bullet with a table or note:

> Signature varies by GUC type. The exact pointer type of the first
> argument matches the variable's storage type:
>
> | GUC type | check_hook first arg |
> |---|---|
> | bool   | `bool *newval` |
> | int    | `int *newval` |
> | real   | `double *newval` |
> | string | `char **newval` (so `*newval` is `char *`) |
> | enum   | `int *newval` (enum encoded as int) |

Verified against `source/src/backend/utils/misc/README:25-30` which states
*"The "newvalue" argument is of type bool \*, int \*, double \*, or char \*\*
for bool, int/enum, real, or string variables respectively."*

### 7. Sub-cite README for assign + show hook contracts

In §6, under `assign_hook(newval, void *extra) → void`, add cite:
`[from-README source/src/backend/utils/misc/README:78-109]`.

Under `show_hook(void) → const char *`, add cite:
`[from-README source/src/backend/utils/misc/README:112-117]`.

Verified: assign-hook section at README:78-109 (signature + rollback rule
+ catalog-lookup gotcha); show-hook section at README:112-117 (signature
+ static-buffer note).

## Non-edits

- The five-row Define*Variable table at §1 is correct and matches
  `source/src/include/utils/guc.h:358-416` exactly. Don't change.
- The GucContext table at §2 matches `guc.h:71-80` exactly. Don't change.
- The flags table at §7 matches `guc.h:214-242` exactly (verified
  individually: `GUC_LIST_INPUT=0x000001`, `GUC_LIST_QUOTE=0x000002`,
  `GUC_REPORT=0x000040`, etc.). Don't change.
- §3 worker_spi citation `:303-360` verified — `_PG_init` at 303,
  `MarkGUCPrefixReserved` at 360.
- The `EmitWarningsOnPlaceholders` alias note cites `guc.h:421` — verified
  exactly (`#define EmitWarningsOnPlaceholders(className) MarkGUCPrefixReserved(className)`).
- §8 (workers cross-cutting) is the correct cross-link surface for
  `parallel-query` and `bgworker-and-extensions` siblings — don't expand
  it here.

## Score delta if all edits applied

Iter-1 with_skill is already 30/30 (saturated); iter-2 with_skill should
remain 30/30. Baseline should remain ~18/30 (the gaps are baseline
knowledge gaps the skill can't help with from the other side). The value
of these edits is **regression hardening** + **better source-cite
precision** + adding `SplitIdentifierString` (the one real operational
omission). None of the edits are speculative — every cite is verified
against `source/` before proposing.
