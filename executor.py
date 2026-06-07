"""Sandboxed code execution engine for Python, SQL, and PySpark validation."""
import ast
import json
import re
import sqlite3
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import Optional

from config import PYTHON_EXEC_TIMEOUT, SQL_EXEC_TIMEOUT, MAX_OUTPUT_ROWS


# ═══════════════════════════════════════════════════════════
#  SQL EXECUTOR — Real execution against in-memory SQLite
# ═══════════════════════════════════════════════════════════

def execute_sql(user_query: str, sample_data: str,
                expected_output: str = None,
                test_cases: list = None) -> dict:
    """Execute SQL against in-memory SQLite with seed data, compare results."""
    results = {
        "passed": False,
        "test_results": [],
        "execution_time_ms": 0,
        "actual_output": "",
        "error": None,
    }

    start = time.perf_counter()
    try:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row

        # Inject seed data
        if sample_data:
            # Adapt PostgreSQL-isms to SQLite
            adapted_ddl = _adapt_sql_to_sqlite(sample_data)
            conn.executescript(adapted_ddl)

        # Execute user query
        user_query_clean = user_query.strip().rstrip(";")
        cursor = conn.execute(user_query_clean)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []

        # Format output
        actual_rows = []
        for row in rows[:MAX_OUTPUT_ROWS]:
            actual_rows.append("|".join(str(v) for v in row))
        actual_output = "\n".join(actual_rows)
        results["actual_output"] = actual_output
        results["columns"] = columns
        results["row_count"] = len(rows)

        # Compare against expected output
        if expected_output:
            match = _compare_sql_output(actual_output, expected_output)
            results["test_results"].append({
                "name": "expected_output_match",
                "passed": match,
                "expected": expected_output.strip()[:500],
                "actual": actual_output[:500],
            })

        # Run additional test cases
        if test_cases:
            for tc in test_cases:
                tc_result = _run_sql_test_case(conn, tc, user_query_clean)
                results["test_results"].append(tc_result)

        conn.close()

        # Overall pass = all test cases passed
        if results["test_results"]:
            results["passed"] = all(t["passed"] for t in results["test_results"])
        else:
            results["passed"] = len(rows) > 0  # At least returned something

    except Exception as exc:
        results["error"] = str(exc)[:500]
        results["test_results"].append({
            "name": "execution",
            "passed": False,
            "expected": "No errors",
            "actual": str(exc)[:300],
        })

    results["execution_time_ms"] = round((time.perf_counter() - start) * 1000, 1)
    return results


def _adapt_sql_to_sqlite(sql: str) -> str:
    """Adapt common PostgreSQL syntax to SQLite."""
    adapted = sql
    # VARCHAR(N) → TEXT
    adapted = re.sub(r"VARCHAR\(\d+\)", "TEXT", adapted, flags=re.IGNORECASE)
    # SERIAL → INTEGER
    adapted = re.sub(r"\bSERIAL\b", "INTEGER", adapted, flags=re.IGNORECASE)
    # BOOLEAN → INTEGER
    adapted = re.sub(r"\bBOOLEAN\b", "INTEGER", adapted, flags=re.IGNORECASE)
    # DECIMAL → REAL
    adapted = re.sub(r"DECIMAL(\(\d+,?\d*\))?", "REAL", adapted, flags=re.IGNORECASE)
    # TIMESTAMP → TEXT
    adapted = re.sub(r"\bTIMESTAMP\b", "TEXT", adapted, flags=re.IGNORECASE)
    # DATE → TEXT
    adapted = re.sub(r"\bDATE\b(?!\s*\()", "TEXT", adapted, flags=re.IGNORECASE)
    # INTERVAL → remove (SQLite doesn't support)
    adapted = re.sub(r"INTERVAL\s+'[^']*'", "'90 days'", adapted, flags=re.IGNORECASE)
    # CURRENT_DATE - INTERVAL '90 day' → date('now', '-90 days')
    adapted = re.sub(
        r"CURRENT_DATE\s*-\s*INTERVAL\s*'(\d+)\s*days?'",
        r"date('now', '-\1 days')",
        adapted, flags=re.IGNORECASE
    )
    # EXTRACT(MONTH FROM x) → strftime('%m', x)
    adapted = re.sub(
        r"EXTRACT\s*\(\s*MONTH\s+FROM\s+(\w+)\s*\)",
        r"CAST(strftime('%m', \1) AS INTEGER)",
        adapted, flags=re.IGNORECASE
    )
    return adapted


