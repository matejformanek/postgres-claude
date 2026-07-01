-- Workload 1: "any user would do this" baseline.
-- 100 iterations of: SELECT 1; SELECT count(*) FROM pg_class; pg_sleep(0.1);
-- Total runtime ~10s; exercises parser, catalog scan, sleep.
-- Run via: psql -h /tmp -p 5433 -d postgres -f normal-select.sql

\timing on
\set ON_ERROR_STOP on

-- Pre-workload snapshot
\echo === pre-workload pg_backend_memory_contexts ===
SELECT name, ident, type, level, total_bytes, total_nblocks, used_bytes, free_bytes, free_chunks
FROM pg_backend_memory_contexts
ORDER BY name, level;

\echo === starting 100-iter loop ===

DO $$
DECLARE
  i int;
  n bigint;
BEGIN
  FOR i IN 1..100 LOOP
    PERFORM 1;
    SELECT count(*) INTO n FROM pg_class;
    PERFORM pg_sleep(0.01);  -- 0.01 not 0.1 to keep wall-time reasonable
  END LOOP;
END $$;

\echo === post-workload pg_backend_memory_contexts ===
SELECT name, ident, type, level, total_bytes, total_nblocks, used_bytes, free_bytes, free_chunks
FROM pg_backend_memory_contexts
ORDER BY name, level;

\echo === backend pid for external leak probe ===
SELECT pg_backend_pid();
