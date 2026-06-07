"""Seed exercise library — SQL, Python, PySpark for Senior DE prep.
Loads problems from sql_bank.py and py_bank.py, plus inline PySpark exercises."""
import json
from database import insert_exercise, get_db
from sql_bank import PROBLEMS as SQL_BANK
from py_bank import PROBLEMS as PY_BANK


# ── PySpark exercises (kept inline — small set) ────────────────────
PYSPARK_EXERCISES = [
    {
        "difficulty": 2, "title": "Filter and Select Columns",
        "topic": "dataframe_basics",
        "description": "Given a PySpark DataFrame `df` with columns: id, name, department, salary.\n\nWrite code to:\n1. Filter employees with salary > 80000\n2. Select only name and salary columns\n3. Return the result sorted by salary descending\n\nThe DataFrame is pre-loaded as `df`. Write your transformation and assign the result to `result`.",
        "sample_data": "from pyspark.sql import SparkSession\nspark = SparkSession.builder.master('local').getOrCreate()\ndf = spark.createDataFrame([(1,'Alice','Eng',90000),(2,'Bob','Mkt',75000),(3,'Carol','Eng',85000),(4,'Dan','Sales',95000)], ['id','name','department','salary'])",
        "expected_output": "Dan|95000\nAlice|90000\nCarol|85000",
        "solution": "result = df.filter(df.salary > 80000).select('name', 'salary').orderBy(df.salary.desc())",
        "tags": ["spark:dataframe_ops", "spark:filtering"],
        "hints": ["Use .filter() with a column condition", "Chain .select() after filter", "Use .orderBy(col.desc()) for descending sort"],
    },
    {
        "difficulty": 2, "title": "GroupBy Aggregation",
        "topic": "transformations",
        "description": "Given DataFrame `df` with columns: id, name, department, salary.\n\nCalculate the average salary per department.\nReturn columns: department, avg_salary (rounded to nearest integer).\nSort by department name ascending.\n\nAssign to `result`.",
        "sample_data": "from pyspark.sql import SparkSession\nfrom pyspark.sql import functions as F\nspark = SparkSession.builder.master('local').getOrCreate()\ndf = spark.createDataFrame([(1,'Alice','Eng',90000),(2,'Bob','Mkt',75000),(3,'Carol','Eng',85000),(4,'Dan','Mkt',80000)], ['id','name','department','salary'])",
        "expected_output": "Eng|87500\nMkt|77500",
        "solution": "from pyspark.sql import functions as F\nresult = df.groupBy('department').agg(F.round(F.avg('salary'), 0).cast('int').alias('avg_salary')).orderBy('department')",
        "tags": ["spark:dataframe_ops", "spark:aggregation"],
        "hints": ["Use .groupBy().agg()", "F.avg('salary') inside agg()", "Round and cast to int, then alias"],
    },
    {
        "difficulty": 3, "title": "Window Function: Rank Within Group",
        "topic": "window_functions",
        "description": "Given DataFrame `df` with columns: id, name, department, salary.\n\nFor each department, rank employees by salary (highest first).\nReturn: name, department, salary, rank.\nSort by department, then rank.\n\nAssign to `result`.",
        "sample_data": "from pyspark.sql import SparkSession\nfrom pyspark.sql import functions as F\nfrom pyspark.sql.window import Window\nspark = SparkSession.builder.master('local').getOrCreate()\ndf = spark.createDataFrame([(1,'Alice','Eng',90000),(2,'Bob','Eng',85000),(3,'Carol','Mkt',75000),(4,'Dan','Mkt',80000)], ['id','name','department','salary'])",
        "expected_output": "Alice|Eng|90000|1\nBob|Eng|85000|2\nDan|Mkt|80000|1\nCarol|Mkt|75000|2",
        "solution": "from pyspark.sql import functions as F\nfrom pyspark.sql.window import Window\nw = Window.partitionBy('department').orderBy(F.desc('salary'))\nresult = df.withColumn('rank', F.rank().over(w)).select('name','department','salary','rank').orderBy('department','rank')",
        "tags": ["spark:window_functions", "spark:dataframe_ops"],
        "hints": ["Create a Window spec with partitionBy and orderBy", "Use F.rank().over(window)", "orderBy department then rank at the end"],
    },
    {
        "difficulty": 3, "title": "Join and Deduplicate",
        "topic": "joins",
        "description": "Two DataFrames:\n- `orders`: order_id, customer_id, amount\n- `customers`: customer_id, name, region\n\nJoin them, then for each region find the customer with the highest single order.\nReturn: region, name, max_order_amount.\nSort by region.\n\nAssign to `result`.",
        "sample_data": "from pyspark.sql import SparkSession\nfrom pyspark.sql import functions as F\nfrom pyspark.sql.window import Window\nspark = SparkSession.builder.master('local').getOrCreate()\norders = spark.createDataFrame([(1,1,500),(2,1,300),(3,2,700),(4,3,400),(5,3,600)], ['order_id','customer_id','amount'])\ncustomers = spark.createDataFrame([(1,'Alice','East'),(2,'Bob','West'),(3,'Carol','East')], ['customer_id','name','region'])\ndf = orders  # primary reference",
        "expected_output": "East|Carol|600\nWest|Bob|700",
        "solution": "from pyspark.sql import functions as F\nfrom pyspark.sql.window import Window\njoined = orders.join(customers, 'customer_id')\nw = Window.partitionBy('region').orderBy(F.desc('amount'))\nresult = joined.withColumn('rn', F.row_number().over(w)).filter('rn = 1').select('region','name', F.col('amount').alias('max_order_amount')).orderBy('region')",
        "tags": ["spark:joins", "spark:window_functions", "spark:dataframe_ops"],
        "hints": ["Join orders with customers on customer_id", "Use Window + row_number to find top per region", "Filter where rn = 1"],
    },
]