def _compare_sql_output(actual: str, expected: str) -> bool:
    """Compare SQL outputs flexibly (ignore whitespace, case for values)."""
    def normalize(s):
        lines = [line.strip() for line in s.strip().splitlines() if line.strip()]
        return sorted(lines)
    return normalize(actual) == normalize(expected)


def _run_sql_test_case(conn, test_case: dict, user_query: str) -> dict:
    """Run a single SQL test case."""
    name = test_case.get("name", "test")
    try:
        # If test case has setup SQL, run it
        if test_case.get("setup"):
            conn.executescript(test_case["setup"])

        cursor = conn.execute(user_query)
        rows = cursor.fetchall()
        actual = "\n".join("|".join(str(v) for v in row) for row in rows[:100])

        expected = test_case.get("expected", "")
        passed = _compare_sql_output(actual, str(expected))

        return {"name": name, "passed": passed,
                "expected": str(expected)[:300], "actual": actual[:300]}
    except Exception as exc:
        return {"name": name, "passed": False,
                "expected": test_case.get("expected", "")[:300],
                "actual": f"Error: {exc}"[:300]}


# ═══════════════════════════════════════════════════════════
#  PYTHON EXECUTOR — subprocess with strict timeout
# ═══════════════════════════════════════════════════════════

def execute_python(user_code: str, test_cases: list = None,
                   expected_output: str = None) -> dict:
    """Execute Python code in a subprocess with timeout."""
    results = {
        "passed": False,
        "test_results": [],
        "execution_time_ms": 0,
        "actual_output": "",
        "error": None,
    }

    if not user_code.strip():
        results["error"] = "No code submitted."
        return results

    # Build test harness
    test_script = _build_python_test_script(user_code, test_cases, expected_output)

    start = time.perf_counter()
    try:
        proc = subprocess.run(
            [sys.executable, "-c", test_script],
            capture_output=True,
            text=True,
            timeout=PYTHON_EXEC_TIMEOUT,
            cwd=str(Path(__file__).parent),
        )

        results["actual_output"] = proc.stdout[:2000]

        if proc.returncode != 0:
            results["error"] = proc.stderr[:1000]
            results["test_results"].append({
                "name": "execution",
                "passed": False,
                "expected": "No errors",
                "actual": proc.stderr[:300],
            })
        else:
            # Parse test results from stdout
            try:
                output_lines = proc.stdout.strip().splitlines()
                # Look for our JSON results marker
                for line in output_lines:
                    if line.startswith("__TEST_RESULTS__:"):
                        test_data = json.loads(line[17:])
                        results["test_results"] = test_data
                        break
                else:
                    # No structured results, check if output matches
                    if expected_output:
                        match = proc.stdout.strip() == expected_output.strip()
                        results["test_results"].append({
                            "name": "output_match",
                            "passed": match,
                            "expected": expected_output[:300],
                            "actual": proc.stdout.strip()[:300],
                        })
            except (json.JSONDecodeError, IndexError):
                pass

        if results["test_results"]:
            results["passed"] = all(t["passed"] for t in results["test_results"])

    except subprocess.TimeoutExpired:
        results["error"] = f"Execution timed out after {PYTHON_EXEC_TIMEOUT}s"
        results["test_results"].append({
            "name": "timeout", "passed": False,
            "expected": f"Complete within {PYTHON_EXEC_TIMEOUT}s",
            "actual": "Timed out",
        })
    except Exception as exc:
        results["error"] = str(exc)[:500]

    results["execution_time_ms"] = round((time.perf_counter() - start) * 1000, 1)
    return results


