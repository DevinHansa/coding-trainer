# Senior Data Engineer — Skills Progression Ladder
# Zero Machine Learning. Pure engineering fundamentals.
# This file drives the adaptive curriculum engine.

---

## 🐍 Pure Python

### Level 1 — Foundations
| Tag | Concept | What Senior Means |
|-----|---------|-------------------|
| `py:data_structures` | Lists, dicts, sets, tuples | Know when to use each, understand hash vs ordered, amortized costs |
| `py:comprehensions` | List/dict/set comprehensions | Fluent with nested comprehensions, generator expressions, conditional logic |
| `py:string_manipulation` | Parsing, formatting, regex | f-strings, regex groups, efficient string building (join vs concat) |
| `py:sorting` | sorted(), key functions | Multi-key sorting, stable sort awareness, custom comparators |
| `py:filtering` | filter(), conditional logic | Lazy vs eager evaluation, short-circuit patterns |

### Level 2 — Intermediate
| Tag | Concept | What Senior Means |
|-----|---------|-------------------|
| `py:generators` | yield, itertools, lazy pipelines | Build memory-efficient pipelines, understand generator state |
| `py:decorators` | Function/class decorators | Write retry decorators, logging wrappers, timing decorators |
| `py:error_handling` | try/except, custom exceptions | Granular exception hierarchies, context managers, `__exit__` cleanup |
| `py:big_o` | Time/space complexity | Identify O(n²) traps, optimize to O(n log n) or O(n), space trade-offs |
| `py:collections` | Counter, defaultdict, deque, namedtuple | Choose the right collection for the job, understand underlying implementations |
| `py:functional` | map, reduce, partial, lambda | Know when functional style improves clarity vs when it obscures |

### Level 3 — Advanced
| Tag | Concept | What Senior Means |
|-----|---------|-------------------|
| `py:memory_management` | Slots, weak refs, gc, sys.getsizeof | Profile memory usage, avoid leaks in long-running processes |
| `py:concurrency` | threading, multiprocessing, asyncio | Know the GIL, when to use each model, producer-consumer patterns |
| `py:design_patterns` | Factory, Strategy, Observer, Singleton | Apply patterns to data pipeline architecture, not just theory |
| `py:testing` | pytest, fixtures, parametrize, mocking | Write testable data code, mock external dependencies, parametrized edge cases |
| `py:type_hints` | typing module, Protocol, TypeVar | Use type hints for self-documenting pipeline interfaces |

### Level 4 — Senior / Expert
| Tag | Concept | What Senior Means |
|-----|---------|-------------------|
| `py:custom_data_structures` | Implementing trees, graphs, LRU caches | Build specialized structures for data processing (interval trees, tries) |
| `py:profiling` | cProfile, line_profiler, memory_profiler | Profile production bottlenecks, identify hot paths |
| `py:metaprogramming` | Metaclasses, `__init_subclass__`, descriptors | Build configurable pipeline frameworks, plugin architectures |
| `py:edge_case_hardening` | Boundary values, None/NaN handling, encoding | Bulletproof code against production data chaos |
| `py:packaging` | Modules, imports, `__all__`, relative imports | Structure large data projects for team scalability |

---

## 🗄️ Advanced SQL

### Level 1 — Foundations
| Tag | Concept | What Senior Means |
|-----|---------|-------------------|
| `sql:joins` | INNER, LEFT, RIGHT, FULL, CROSS | Know exactly when each join type drops or duplicates rows |
| `sql:group_by` | GROUP BY, aggregate functions | Understand grouping semantics, multi-column grouping |
| `sql:filtering` | WHERE, HAVING, BETWEEN, IN | Know WHERE vs HAVING execution order, null-safe filtering |
| `sql:subquery` | Scalar, correlated, EXISTS | Know performance implications of correlated subqueries |
| `sql:aggregation` | SUM, COUNT, AVG, MIN, MAX | COUNT(*) vs COUNT(col), null behavior in aggregates |

