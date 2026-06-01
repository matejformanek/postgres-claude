# print.h

- **Source:** `source/src/include/nodes/print.h` (34 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## Purpose

Declares the debug pretty-print helpers implemented in `print.c`.

## API

```c
#define nodeDisplay(x)  pprint(x)

extern void  print(const void *obj);
extern void  pprint(const void *obj);
extern void  elog_node_display(int lev, const char *title,
                               const void *obj, bool pretty);
extern char *format_node_dump(const char *dump);
extern char *pretty_format_node_dump(const char *dump);
extern void  print_rt(const List *rtable);
extern void  print_expr(const Node *expr, const List *rtable);
extern void  print_pathkeys(const List *pathkeys, const List *rtable);
extern void  print_tl(const List *tlist, const List *rtable);
extern void  print_slot(TupleTableSlot *slot);
```

`:20-32` `[verified-by-code]`

## Cross-references

- Implementation: `source/src/backend/nodes/print.c`
