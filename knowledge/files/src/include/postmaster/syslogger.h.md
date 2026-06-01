# syslogger.h

- **Source:** `source/src/include/postmaster/syslogger.h`
- **Depth:** skim

## Symbols

- `SysLoggerMain` — the `B_LOGGER` `main_fn`.
- Pipe chunk header struct (`PipeProtoChunk`) — every chunk sent through
  the syslogger pipe has this prefix so multi-process writes interleave
  cleanly.
- `PIPE_CHUNK_SIZE`, `PIPE_MAX_PAYLOAD`.
- GUC globals: `Logging_collector`, `Log_directory`, `Log_filename`,
  `Log_RotationAge`, `Log_RotationSize`, etc.
- `SysLogger_Start` — postmaster-side launcher hook.
