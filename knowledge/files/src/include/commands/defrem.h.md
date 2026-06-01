# defrem.h

- **Source path:** `source/src/include/commands/defrem.h`
- **Lines:** 166
- **Last verified commit:** `ef6a95c7c64`

The "define and remove utility definitions" header — a **cross-cutting catch-all** for define.c (defGet* extractors), dropcmds.c (`RemoveObjects`), indexcmds.c (`DefineIndex`, `ReindexIndex`, `ReindexTable`, `ExecReindex`, opclass helpers `ResolveOpClass`/`GetDefaultOpClass`), opclasscmds.c (`DefineOpClass`/`DefineOpFamily`/`AlterOpFamily`), operatorcmds.c, aggregatecmds.c, functioncmds.c (`CreateFunction`/`AlterFunction`/`ExecuteDoStmt`/`ExecuteCallStmt`/`CreateCast`/`CreateTransform`/`CreateProceduralLanguage`), tsearchcmds.c, amcmds.c, foreigncmds.c, statscmds.c. Roughly one block of prototypes per consuming `.c` file. The file's location at this single header (rather than per-module headers) is historical.
