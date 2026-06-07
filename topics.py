"""Canonical topic taxonomy for SQL and Python problem classification."""

TOPICS = {
    "sql": {
        "select_filtering": "SELECT / WHERE / Filtering",
        "order_limit_distinct": "ORDER BY / LIMIT / DISTINCT",
        "aggregations": "Aggregations (COUNT/SUM/AVG/MIN/MAX)",
        "group_by_having": "GROUP BY + HAVING",
        "joins": "JOINs (INNER/LEFT/RIGHT/FULL/SELF)",
        "subqueries_ctes": "Subqueries & CTEs",
        "window_functions": "Window Functions",
        "string_date_functions": "String / Date Functions",
        "case_when": "CASE WHEN / Conditional Aggregation",
        "set_operations": "Set Operations (UNION/INTERSECT/EXCEPT)",
        "scenario_pipeline": "Scenario / Pipeline-Style",
    },
    "python": {
        "strings": "Strings (parse, reverse, palindrome, anagram)",
        "lists_comprehensions": "Lists & List Comprehensions",
        "matrices_2d": "2D Lists / Matrices",
        "dicts_sets": "Dicts & Sets (counters, grouping, frequency)",
        "sorting_ranking": "Sorting & Ranking",
        "loops_control_flow": "Loops & Control Flow",
        "recursion": "Recursion",
        "data_structures": "Data Structures (stack, queue, linked list, heap)",
        "algorithms": "Algorithms (binary search, two-pointer, sliding window)",
        "big_o": "Big-O Reasoning",
        "scenario_etl": "Scenario / ETL-Style",
    },
    "pyspark": {
        "dataframe_basics": "DataFrame Basics",
        "transformations": "Transformations",
        "window_functions": "Window Functions",
        "joins": "Joins & Broadcast",
        "medallion": "Medallion Architecture",
    },
}


def get_topics_for_language(language: str) -> dict:
    """Get topic slugs and display names for a language."""
    return TOPICS.get(language, {})


def get_all_topic_labels() -> dict:
    """Get a flat dict of topic_slug -> display_name across all languages."""
    result = {}
    for lang_topics in TOPICS.values():
        result.update(lang_topics)
    return result
