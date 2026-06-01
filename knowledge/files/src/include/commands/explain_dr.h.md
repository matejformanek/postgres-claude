# explain_dr.h

- **Source path:** `source/src/include/commands/explain_dr.h`
- **Lines:** 33
- **Last verified commit:** `ef6a95c7c64`

Defines `SerializeMetrics` (`bytesSent`, `timeSpent`, `BufferUsage bufferUsage`) and exports `CreateExplainSerializeDestReceiver`. Used by `EXPLAIN (ANALYZE, SERIALIZE)` to measure the cost of actually producing protocol-bound output without sending it on the wire.
