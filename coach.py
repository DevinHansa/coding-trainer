"""Gemini AI coaching engine with structured JSON outputs and taxonomy-bound evaluation."""
import json
import re
import ast
import logging
from typing import Any, Optional
from pathlib import Path

from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_API_KEYS, GEMINI_MODEL, VALID_SKILL_TAGS

# ── Gemini Client with Key Rotation ────────────────────────
_clients = {}       # key -> client cache
_current_key_idx = 0


def _get_client(key_index=None):
    """Get a Gemini client, optionally for a specific key index."""
    global _current_key_idx
    if not GEMINI_API_KEYS:
        return None
    idx = key_index if key_index is not None else _current_key_idx
    idx = idx % len(GEMINI_API_KEYS)
    key = GEMINI_API_KEYS[idx]
    if key not in _clients:
        _clients[key] = genai.Client(api_key=key)
    return _clients[key]


def _rotate_key():
    """Move to the next API key."""
    global _current_key_idx
    _current_key_idx = (_current_key_idx + 1) % len(GEMINI_API_KEYS)


def _is_quota_error(exc):
    """Check if an exception is a quota/rate-limit error."""
    err = str(exc)
    return "429" in err or "RESOURCE_EXHAUSTED" in err


def check_gemini_connection():
    """Check if any Gemini API key is reachable."""
    if not GEMINI_API_KEYS:
        return {"connected": False, "error": "No API key configured."}

    for i in range(len(GEMINI_API_KEYS)):
        client = _get_client(i)
        try:
            client.models.generate_content(
                model=GEMINI_MODEL,
                contents="Reply with exactly: {\"status\": \"ok\"}",
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    max_output_tokens=32,
                    temperature=0.0,
                ),
            )
            global _current_key_idx
            _current_key_idx = i  # Use this working key going forward
            return {"connected": True, "model": GEMINI_MODEL,
                    "active_key": i + 1, "total_keys": len(GEMINI_API_KEYS)}
        except Exception as exc:
            if _is_quota_error(exc):
                continue  # Try next key
            return {"connected": False, "error": str(exc)[:200]}

    # All keys exhausted
    return {"connected": True, "model": GEMINI_MODEL, "throttled": True,
            "warning": f"All {len(GEMINI_API_KEYS)} keys quota-limited. Requests may be delayed."}


# ── Core Gemini Call with Exponential Backoff + Key Rotation ──

log = logging.getLogger("sde_prep.coach")


class _QuotaExhausted(Exception):
    """Raised when a Gemini key hits 429, triggering tenacity retry."""
    pass


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(_QuotaExhausted),
    reraise=True,
)
def _gemini_request(client, prompt, config):
    """Single Gemini API call with exponential backoff on quota errors."""
    try:
        return client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=config,
        )
    except Exception as exc:
        if _is_quota_error(exc):
            log.warning("Gemini 429 — backing off (key idx %d)...", _current_key_idx)
            raise _QuotaExhausted(str(exc)) from exc
        raise  # Non-quota errors propagate immediately


def _call_gemini(prompt: str, *, temperature: float = 0.3,
                 max_tokens: int = 2048, json_mode: bool = True) -> dict:
    """Call Gemini with exponential backoff per key + automatic key rotation."""
    if not GEMINI_API_KEYS:
        return {"ok": False, "error": "Gemini API key not configured."}

    last_error = None
    for key_attempt in range(len(GEMINI_API_KEYS)):
        client = _get_client()
        try:
            config = types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            )
            if json_mode:
                config.response_mime_type = "application/json"

            response = _gemini_request(client, prompt, config)
            text = response.text or ""
            if json_mode:
                try:
                    data = json.loads(text)
                    return {"ok": True, "data": data}
                except json.JSONDecodeError:
                    match = re.search(r"\{.*\}", text, re.DOTALL)
                    if match:
                        try:
                            data = json.loads(match.group(0))
                            return {"ok": True, "data": data}
                        except json.JSONDecodeError:
                            pass
                    return {"ok": False, "error": "Invalid JSON from Gemini", "raw": text[:500]}
            return {"ok": True, "text": text}

        except _QuotaExhausted as exc:
            # Tenacity exhausted all 3 retries for this key — rotate to next
            last_error = str(exc)
            log.warning("Key %d exhausted after retries, rotating...", _current_key_idx + 1)
            if key_attempt < len(GEMINI_API_KEYS) - 1:
                _rotate_key()
                continue
        except Exception as exc:
            last_error = str(exc)
            return {"ok": False, "error": last_error[:300]}

    return {"ok": False, "error": f"All {len(GEMINI_API_KEYS)} keys exhausted after backoff: {(last_error or '')[:200]}"}


