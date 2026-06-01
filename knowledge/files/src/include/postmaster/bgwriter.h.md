# bgwriter.h

- **Source:** `source/src/include/postmaster/bgwriter.h`
- **Depth:** skim

## What's here

- `BackgroundWriterMain` prototype.
- `BgWriterDelay` GUC global.
- Historically also held checkpointer prototypes — modern code splits
  some of those into `checkpointer.h` / `xlog.h`.

Consumed by `postmaster.c`, `launch_backend.c`, the bgwriter itself.