### Level 2 — Intermediate
| Tag | Concept | What Senior Means |
|-----|---------|-------------------|
| `sql:window_functions` | ROW_NUMBER, RANK, DENSE_RANK, NTILE | Frame clauses, ROWS vs RANGE, running totals, moving averages |
| `sql:cte` | Common Table Expressions | Multi-CTE pipelines, readability patterns, when CTE vs subquery |
| `sql:lag_lead` | LAG, LEAD, FIRST_VALUE, LAST_VALUE | Period-over-period analysis, gap detection, sessionization |
| `sql:date_functions` | EXTRACT, DATE_TRUNC, intervals | Timezone-aware date math, fiscal calendar handling |
| `sql:having` | Post-aggregation filtering | Complex HAVING with multiple conditions, HAVING COUNT(DISTINCT) |
| `sql:case_when` | Conditional logic in SQL | Multi-branch CASE, CASE inside aggregates, pivoting with CASE |

### Level 3 — Advanced
| Tag | Concept | What Senior Means |
|-----|---------|-------------------|
| `sql:recursive_cte` | WITH RECURSIVE | Hierarchy traversal (org charts, BOM), graph walks, sequence generation |
| `sql:query_optimization` | Index usage, query plans, statistics | Read EXPLAIN output, identify full table scans, index-only scans |
| `sql:execution_plans` | EXPLAIN ANALYZE, cost estimation | Identify nested loop vs hash join decisions, buffer usage |
| `sql:set_operations` | UNION, INTERSECT, EXCEPT | Deduplication behavior, ALL variants, when to use vs JOIN |
| `sql:advanced_joins` | Self-joins, lateral joins, anti-joins | Pattern: find rows WITHOUT matching rows, running comparisons |
| `sql:null_semantics` | IS NULL, COALESCE, NULLIF, three-valued logic | NULL in joins, aggregates, CASE expressions — avoid silent data loss |

### Level 4 — Senior / Expert
| Tag | Concept | What Senior Means |
|-----|---------|-------------------|
| `sql:complex_analytics` | Multi-level window + CTE + aggregation | Build complete analytical queries: retention, cohort, funnel analysis |
| `sql:materialized_views` | Materialized views, refresh strategies | Pre-compute expensive queries, incremental refresh patterns |
| `sql:index_strategies` | B-tree, GIN, partial, covering indexes | Design indexes for specific query patterns, measure impact |
| `sql:partitioning` | Range, list, hash partitioning | Partition pruning, when to partition vs index, maintenance overhead |
| `sql:data_modeling` | Star schema, slowly changing dimensions | Design fact/dimension tables, SCD Type 1/2/3 implementations |
| `sql:pivot_unpivot` | Dynamic pivoting, CROSSTAB | Transform row data to columnar summaries and vice versa |

---

## ⚡ PySpark

### Level 1 — Foundations
| Tag | Concept | What Senior Means |
|-----|---------|-------------------|
| `spark:dataframe_basics` | Creating DataFrames, schema definition | StructType/StructField, inferSchema pitfalls, explicit typing |
| `spark:transformations` | select, filter, withColumn, drop | Lazy evaluation awareness, transformation vs action distinction |
| `spark:aggregations` | groupBy, agg, count, sum | Multi-column aggregation, alias naming, column expressions |
| `spark:io` | Read/write Parquet, CSV, JSON | Schema evolution, partition discovery, compression codecs |

### Level 2 — Intermediate
| Tag | Concept | What Senior Means |
|-----|---------|-------------------|
| `spark:rdd_vs_df` | RDD, DataFrame, Dataset trade-offs | Know when RDD is necessary (custom partitioning), Catalyst optimizer limits |
| `spark:column_operations` | F.col, F.lit, F.when, F.coalesce | Expression API fluency, avoid Python UDF overhead when possible |
| `spark:udf` | Python UDFs, Pandas UDFs | Performance implications, Arrow optimization, type mapping |
| `spark:joins` | Broadcast, sort-merge, shuffle hash | Join type selection, broadcast threshold tuning |
| `spark:window_functions` | Window specs, row-between, range-between | Spark-specific window behavior, partition ordering guarantees |