# ── Taxonomy Validation ────────────────────────────────────
def _validate_tags(tags: list) -> list:
    """Filter tags to only those in skills.md taxonomy."""
    return [t for t in tags if t in VALID_SKILL_TAGS]


def _coerce_tags(raw_tags: list, category: str) -> list:
    """Attempt to map raw tags to valid taxonomy tags."""
    prefix_map = {"python": "py:", "sql": "sql:", "pyspark": "spark:"}
    prefix = prefix_map.get(category, "")
    result = []
    for tag in raw_tags:
        if tag in VALID_SKILL_TAGS:
            result.append(tag)
        elif f"{prefix}{tag}" in VALID_SKILL_TAGS:
            result.append(f"{prefix}{tag}")
        else:
            # Try fuzzy: joins -> sql:joins
            for valid in VALID_SKILL_TAGS:
                if valid.endswith(f":{tag}"):
                    result.append(valid)
                    break
    return result or [f"{prefix}{'data_structures' if category == 'python' else 'joins' if category == 'sql' else 'dataframe_basics'}"]


# ── Exercise Generation ───────────────────────────────────
def generate_exercise(category: str, difficulty: int,
                      weak_tags: list = None, user_profile: dict = None) -> dict:
    """Generate a Senior DE exercise with Gemini."""
    weak_context = ""
    if weak_tags:
        valid_weak = _validate_tags(weak_tags)
        if valid_weak:
            weak_context = f"\nThe student struggles with: {', '.join(valid_weak)}. Target these concepts.\n"

    profile_context = ""
    if user_profile:
        profile_context = f"\nStudent profile: {json.dumps(user_profile, default=str)[:800]}\n"

    category_desc = {
        "sql": "an Advanced SQL exercise (PostgreSQL-compatible). Include CREATE TABLE + INSERT statements as sample_data.",
        "python": "a Pure Python data engineering exercise. No ML. Focus on data structures, optimization, edge cases.",
        "pyspark": "a PySpark exercise. Include the expected DataFrame transformations. Test real Spark API knowledge.",
    }

    diff_desc = {
        1: "Foundations — single concept, confidence building.",
        2: "Intermediate — combine two concepts, practical scenario.",
        3: "Advanced — three+ concepts, real-world complexity.",
        4: "Senior/Expert — production scenario with edge cases and gotchas.",
    }

    prompt = f"""You are a Senior Data Engineer interview coach.

Generate one {category.upper()} exercise for a Senior DE candidate.
Difficulty: Level {difficulty} — {diff_desc.get(difficulty, diff_desc[2])}
{weak_context}{profile_context}
{category_desc.get(category, category_desc['python'])}

The exercise must test REAL engineering skill, not trivia. Include edge cases.

Return valid JSON with these exact keys:
{{
  "title": "Short descriptive title",
  "description": "Detailed problem statement with business context",
  "sample_data": "SQL DDL+DML or Python input data or PySpark schema",
  "expected_output": "Exact expected output",
  "solution": "Complete reference solution",
  "tags": ["tag1", "tag2"],
  "hints": ["hint1", "hint2", "hint3"],
  "test_cases": [
    {{"name": "basic", "input": "...", "expected": "..."}},
    {{"name": "edge_case", "input": "...", "expected": "..."}}
  ],
  "time_limit_seconds": 900
}}

Tags must be from this list: {json.dumps(sorted([t for t in VALID_SKILL_TAGS if t.startswith(('py:', 'sql:', 'spark:', 'gotcha:'))]))}
"""

    response = _call_gemini(prompt, temperature=0.5, max_tokens=3000)
    if not response["ok"]:
        return _fallback_exercise(category, difficulty, weak_tags)

    result = response["data"]
    required = ["title", "description", "solution", "tags"]
    if not all(result.get(f) for f in required):
        return _fallback_exercise(category, difficulty, weak_tags)

    # Enforce taxonomy
    result["tags"] = _coerce_tags(result.get("tags", []), category)
    result["hints"] = (result.get("hints") or [])[:3]
    result["test_cases"] = result.get("test_cases") or []
    result["time_limit_seconds"] = result.get("time_limit_seconds", 900)
    return result


