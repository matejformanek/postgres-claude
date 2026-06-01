# copy.h

- **Source path:** `source/src/include/commands/copy.h`
- **Lines:** 140
- **Last verified commit:** `ef6a95c7c64`

Public surface of COPY. Declares the `CopyFormatOptions` struct, `CopyHeaderChoice` enum (`MATCH=-1`, `FALSE=0`, `TRUE=1`), and statement entries `DoCopy`, `BeginCopyFrom`, `EndCopyFrom`, `CopyFrom`, `BeginCopyTo`, `EndCopyTo`, `DoCopyTo`, `CopyOneRowTo`. Also exports the opaque `CopyFromState` / `CopyToState` typedefs (defined in copyfrom_internal.h / copyto.c) so other backend modules (`createas.c`'s INTO logic, FDW callbacks) can pass them around.