def _build_python_test_script(user_code: str, test_cases: list = None,
                               expected_output: str = None) -> str:
    """Build a test harness script that wraps user code."""
    parts = [
        "import json, sys",
        "",
        "# User code",
        user_code,
        "",
        "# Test harness",
        "test_results = []",
    ]

    if test_cases:
        for i, tc in enumerate(test_cases):
            name = tc.get("name", f"test_{i}")
            test_input = tc.get("input", "")
            expected = tc.get("expected", "")
            parts.append(f"""
try:
    result = {test_input}
    expected = {expected}
    passed = str(result) == str(expected) or result == expected
    test_results.append({{"name": {json.dumps(name)}, "passed": passed,
                          "expected": str(expected)[:300], "actual": str(result)[:300]}})
except Exception as e:
    test_results.append({{"name": {json.dumps(name)}, "passed": False,
                          "expected": {json.dumps(str(expected)[:300])}, "actual": str(e)[:300]}})
""")

    parts.append('print("__TEST_RESULTS__:" + json.dumps(test_results))')
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════
#  PYSPARK VALIDATOR — AST + regex pattern matching
# ═══════════════════════════════════════════════════════════

def validate_pyspark(user_code: str, required_patterns: list = None,
                     test_cases: list = None) -> dict:
    """Validate PySpark code using AST parsing and pattern matching."""
    results = {
        "passed": False,
        "test_results": [],
        "execution_time_ms": 0,
        "actual_output": "",
        "error": None,
        "patterns_found": [],
        "patterns_missing": [],
    }

    start = time.perf_counter()

    if not user_code.strip():
        results["error"] = "No code submitted."
        return results

    # 1. Syntax check via AST
    try:
        tree = ast.parse(user_code)
        results["test_results"].append({
            "name": "syntax_valid",
            "passed": True,
            "expected": "Valid Python syntax",
            "actual": "Parsed successfully",
        })
    except SyntaxError as e:
        results["error"] = f"Syntax error: {e}"
        results["test_results"].append({
            "name": "syntax_valid",
            "passed": False,
            "expected": "Valid Python syntax",
            "actual": str(e)[:300],
        })
        results["execution_time_ms"] = round((time.perf_counter() - start) * 1000, 1)
        return results

    # 2. Pattern matching for required PySpark APIs
    if required_patterns is None:
        # Auto-detect what patterns should be present based on common PySpark APIs
        required_patterns = _infer_pyspark_patterns(test_cases or [])

    for pattern in required_patterns:
        found = _check_pyspark_pattern(user_code, pattern)
        if found:
            results["patterns_found"].append(pattern)
            results["test_results"].append({
                "name": f"pattern_{pattern}",
                "passed": True,
                "expected": f"Uses {pattern}",
                "actual": "Found",
            })
        else:
            results["patterns_missing"].append(pattern)
            results["test_results"].append({
                "name": f"pattern_{pattern}",
                "passed": False,
                "expected": f"Uses {pattern}",
                "actual": "Not found in code",
            })

    # 3. Check for common anti-patterns
    anti_patterns = _check_pyspark_antipatterns(user_code)
    for ap in anti_patterns:
        results["test_results"].append({
            "name": f"antipattern_{ap['name']}",
            "passed": False,
            "expected": ap["suggestion"],
            "actual": ap["found"],
        })

    if results["test_results"]:
        results["passed"] = all(t["passed"] for t in results["test_results"])

    results["execution_time_ms"] = round((time.perf_counter() - start) * 1000, 1)
    return results