# ── Submission Evaluation ─────────────────────────────────
def evaluate_submission(problem_description: str, user_code: str,
                        category: str, logical_steps: str = None,
                        execution_result: dict = None,
                        user_profile: dict = None) -> dict:
    """Evaluate code at Senior DE level with structured JSON output."""
    exec_context = ""
    if execution_result:
        passed = execution_result.get("passed", False)
        exec_context = f"""
EXECUTION RESULTS (programmatic):
- Passed all tests: {passed}
- Test details: {json.dumps(execution_result.get('test_results', [])[:5], default=str)}
- Execution time: {execution_result.get('execution_time_ms', 'N/A')}ms
"""

    steps_context = ""
    if logical_steps:
        steps_context = f"\nStudent's planning notes:\n{logical_steps[:500]}\n"

    profile_context = ""
    if user_profile:
        profile_context = f"\nStudent weakness history: {json.dumps(user_profile, default=str)[:500]}\n"

    prompt = f"""You are a Senior Data Engineer interview evaluator. Be strict but constructive.

PROBLEM:
{problem_description[:1500]}

STUDENT'S {category.upper()} CODE:
```
{user_code[:3000]}
```
{steps_context}{exec_context}{profile_context}

Evaluate for SENIOR-LEVEL quality:
1. Correctness (does it solve the problem?)
2. Efficiency (Big O, unnecessary scans, redundant operations)
3. Edge case handling (nulls, empty inputs, duplicates, overflow)
4. Idiomatic style (Pythonic patterns, proper SQL constructs, Spark best practices)
5. Production readiness (error handling, maintainability)

Return valid JSON:
{{
  "score": 0-100,
  "works_correctly": true/false,
  "what_worked": "Specific praise for senior-level patterns used",
  "issues": [
    {{
      "issue": "Specific problem",
      "severity": "critical|major|minor",
      "what_they_wrote": "problematic snippet",
      "what_it_should_be": "corrected code",
      "explanation": "Why this matters at senior level"
    }}
  ],
  "efficiency_notes": "Big O analysis and optimization suggestions",
  "detected_weaknesses": ["tag1", "tag2"],
  "overall_feedback": "Constructive summary",
  "concepts_demonstrated": ["tag1", "tag2"]
}}

detected_weaknesses and concepts_demonstrated must use tags from: {json.dumps(sorted([t for t in VALID_SKILL_TAGS]))}
"""

    response = _call_gemini(prompt, temperature=0.2, max_tokens=2000)
    if not response["ok"]:
        return _fallback_evaluation(user_code, category, response.get("error"), execution_result)

    result = response["data"]
    # Enforce taxonomy on detected weaknesses
    result["detected_weaknesses"] = _validate_tags(result.get("detected_weaknesses", []))
    result["concepts_demonstrated"] = _validate_tags(result.get("concepts_demonstrated", []))
    result["score"] = max(0, min(100, int(result.get("score", 0))))
    result["issues"] = result.get("issues", [])
    result["works_correctly"] = bool(result.get("works_correctly", False))
    return result


# ── Weakness Detection ────────────────────────────────────
def detect_weakness(user_code: str, category: str,
                    problem_description: str, score: int) -> list:
    """Detect specific conceptual weaknesses, bound to skills.md taxonomy."""
    if score >= 80:
        return []

    prefix_map = {"python": "py:", "sql": "sql:", "pyspark": "spark:"}
    prefix = prefix_map.get(category, "")
    relevant_tags = sorted([t for t in VALID_SKILL_TAGS if t.startswith(prefix) or t.startswith("gotcha:")])

    prompt = f"""Analyze this {category.upper()} submission for specific conceptual weaknesses.

Problem: {problem_description[:800]}
Code: {user_code[:2000]}
Score: {score}/100

Identify 1-3 specific weak concepts from ONLY this list:
{json.dumps(relevant_tags)}

Return JSON: {{"weaknesses": ["tag1", "tag2"]}}
"""
    response = _call_gemini(prompt, temperature=0.1, max_tokens=200)
    if not response["ok"]:
        return []
    raw = response["data"].get("weaknesses", [])
    return _validate_tags(raw)


# ── MCQ Drill Generation ─────────────────────────────────
def generate_mcq_drill(weakness_tag: str, category: str) -> dict:
    """Generate a targeted MCQ drill for a specific weakness."""
    prompt = f"""Generate a multiple-choice question targeting this specific concept: {weakness_tag}
Category: {category.upper()}
Level: Senior Data Engineer

The question must test DEEP understanding, not surface syntax.

Return JSON:
{{
  "question": "The question text with code context if needed",
  "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
  "correct_index": 0,
  "explanation": "Detailed explanation of why the answer is correct and others are wrong",
  "concept_tag": "{weakness_tag}"
}}
"""
    response = _call_gemini(prompt, temperature=0.4, max_tokens=1200)
    if not response["ok"]:
        return _fallback_mcq(weakness_tag)
    result = response["data"]
    result["concept_tag"] = weakness_tag  # Force taxonomy binding
    return result


