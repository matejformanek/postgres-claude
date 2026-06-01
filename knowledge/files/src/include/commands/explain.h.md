# explain.h

- **Source path:** `source/src/include/commands/explain.h`
- **Lines:** 85
- **Last verified commit:** `ef6a95c7c64`

Public surface of EXPLAIN. Forward-declares `ExplainState` (real def in explain_state.h). Declares the `ExplainOneQuery_hook` (used by auto_explain), entry `ExplainQuery`, and the per-node display helpers `ExplainOneUtility`, `ExplainOnePlan`, `ExplainPrintPlan`, `ExplainPrintTriggers`, `ExplainPrintJIT`, `ExplainQueryText`, `ExplainQueryParameters`, `standard_ExplainOneQuery`.
