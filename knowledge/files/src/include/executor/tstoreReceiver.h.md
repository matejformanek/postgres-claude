# tstoreReceiver.h

- **Source:** `source/src/include/executor/tstoreReceiver.h` (31 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (whole file)

## API

```
extern DestReceiver *CreateTuplestoreDestReceiver(void);
extern void SetTuplestoreDestReceiverParams(DestReceiver *self,
                                            Tuplestorestate *tStore,
                                            MemoryContext tContext,
                                            bool detoast,
                                            TupleDesc target_tupdesc,
                                            const char *map_failure_msg);
```

Two-step create-then-configure pattern lets callers reuse one DestReceiver
across multiple target Tuplestores (e.g. functions.c per command). Set
`detoast=true` for WITH HOLD cursors. `target_tupdesc=NULL` skips the
conversion map.

## Tags

- [verified-by-code] full API surface.
