# copyfrom_internal.h

- **Source path:** `source/src/include/commands/copyfrom_internal.h`
- **Lines:** 205
- **Last verified commit:** `ef6a95c7c64`

Internal layout of `CopyFromStateData` — the runtime struct shared between `copyfrom.c` and `copyfromparse.c`. Defines `CopySource` enum (`COPY_FILE`, `COPY_FRONTEND`, `COPY_CALLBACK`), per-format routine vtables (`CopyFromRoutine` pointer), the four parsing buffers (`raw_buf`, `input_buf`, `line_buf`, `attribute_buf`), per-column input function lookup arrays, and ON_ERROR/LOG_VERBOSITY tracking. Not exposed outside the COPY subsystem.