# ── Hint Generation ───────────────────────────────────────
def give_hint(problem_description: str, user_code: str,
              hint_level: int, category: str) -> dict:
    """Provide a progressive hint via Gemini."""
    level_instructions = {
        1: "Give a conceptual nudge only. No code. One or two sentences.",
        2: "Name the specific construct or pattern needed. No full answer.",
        3: "Provide a code skeleton with blanks. Do NOT give the complete solution.",
    }

    prompt = f"""You are a Senior DE coach giving hint {hint_level}/3 for a {category.upper()} problem.

PROBLEM:
{problem_description[:1000]}

CURRENT CODE:
```
{user_code[:1500]}
```

{level_instructions.get(hint_level, level_instructions[1])}

Return JSON:
{{
  "hint": "The hint text",
  "encouragement": "Short encouraging message"
}}
"""
    response = _call_gemini(prompt, temperature=0.3, max_tokens=500)
    if not response["ok"]:
        return _fallback_hint(category, hint_level)
    result = response["data"]
    return {
        "hint": result.get("hint", "Think about the data flow step by step."),
        "encouragement": result.get("encouragement", "You're building real engineering skill."),
    }


# ── Fallbacks ─────────────────────────────────────────────
def _fallback_exercise(category: str, difficulty: int, weak_tags: list = None) -> dict:
    """Return a curated fallback exercise when Gemini is unavailable."""
    if category == "sql":
        return {
            "title": "Latest Approved Application Per Candidate",
            "description": (
                "Write a query returning one row per candidate with at least one "
                "approved application in the last 90 days. Return: candidate_id, "
                "candidate_name, latest_approved_job_id, latest_approved_at, "
                "total_applications_last_90_days."
            ),
            "sample_data": (
                "CREATE TABLE candidates (candidate_id INT, candidate_name VARCHAR(100));\n"
                "CREATE TABLE applications (application_id INT, candidate_id INT, "
                "job_id INT, status VARCHAR(20), applied_at TIMESTAMP);"
            ),
            "expected_output": "candidate_id | candidate_name | latest_approved_job_id | latest_approved_at | total_applications_last_90_days",
            "solution": "WITH recent AS (SELECT * FROM applications WHERE applied_at >= CURRENT_DATE - INTERVAL '90 day') SELECT ...",
            "tags": _coerce_tags(["cte", "window_functions"], category),
            "hints": ["Isolate last 90 days in a CTE.", "Use ROW_NUMBER() to rank approved apps.", "JOIN back for total counts."],
            "test_cases": [],
            "fallback_used": True,
        }
    elif category == "pyspark":
        return {
            "title": "Customer Purchase Aggregation with PySpark",
            "description": (
                "Given a DataFrame of purchase events, compute per-customer: "
                "total_spend, transaction_count, and latest_purchase_date. "
                "Filter out null amounts. Use DataFrame API (no RDDs)."
            ),
            "sample_data": "schema: customer_id INT, amount DOUBLE, purchase_date DATE",
            "expected_output": "DataFrame with customer_id, total_spend, transaction_count, latest_purchase_date",
            "solution": "df.filter(F.col('amount').isNotNull()).groupBy('customer_id').agg(...)",
            "tags": _coerce_tags(["aggregations", "transformations"], category),
            "hints": ["Start with filter to remove nulls.", "Use groupBy + agg with multiple aggregation functions.", "F.max for latest date."],
            "test_cases": [],
            "fallback_used": True,
        }
    else:
        return {
            "title": "Build Customer Purchase Summary",
            "description": (
                "Write build_customer_summary(events) that returns a list of dicts "
                "with customer_id, latest_purchase_at, total_valid_amount, unique_product_count. "
                "Ignore rows with missing/zero amounts. Deduplicate by (customer_id, product_id, purchased_at)."
            ),
            "sample_data": "events = [{'customer_id': 1, 'product_id': 'A', 'purchased_at': '2026-04-01', 'amount': 50}, ...]",
            "expected_output": "[{'customer_id': 1, ...}]",
            "solution": "def build_customer_summary(events): seen = set(); ...",
            "tags": _coerce_tags(["data_structures", "sorting"], category),
            "hints": ["Filter invalid rows first.", "Use set for deduplication.", "Track products in a set, convert to count at end."],
            "test_cases": [],
            "fallback_used": True,
        }


