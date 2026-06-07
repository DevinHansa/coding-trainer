"""Application configuration for SDE Prep platform."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).parent / ".env")

# ── Gemini AI Settings ─────────────────────────────────────
GEMINI_API_KEYS = [
    k for k in [
        os.environ.get("GEMINI_API_KEY", ""),
        os.environ.get("GEMINI_API_KEY_2", ""),
        os.environ.get("GEMINI_API_KEY_3", ""),
        os.environ.get("GEMINI_API_KEY_4", ""),
    ] if k
]
GEMINI_API_KEY = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else ""
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

# ── Flask Settings ─────────────────────────────────────────
SECRET_KEY = os.environ.get("SECRET_KEY", "sde-prep-dev-key-2026")
DEBUG = os.environ.get("FLASK_DEBUG", "1") == "1"
PORT = int(os.environ.get("PORT", "5000"))

# ── Database ───────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "coding_trainer.db")

# ── Categories ─────────────────────────────────────────────
VALID_CATEGORIES = ("python", "sql", "pyspark")

# ── Training Settings ──────────────────────────────────────
MAX_HINTS_PER_EXERCISE = 3
EXERCISE_TIME_LIMIT_SECONDS = 1800  # 30 minutes

# ── Code Execution Sandbox ─────────────────────────────────
PYTHON_EXEC_TIMEOUT = 5       # seconds
SQL_EXEC_TIMEOUT = 5           # seconds
MAX_OUTPUT_ROWS = 500          # cap result rows for comparison

# ── Difficulty Levels ──────────────────────────────────────
DIFFICULTY_LEVELS = {
    1: "Foundations",
    2: "Intermediate",
    3: "Advanced",
    4: "Senior / Expert",
}

# ── Mastery Levels ─────────────────────────────────────────
MASTERY_LEVELS = {
    "novice": {"min_score": 0, "min_attempts": 0, "min_streak": 0},
    "learning": {"min_score": 0, "min_attempts": 1, "min_streak": 0},
    "competent": {"min_score": 50, "min_attempts": 3, "min_streak": 0},
    "proficient": {"min_score": 70, "min_attempts": 5, "min_streak": 2},
    "expert": {"min_score": 85, "min_attempts": 8, "min_streak": 3},
}

# ── Flow State Thresholds ──────────────────────────────────
FLOW_FAST_SOLVE_RATIO = 0.3   # if solved in < 30% of expected time → bump difficulty
FLOW_FAIL_THRESHOLD = 3       # 3+ consecutive fails → pivot to MCQ drill
FLOW_STREAK_BONUS = 3         # streak >= 3 → XP multiplier

# ── The Ladder — XP Thresholds ─────────────────────────────
LADDER_RANKS = {
    "associate_de": {"xp": 0, "label": "Associate DE", "icon": "🥉"},
    "mid_de": {"xp": 500, "label": "Mid-Level DE", "icon": "🥈"},
    "senior_de": {"xp": 1500, "label": "Senior DE", "icon": "🥇"},
    "staff_de": {"xp": 3500, "label": "Staff DE", "icon": "💎"},
    "principal_de": {"xp": 7000, "label": "Principal DE", "icon": "👑"},
}

# ── Valid Skill Tags (from skills.md — source of truth) ────
VALID_SKILL_TAGS = frozenset([
    # Python
    "py:data_structures", "py:comprehensions", "py:string_manipulation",
    "py:sorting", "py:filtering", "py:generators", "py:decorators",
    "py:error_handling", "py:big_o", "py:collections", "py:functional",
    "py:memory_management", "py:concurrency", "py:design_patterns",
    "py:testing", "py:type_hints", "py:custom_data_structures",
    "py:profiling", "py:metaprogramming", "py:edge_case_hardening",
    "py:packaging",
    # SQL
    "sql:joins", "sql:group_by", "sql:filtering", "sql:subquery",
    "sql:aggregation", "sql:window_functions", "sql:cte", "sql:lag_lead",
    "sql:date_functions", "sql:having", "sql:case_when", "sql:recursive_cte",
    "sql:query_optimization", "sql:execution_plans", "sql:set_operations",
    "sql:advanced_joins", "sql:null_semantics", "sql:complex_analytics",
    "sql:materialized_views", "sql:index_strategies", "sql:partitioning",
    "sql:data_modeling", "sql:pivot_unpivot",
    # PySpark
    "spark:dataframe_basics", "spark:transformations", "spark:aggregations",
    "spark:io", "spark:rdd_vs_df", "spark:column_operations", "spark:udf",
    "spark:joins", "spark:window_functions", "spark:broadcast_joins",
    "spark:partitioning", "spark:data_skew", "spark:caching",
    "spark:catalyst", "spark:medallion", "spark:dynamic_pipelines",
    "spark:streaming", "spark:performance", "spark:delta",
    # Gotchas
    "gotcha:silent_failures", "gotcha:integer_overflow", "gotcha:timezone_bugs",
    "gotcha:non_deterministic_order", "gotcha:schema_drift",
    "gotcha:duplicate_keys", "gotcha:encoding_corruption",
    "gotcha:empty_partition", "gotcha:cartesian_explosion",
    "gotcha:late_arriving_data",
])