### Level 3 — Advanced
| Tag | Concept | What Senior Means |
|-----|---------|-------------------|
| `spark:broadcast_joins` | Broadcast hash join, hint API | When to force broadcast, size thresholds, skew with broadcast |
| `spark:partitioning` | repartition, coalesce, partition-by-write | Optimize shuffle, control output file count, partition pruning |
| `spark:data_skew` | Salting, AQE skew join, repartition | Diagnose skew in Spark UI, apply salting pattern, AQE config |
| `spark:caching` | persist, cache, storage levels | When to cache, memory vs disk, unpersist lifecycle |
| `spark:catalyst` | Logical/physical plans, predicate pushdown | Read `.explain(true)`, understand optimization rules |

### Level 4 — Senior / Expert
| Tag | Concept | What Senior Means |
|-----|---------|-------------------|
| `spark:medallion` | Bronze → Silver → Gold architecture | Design multi-layer lakehouse pipelines, SCD handling in each layer |
| `spark:dynamic_pipelines` | Config-driven transformations, metadata-driven ETL | Build pipelines that adapt to schema changes without code changes |
| `spark:streaming` | Structured Streaming, watermarks, triggers | Exactly-once semantics, late data handling, micro-batch vs continuous |
| `spark:performance` | AQE, CBO, spark.sql.shuffle.partitions | Tune shuffle partitions, broadcast thresholds, memory fractions |
| `spark:delta` | Delta Lake, MERGE, time travel, VACUUM | Upsert patterns, schema enforcement, optimize/z-order |

---

## 🔥 Real-World Gotchas (Cross-Cutting)

These appear as surprise scenarios at any level to build production debugging instincts.

| Tag | Gotcha | The Trap |
|-----|--------|----------|
| `gotcha:silent_failures` | Pipeline succeeds but produces wrong results | Missing WHERE clause drops rows silently, LEFT JOIN duplicates, NULL in aggregate |
| `gotcha:integer_overflow` | Forecast column exceeds MAX_INT | SUM of large values in INT column → overflow without error in some engines |
| `gotcha:timezone_bugs` | Datetime without timezone info | UTC vs local time mismatch, DST edge cases, `timestamp` vs `timestamptz` |
| `gotcha:non_deterministic_order` | Results depend on row ordering | No ORDER BY → random order, hash-based operations in Spark, dict ordering pre-3.7 |
| `gotcha:schema_drift` | New column appears in source data | Pipeline breaks or silently ignores new columns, schema enforcement patterns |
| `gotcha:duplicate_keys` | Primary key violation in upsert | MERGE with duplicate source keys → non-deterministic results |
| `gotcha:encoding_corruption` | UTF-8 vs Latin-1 mismatches | Mojibake in names/addresses, BOM characters, null bytes in strings |
| `gotcha:empty_partition` | Zero-row partition causes division by zero | Aggregation on empty group, coalesce(0) patterns, guard clauses |
| `gotcha:cartesian_explosion` | Unintended CROSS JOIN | Missing join condition → output rows = M × N, memory blow-up |
| `gotcha:late_arriving_data` | Records arrive after window closes | Watermark handling, idempotent upserts, reprocessing patterns |

---

## Mastery Levels

Each concept tag is tracked independently through these mastery levels:

| Level | Name | Criteria |
|-------|------|----------|
| 0 | **Novice** | Never attempted |
| 1 | **Learning** | Attempted but avg score < 50% |
| 2 | **Competent** | Avg score 50-69% with 3+ attempts |
| 3 | **Proficient** | Avg score 70-84% with 5+ attempts and streak ≥ 2 |
| 4 | **Expert** | Avg score ≥ 85% with 8+ attempts and streak ≥ 3 |

## The Ladder — Overall Progression

| Rank | Title | Requirements |
|------|-------|--------------|
| 🥉 | **Associate DE** | 10 concepts at Competent+ |
| 🥈 | **Mid-Level DE** | 20 concepts at Competent+, 10 at Proficient+ |
| 🥇 | **Senior DE** | 30 concepts at Proficient+, 15 at Expert, all gotchas attempted |
| 💎 | **Staff DE** | 40 concepts at Expert, all gotchas passed |
| 👑 | **Principal DE** | Everything at Expert, zero active weaknesses |