def _fallback_evaluation(user_code: str, category: str, error_msg: str = None,
                          execution_result: dict = None) -> dict:
    """Smart fallback evaluation using programmatic execution results."""
    code = (user_code or "").strip()
    exec_r = execution_result or {}
    test_results = exec_r.get("test_results", [])
    tests_passed = sum(1 for t in test_results if t.get("passed")) if test_results else 0
    tests_total = len(test_results) if test_results else 0
    all_passed = exec_r.get("passed", False)
    has_error = bool(exec_r.get("error"))

    # Score from execution results
    if not code:
        score = 0
    elif all_passed and tests_total > 0:
        score = 85  # Passed all tests — solid score even without AI
    elif tests_total > 0:
        score = max(10, int((tests_passed / tests_total) * 80))
    elif has_error:
        score = 15
    else:
        score = 40  # Code exists but no tests to run

    # Build issues from failed tests
    issues = []
    if not code:
        issues.append({"issue": "No code submitted", "severity": "critical",
                        "what_they_wrote": "", "what_it_should_be": "Write a solution.",
                        "explanation": "Start with the smallest working version."})
    if has_error:
        issues.append({"issue": "Runtime error", "severity": "critical",
                        "what_they_wrote": exec_r.get("error", "")[:200],
                        "what_it_should_be": "Code should execute without errors.",
                        "explanation": "Fix the error and try again."})
    for t in test_results:
        if not t.get("passed"):
            issues.append({"issue": f"Test '{t.get('name', 'test')}' failed",
                            "severity": "major",
                            "what_they_wrote": str(t.get("actual", ""))[:200],
                            "what_it_should_be": str(t.get("expected", ""))[:200],
                            "explanation": "Your output doesn't match the expected result."})

    # Build feedback message
    if all_passed and tests_total > 0:
        what_worked = f"All {tests_total} tests passed! Your code produces correct output."
        feedback = ("Tests passed. AI coach is temporarily unavailable for detailed efficiency analysis. "
                    "Your code is functionally correct — well done!")
    elif tests_total > 0:
        what_worked = f"{tests_passed}/{tests_total} tests passed." if tests_passed > 0 else ""
        feedback = (f"{tests_passed}/{tests_total} tests passed. "
                    f"Review the failed test cases above and fix the issues.")
    elif has_error:
        what_worked = ""
        feedback = f"Your code has an error: {exec_r.get('error', '')[:150]}. Fix and retry."
    else:
        what_worked = "You made an attempt." if code else ""
        feedback = "Code submitted. AI coach is temporarily unavailable — try again shortly."

    # PySpark pattern feedback
    if exec_r.get("patterns_found"):
        what_worked += f" Used correct patterns: {', '.join(exec_r['patterns_found'])}."
    if exec_r.get("patterns_missing"):
        for p in exec_r["patterns_missing"]:
            issues.append({"issue": f"Missing required pattern: {p}", "severity": "major",
                            "what_they_wrote": "Pattern not found in code",
                            "what_it_should_be": f"Use {p}() in your solution",
                            "explanation": f"The exercise requires using {p}."})

    return {
        "score": score,
        "works_correctly": all_passed,
        "what_worked": what_worked,
        "issues": issues,
        "efficiency_notes": f"Execution time: {exec_r.get('execution_time_ms', 'N/A')}ms" if exec_r.get('execution_time_ms') else "",
        "detected_weaknesses": [],
        "overall_feedback": feedback,
        "concepts_demonstrated": [],
        "fallback_used": True,
    }


def _fallback_hint(category: str, hint_level: int) -> dict:
    """Return a fallback hint when Gemini is unavailable."""
    hints = {
        1: "Think about the intermediate data structure you need before the final output.",
        2: "Break the problem into stages: input → transform → aggregate → output.",
        3: "Start with a skeleton: define the function signature and return type first.",
    }
    return {
        "hint": hints.get(hint_level, hints[1]),
        "encouragement": "Keep the next step small. You're building real skill.",
        "fallback_used": True,
    }


def _fallback_mcq(weakness_tag: str) -> dict:
    """Return a fallback MCQ when Gemini is unavailable."""
    return {
        "question": f"Which of the following best describes a senior-level approach to {weakness_tag.split(':')[-1].replace('_', ' ')}?",
        "options": [
            "A) Use the simplest approach that works",
            "B) Optimize for readability first, then performance",
            "C) Consider edge cases, performance, and maintainability together",
            "D) Always use the most complex solution to show expertise",
        ],
        "correct_index": 2,
        "explanation": "Senior engineers balance correctness, performance, edge cases, and maintainability.",
        "concept_tag": weakness_tag,
        "fallback_used": True,
    }
