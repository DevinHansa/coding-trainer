"""Import new problems from Refer/problems.json that don't already exist."""
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

from database import insert_exercise, get_db, init_db
from sql_bank import PROBLEMS as sql_bank
from py_bank import PROBLEMS as py_bank

# Topic slug mapping: Refer format -> our format
TOPIC_MAP = {
    "select-where": "select_filtering",
    "order-limit-distinct": "order_limit_distinct",
    "aggregations": "aggregations",
    "group-having": "group_by_having",
    "joins": "joins",
    "subqueries-ctes": "subqueries_ctes",
    "window-functions": "window_functions",
    "string-date": "string_date_functions",
    "case-when": "case_when",
    "set-ops": "set_operations",
    "scenario": "scenario_pipeline",
    "strings": "strings",
    "lists": "lists_comprehensions",
    "matrices": "matrices_2d",
    "dicts-sets": "dicts_sets",
    "sorting-ranking": "sorting_ranking",
    "loops": "loops_control_flow",
    "recursion": "recursion",
    "data-structures": "data_structures",
    "algorithms": "algorithms",
    "big-o": "big_o",
}

TAG_MAP = {
    "select-where": ["sql:filtering"],
    "order-limit-distinct": ["sql:filtering"],
    "aggregations": ["sql:aggregation"],
    "group-having": ["sql:group_by", "sql:having"],
    "joins": ["sql:joins"],
    "subqueries-ctes": ["sql:subquery", "sql:cte"],
    "window-functions": ["sql:window_functions"],
    "string-date": ["sql:date_functions"],
    "case-when": ["sql:case_when"],
    "set-ops": ["sql:set_operations"],
    "scenario": ["sql:complex_analytics"],
    "strings": ["py:string_manipulation"],
    "lists": ["py:comprehensions"],
    "matrices": ["py:data_structures"],
    "dicts-sets": ["py:data_structures", "py:collections"],
    "sorting-ranking": ["py:sorting"],
    "loops": ["py:data_structures"],
    "recursion": ["py:data_structures"],
    "data-structures": ["py:custom_data_structures"],
    "algorithms": ["py:big_o", "py:data_structures"],
    "big-o": ["py:big_o"],
}


def convert_expected(expected):
    """Convert [[1,'Alice'],[3,'Carol']] to '1|Alice\\n3|Carol'"""
    if not expected:
        return ""
    lines = []
    for row in expected:
        if isinstance(row, list):
            lines.append("|".join(str(v) if v is not None else "None" for v in row))
        else:
            lines.append(str(row))
    return "\n".join(lines)


def convert_python_tests(fn_name, tests):
    """Convert [[[args], expected], ...] to test_cases format."""
    if not tests or not fn_name:
        return []
    result = []
    for i, test in enumerate(tests):
        if len(test) < 2:
            continue
        args = test[0]
        expected = test[1]
        if not isinstance(args, list):
            args = [args]
        args_str = ", ".join(repr(a) for a in args)
        result.append({
            "name": f"test_{i}",
            "input": f"{fn_name}({args_str})",
            "expected": repr(expected),
        })
    return result


def main():
    init_db()

    # Load existing titles
    existing_titles = {p['title'] for p in sql_bank + py_bank}
    conn = get_db()
    try:
        db_titles = {
            row["title"]
            for row in conn.execute("SELECT title FROM exercises").fetchall()
        }
    except Exception:
        db_titles = set()
    conn.close()
    all_existing = existing_titles | db_titles

    # Load Refer problems
    with open("Refer/problems.json", "r", encoding="utf-8") as f:
        refer_data = json.load(f)

    count = 0
    for p in refer_data:
        if p["title"] in all_existing:
            continue

        lang = p["lang"]
        topic = TOPIC_MAP.get(p["topic"], p["topic"])
        tags = TAG_MAP.get(p["topic"], [])

        if lang == "sql":
            expected_output = convert_expected(p.get("expected", []))
            test_cases = []
            sample_data = p.get("schema", "")
        else:
            expected_output = ""
            test_cases = convert_python_tests(p.get("fn", ""), p.get("tests", []))
            sample_data = p.get("prompt", "")

        insert_exercise(
            category=lang,
            difficulty=p["diff"],
            title=p["title"],
            description=p.get("prompt", ""),
            sample_data=sample_data or "",
            expected_output=expected_output,
            solution=p.get("solution", ""),
            tags=tags,
            hints=p.get("hints", []),
            is_seed=1,
            test_cases=test_cases,
            time_limit_seconds=900,
            topic=topic,
        )
        count += 1
        print(f"  + [{lang}] {p['title']}")

    print(f"\nImported {count} new problems from Refer/problems.json")

    # Show total
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM exercises").fetchone()[0]
    conn.close()
    print(f"Total exercises in database: {total}")


if __name__ == "__main__":
    main()