def _check_pyspark_pattern(code: str, pattern: str) -> bool:
    """Check if a PySpark pattern/API is used in the code."""
    pattern_regexes = {
        "groupBy": r"\.\s*groupBy\s*\(",
        "agg": r"\.\s*agg\s*\(",
        "filter": r"\.\s*filter\s*\(",
        "select": r"\.\s*select\s*\(",
        "withColumn": r"\.\s*withColumn\s*\(",
        "join": r"\.\s*join\s*\(",
        "broadcast": r"broadcast\s*\(|F\.broadcast\s*\(",
        "Window": r"Window\.|from\s+pyspark\.sql\.window\s+import",
        "partitionBy": r"\.\s*partitionBy\s*\(",
        "orderBy": r"\.\s*orderBy\s*\(|\.sort\s*\(",
        "repartition": r"\.\s*repartition\s*\(",
        "coalesce": r"\.\s*coalesce\s*\(",
        "udf": r"@udf|F\.udf|pandas_udf",
        "cache": r"\.\s*cache\s*\(|\.\s*persist\s*\(",
        "dropDuplicates": r"\.\s*dropDuplicates\s*\(|\.\s*drop_duplicates\s*\(",
        "fillna": r"\.\s*fillna\s*\(|\.\s*na\.fill\s*\(",
        "when": r"F\.when\s*\(|when\s*\(",
        "col": r"F\.col\s*\(|col\s*\(",
        "lit": r"F\.lit\s*\(|lit\s*\(",
        "Row": r"Row\s*\(",
        "StructType": r"StructType|StructField",
    }

    regex = pattern_regexes.get(pattern, re.escape(pattern))
    return bool(re.search(regex, code))


def _infer_pyspark_patterns(test_cases: list) -> list:
    """Infer required patterns from test case metadata."""
    patterns = []
    for tc in test_cases:
        if "required_patterns" in tc:
            patterns.extend(tc["required_patterns"])
    return list(set(patterns))


def _check_pyspark_antipatterns(code: str) -> list:
    """Detect common PySpark anti-patterns."""
    issues = []

    # Collecting to driver in a loop
    if re.search(r"\.collect\(\).*for\s", code, re.DOTALL):
        issues.append({
            "name": "collect_in_loop",
            "found": ".collect() used inside a loop",
            "suggestion": "Avoid collecting to driver in loops. Use DataFrame operations instead.",
        })

    # Python UDF when built-in functions would work
    if re.search(r"@udf|F\.udf", code) and not re.search(r"pandas_udf", code):
        issues.append({
            "name": "python_udf",
            "found": "Python UDF detected",
            "suggestion": "Consider using built-in PySpark functions (F.when, F.coalesce) for better performance.",
        })

    # Using .count() just to check emptiness
    if re.search(r"\.count\(\)\s*[>=!<]+\s*0", code):
        issues.append({
            "name": "count_for_empty",
            "found": ".count() used to check emptiness",
            "suggestion": "Use .head(1) or .isEmpty() instead of .count() for emptiness checks.",
        })

    return issues


# ═══════════════════════════════════════════════════════════
#  UNIFIED EXECUTOR
# ═══════════════════════════════════════════════════════════

def execute_code(user_code: str, category: str, exercise: dict) -> dict:
    """Execute code based on category."""
    sample_data = exercise.get("sample_data", "")
    expected_output = exercise.get("expected_output", "")
    test_cases = exercise.get("test_cases", [])
    if isinstance(test_cases, str):
        try:
            test_cases = json.loads(test_cases)
        except json.JSONDecodeError:
            test_cases = []

    if category == "sql":
        return execute_sql(user_code, sample_data, expected_output, test_cases)
    elif category == "python":
        return execute_python(user_code, test_cases, expected_output)
    elif category == "pyspark":
        required_patterns = []
        for tc in test_cases:
            if isinstance(tc, dict) and "required_patterns" in tc:
                required_patterns.extend(tc["required_patterns"])
        return validate_pyspark(user_code, required_patterns or None, test_cases)
    else:
        return {"passed": False, "error": f"Unknown category: {category}",
                "test_results": [], "execution_time_ms": 0}
