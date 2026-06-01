# gin.h

- **Source path:** `source/src/include/access/gin.h` (106 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Public AM-callable surface for GIN: opclass procnum constants, `extractQuery` searchMode flags, ternary-consistent return codes, parallel-build entry point prototypes. [from-comment, gin.h:1-9]

## Procnum constants

```
GIN_COMPARE_PROC          1  (mandatory)
GIN_EXTRACTVALUE_PROC     2  (mandatory)
GIN_EXTRACTQUERY_PROC     3  (mandatory)
GIN_CONSISTENT_PROC       4  (mandatory unless 6 present)
GIN_COMPARE_PARTIAL_PROC  5  (optional, for partial match)
GIN_TRICONSISTENT_PROC    6  (optional)
GIN_OPTIONS_PROC          7  (optional)
GINNProcs                 7
```

## searchMode flags (for `extractQuery`)

`GIN_SEARCH_MODE_DEFAULT` (only matches when keys exist), `GIN_SEARCH_MODE_INCLUDE_EMPTY` (also match items with no keys), `GIN_SEARCH_MODE_ALL` (match everything; opclass returned no keys to compare), `GIN_SEARCH_MODE_EVERYTHING` (match all, including null-item placeholders).

## Ternary-consistent return codes

`GIN_FALSE = 0`, `GIN_TRUE = 1`, `GIN_MAYBE = 2`.

Exposes prototype for `_gin_parallel_build_main` (worker entry).