def seed_database():
    """Top up the database with missing seed exercises."""
    conn = get_db()

    try:
        existing = {
            (row["category"], row["title"])
            for row in conn.execute("SELECT category, title FROM exercises").fetchall()
        }
    except Exception:
        existing = set()
    conn.close()

    print("Seeding exercise library...")
    count = 0

    # Seed SQL from sql_bank.py
    for ex in SQL_BANK:
        if ('sql', ex['title']) in existing:
            continue
        insert_exercise(
            category='sql', difficulty=ex['diff'], title=ex['title'],
            description=ex['description'], sample_data=ex['sample_data'],
            expected_output=ex['expected_output'], solution=ex['solution'],
            tags=ex['tags'], hints=ex['hints'], is_seed=1,
            test_cases=ex.get('test_cases', []),
            time_limit_seconds=ex.get('time_limit_seconds', 900),
            topic=ex.get('topic'),
        )
        count += 1

    # Seed Python from py_bank.py
    for ex in PY_BANK:
        if ('python', ex['title']) in existing:
            continue
        insert_exercise(
            category='python', difficulty=ex['diff'], title=ex['title'],
            description=ex['description'], sample_data=ex['sample_data'],
            expected_output=ex['expected_output'], solution=ex['solution'],
            tags=ex['tags'], hints=ex['hints'], is_seed=1,
            test_cases=ex.get('test_cases', []),
            time_limit_seconds=ex.get('time_limit_seconds', 900),
            topic=ex.get('topic'),
        )
        count += 1

    # Seed PySpark (inline)
    for ex in PYSPARK_EXERCISES:
        if ('pyspark', ex['title']) in existing:
            continue
        insert_exercise(
            category='pyspark', difficulty=ex['difficulty'], title=ex['title'],
            description=ex['description'], sample_data=ex['sample_data'],
            expected_output=ex['expected_output'], solution=ex['solution'],
            tags=ex['tags'], hints=ex['hints'], is_seed=1,
            test_cases=ex.get('test_cases', []),
            time_limit_seconds=ex.get('time_limit_seconds', 900),
            topic=ex.get('topic'),
        )
        count += 1

    print(f"Seeded {count} new exercises (total bank: {count + len(existing)}).")


if __name__ == '__main__':
    from database import init_db
    init_db()
    seed_database()
