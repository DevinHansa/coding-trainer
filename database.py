"""Database layer for the SDE Prep platform — SQLite with full schema."""
import sqlite3
import json
from datetime import datetime
from config import DB_PATH, VALID_SKILL_TAGS, MASTERY_LEVELS


def get_db():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize or migrate the database schema."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL CHECK(category IN ('sql', 'python', 'pyspark')),
            difficulty INTEGER NOT NULL CHECK(difficulty BETWEEN 1 AND 5),
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            sample_data TEXT,
            expected_output TEXT,
            solution TEXT,
            tags TEXT NOT NULL,
            hints TEXT,
            test_cases TEXT DEFAULT '[]',
            time_limit_seconds INTEGER DEFAULT 900,
            topic TEXT,
            is_seed INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_id INTEGER NOT NULL,
            user_code TEXT NOT NULL,
            logical_steps TEXT,
            score INTEGER DEFAULT 0 CHECK(score BETWEEN 0 AND 100),
            hints_used INTEGER DEFAULT 0,
            time_spent_seconds INTEGER DEFAULT 0,
            feedback TEXT,
            execution_result TEXT,
            weakness_detected TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (exercise_id) REFERENCES exercises(id)
        );

        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concept_tag TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL CHECK(category IN ('sql', 'python', 'pyspark')),
            attempts_count INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            current_streak INTEGER DEFAULT 0,
            best_streak INTEGER DEFAULT 0,
            difficulty_level INTEGER DEFAULT 1,
            avg_score REAL DEFAULT 0,
            mastery_level TEXT DEFAULT 'novice',
            total_time_spent INTEGER DEFAULT 0,
            last_practiced TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS weakness_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concept_tag TEXT NOT NULL,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            exercise_id INTEGER,
            drill_passed INTEGER DEFAULT 0,
            remediated_at TIMESTAMP,
            FOREIGN KEY (exercise_id) REFERENCES exercises(id)
        );

        CREATE TABLE IF NOT EXISTS flow_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            current_difficulty INTEGER DEFAULT 1,
            consecutive_passes INTEGER DEFAULT 0,
            consecutive_fails INTEGER DEFAULT 0,
            total_xp INTEGER DEFAULT 0,
            current_rank TEXT DEFAULT 'associate_de',
            avg_solve_time_seconds REAL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP,
            exercises_attempted INTEGER DEFAULT 0,
            exercises_passed INTEGER DEFAULT 0,
            avg_score REAL DEFAULT 0,
            focus_areas TEXT,
            notes TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_attempts_exercise ON attempts(exercise_id);
        CREATE INDEX IF NOT EXISTS idx_progress_tag ON progress(concept_tag);
        CREATE INDEX IF NOT EXISTS idx_progress_category ON progress(category);
        CREATE INDEX IF NOT EXISTS idx_exercises_category ON exercises(category, difficulty);
        CREATE INDEX IF NOT EXISTS idx_exercises_topic ON exercises(category, topic, difficulty);
        CREATE INDEX IF NOT EXISTS idx_weakness_tag ON weakness_log(concept_tag);
    """)

    # Migration: add new columns if upgrading from old schema
    _migrate_columns(conn)

    # Ensure flow_state has initial row
    existing = conn.execute("SELECT COUNT(*) FROM flow_state").fetchone()[0]
    if existing == 0:
        conn.execute("INSERT INTO flow_state (category) VALUES (NULL)")

    conn.commit()
    conn.close()


def _migrate_columns(conn):
    """Add columns that may be missing from older schemas."""
    migrations = [
        ("exercises", "test_cases", "TEXT DEFAULT '[]'"),
        ("exercises", "time_limit_seconds", "INTEGER DEFAULT 900"),
        ("exercises", "topic", "TEXT"),
        ("attempts", "execution_result", "TEXT"),
        ("attempts", "weakness_detected", "TEXT"),
        ("progress", "mastery_level", "TEXT DEFAULT 'novice'"),
        ("progress", "total_time_spent", "INTEGER DEFAULT 0"),
    ]
    for table, column, col_type in migrations:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        except sqlite3.OperationalError:
            pass  # Column already exists

    # Migrate category constraint: allow 'pyspark'
    # SQLite can't alter CHECK constraints, but new rows will work.
    # Old rows with only 'sql'/'python' are fine.


# ── Exercise CRUD ──────────────────────────────────────────

def get_exercise(exercise_id):
    """Get a single exercise by ID."""
    conn = get_db()
    row = conn.execute("SELECT * FROM exercises WHERE id = ?", (exercise_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_exercises(category=None, difficulty=None, tags=None, topic=None, limit=20):
    """Get exercises with optional filters."""
    conn = get_db()
    query = "SELECT * FROM exercises WHERE 1=1"
    params = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if difficulty:
        query += " AND difficulty = ?"
        params.append(difficulty)
    if topic:
        query += " AND topic = ?"
        params.append(topic)
    if tags:
        for tag in tags:
            query += " AND tags LIKE ?"
            params.append(f"%{tag}%")
    query += " ORDER BY difficulty, id LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_exercise(category, difficulty, title, description, sample_data,
                     expected_output, solution, tags, hints, is_seed=0,
                     test_cases=None, time_limit_seconds=900, topic=None):
    """Insert a new exercise."""
    conn = get_db()
    tags_str = json.dumps(tags) if isinstance(tags, list) else tags
    hints_str = json.dumps(hints) if isinstance(hints, list) else hints
    tc_str = json.dumps(test_cases) if isinstance(test_cases, list) else (test_cases or "[]")
    cur = conn.execute("""
        INSERT INTO exercises (category, difficulty, title, description, sample_data,
                               expected_output, solution, tags, hints, is_seed,
                               test_cases, time_limit_seconds, topic)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (category, difficulty, title, description, sample_data,
          expected_output, solution, tags_str, hints_str, is_seed,
          tc_str, time_limit_seconds, topic))
    conn.commit()
    exercise_id = cur.lastrowid
    conn.close()
    return exercise_id


def count_exercises(category=None):
    """Count total exercises, optionally by category."""
    conn = get_db()
    if category:
        count = conn.execute("SELECT COUNT(*) FROM exercises WHERE category = ?", (category,)).fetchone()[0]
    else:
        count = conn.execute("SELECT COUNT(*) FROM exercises").fetchone()[0]
    conn.close()
    return count


# ── Attempt CRUD ───────────────────────────────────────────

def save_attempt(exercise_id, user_code, logical_steps, score, hints_used,
                  time_spent, feedback, execution_result=None,
                  weakness_detected=None):
    """Save an attempt and update progress."""
    conn = get_db()
    exec_str = json.dumps(execution_result) if isinstance(execution_result, dict) else execution_result
    weak_str = json.dumps(weakness_detected) if isinstance(weakness_detected, list) else weakness_detected

    conn.execute("""
        INSERT INTO attempts (exercise_id, user_code, logical_steps, score,
                              hints_used, time_spent_seconds, feedback,
                              execution_result, weakness_detected)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (exercise_id, user_code, logical_steps, score, hints_used,
          time_spent, feedback, exec_str, weak_str))

    # Update progress for each tag
    exercise = conn.execute("SELECT * FROM exercises WHERE id = ?", (exercise_id,)).fetchone()
    if exercise:
        tags = json.loads(exercise['tags']) if exercise['tags'] else []
        category = exercise['category']
        passed = score >= 70

        for tag in tags:
            concept = tag if ':' in tag else f"{category}:{tag}"
            _update_progress(conn, concept, category, score, passed, time_spent)

    # Update flow state
    _update_flow_state(conn, exercise['category'] if exercise else None, score, time_spent)

    # Log weaknesses
    if weakness_detected:
        weak_list = weakness_detected if isinstance(weakness_detected, list) else json.loads(weakness_detected or "[]")
        for tag in weak_list:
            if tag in VALID_SKILL_TAGS:
                conn.execute("""
                    INSERT INTO weakness_log (concept_tag, exercise_id)
                    VALUES (?, ?)
                """, (tag, exercise_id))

    conn.commit()
    conn.close()


def _update_progress(conn, concept, category, score, passed, time_spent):
    """Update progress for a single concept tag."""
    existing = conn.execute(
        "SELECT * FROM progress WHERE concept_tag = ?", (concept,)
    ).fetchone()

    if existing:
        new_count = existing['attempts_count'] + 1
        new_success = existing['success_count'] + (1 if passed else 0)
        new_streak = (existing['current_streak'] + 1) if passed else 0
        best_streak = max(existing['best_streak'], new_streak)
        new_avg = ((existing['avg_score'] * existing['attempts_count']) + score) / new_count
        total_time = existing['total_time_spent'] + time_spent
        mastery = _calculate_mastery(new_avg, new_count, new_streak)

        conn.execute("""
            UPDATE progress SET
                attempts_count = ?, success_count = ?, current_streak = ?,
                best_streak = ?, avg_score = ?, mastery_level = ?,
                total_time_spent = ?,
                last_practiced = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE concept_tag = ?
        """, (new_count, new_success, new_streak, best_streak,
              new_avg, mastery, total_time, concept))
    else:
        mastery = _calculate_mastery(score, 1, 1 if passed else 0)
        cat = category
        # Infer category from tag prefix
        if concept.startswith("py:"):
            cat = "python"
        elif concept.startswith("sql:"):
            cat = "sql"
        elif concept.startswith("spark:"):
            cat = "pyspark"
        elif concept.startswith("gotcha:"):
            cat = category  # Use exercise category

        conn.execute("""
            INSERT INTO progress (concept_tag, category, attempts_count, success_count,
                                  current_streak, best_streak, avg_score, mastery_level,
                                  total_time_spent, last_practiced)
            VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (concept, cat, 1 if passed else 0, 1 if passed else 0,
              1 if passed else 0, score, mastery, time_spent))


def _calculate_mastery(avg_score, attempts, streak):
    """Calculate mastery level based on performance metrics."""
    if attempts >= 8 and avg_score >= 85 and streak >= 3:
        return "expert"
    if attempts >= 5 and avg_score >= 70 and streak >= 2:
        return "proficient"
    if attempts >= 3 and avg_score >= 50:
        return "competent"
    if attempts >= 1:
        return "learning"
    return "novice"


def _update_flow_state(conn, category, score, time_spent):
    """Update the flow state tracker."""
    row = conn.execute("SELECT * FROM flow_state LIMIT 1").fetchone()
    if not row:
        return

    passed = score >= 70
    new_passes = (row['consecutive_passes'] + 1) if passed else 0
    new_fails = 0 if passed else (row['consecutive_fails'] + 1)

    # XP calculation
    xp_earned = 0
    if passed:
        xp_earned = score  # Base XP = score
        if new_passes >= 3:
            xp_earned = int(xp_earned * 1.5)  # Streak bonus

    total_xp = row['total_xp'] + xp_earned

    # Rank calculation
    from config import LADDER_RANKS
    current_rank = "associate_de"
    for rank_key, rank_info in sorted(LADDER_RANKS.items(), key=lambda x: x[1]['xp'], reverse=True):
        if total_xp >= rank_info['xp']:
            current_rank = rank_key
            break

    conn.execute("""
        UPDATE flow_state SET
            category = COALESCE(?, category),
            consecutive_passes = ?, consecutive_fails = ?,
            total_xp = ?, current_rank = ?,
            updated_at = CURRENT_TIMESTAMP
    """, (category, new_passes, new_fails, total_xp, current_rank))


def get_attempts_for_exercise(exercise_id, limit=10):
    """Get recent attempts for an exercise."""
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM attempts WHERE exercise_id = ?
        ORDER BY created_at DESC LIMIT ?
    """, (exercise_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Progress & Stats ───────────────────────────────────────

def get_all_progress():
    """Get all progress records."""
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM progress ORDER BY avg_score ASC, attempts_count DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_weak_concepts(category=None, limit=5):
    """Get weakest concepts with at least 1 attempt."""
    conn = get_db()
    query = """
        SELECT *, CAST(success_count AS REAL) / MAX(attempts_count, 1) as success_rate
        FROM progress WHERE attempts_count > 0
    """
    params = []
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY success_rate ASC, last_practiced ASC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_profile(category=None):
    """Build a user profile dict for Gemini context."""
    conn = get_db()

    # Overall stats
    total_attempts = conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
    avg_score_row = conn.execute("SELECT AVG(score) FROM attempts").fetchone()
    avg_score = round(avg_score_row[0], 1) if avg_score_row[0] else 0

    # Weak concepts
    weak = get_weak_concepts(category=category, limit=5)

    # Recent weaknesses
    recent_weak = conn.execute("""
        SELECT concept_tag, COUNT(*) as freq
        FROM weakness_log
        WHERE detected_at > datetime('now', '-7 days')
        GROUP BY concept_tag ORDER BY freq DESC LIMIT 5
    """).fetchall()

    # Mastery distribution
    mastery_dist = {}
    rows = conn.execute("SELECT mastery_level, COUNT(*) as cnt FROM progress GROUP BY mastery_level").fetchall()
    for r in rows:
        mastery_dist[r['mastery_level']] = r['cnt']

    conn.close()

    return {
        "total_attempts": total_attempts,
        "avg_score": avg_score,
        "weak_concepts": [w['concept_tag'] for w in weak],
        "recent_weaknesses": [dict(r) for r in recent_weak],
        "mastery_distribution": mastery_dist,
    }


def get_flow_state():
    """Get current flow state."""
    conn = get_db()
    row = conn.execute("SELECT * FROM flow_state LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else {
        "current_difficulty": 1, "consecutive_passes": 0,
        "consecutive_fails": 0, "total_xp": 0, "current_rank": "associate_de",
    }


def get_dashboard_stats():
    """Get comprehensive stats for the dashboard."""
    conn = get_db()
    stats = {}

    stats['total_exercises'] = conn.execute("SELECT COUNT(*) FROM exercises").fetchone()[0]
    stats['total_attempts'] = conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]

    row = conn.execute("SELECT AVG(score) FROM attempts").fetchone()
    stats['avg_score'] = round(row[0], 1) if row[0] else 0

    stats['today_attempts'] = conn.execute("""
        SELECT COUNT(*) FROM attempts WHERE DATE(created_at) = DATE('now')
    """).fetchone()[0]

    stats['current_streak'] = _calculate_day_streak(conn)

    # Category breakdown (including pyspark)
    for cat in ['sql', 'python', 'pyspark']:
        cat_row = conn.execute("""
            SELECT COUNT(*) as cnt, AVG(a.score) as avg
            FROM attempts a JOIN exercises e ON a.exercise_id = e.id
            WHERE e.category = ?
        """, (cat,)).fetchone()
        stats[f'{cat}_attempts'] = cat_row['cnt']
        stats[f'{cat}_avg'] = round(cat_row['avg'], 1) if cat_row['avg'] else 0

    stats['exercises_passed'] = conn.execute("""
        SELECT COUNT(DISTINCT exercise_id) FROM attempts WHERE score >= 70
    """).fetchone()[0]

    # Weak areas
    weak = conn.execute("""
        SELECT concept_tag, avg_score, mastery_level
        FROM progress WHERE attempts_count > 0
        ORDER BY avg_score ASC LIMIT 5
    """).fetchall()
    stats['weak_areas'] = [{'tag': w['concept_tag'], 'score': round(w['avg_score'], 1),
                             'mastery': w['mastery_level']} for w in weak]

    # Recent activity
    recent = conn.execute("""
        SELECT a.*, e.title, e.category, e.difficulty
        FROM attempts a JOIN exercises e ON a.exercise_id = e.id
        ORDER BY a.created_at DESC LIMIT 7
    """).fetchall()
    stats['recent_activity'] = [dict(r) for r in recent]

    # Flow state
    flow = conn.execute("SELECT * FROM flow_state LIMIT 1").fetchone()
    if flow:
        stats['total_xp'] = flow['total_xp']
        stats['current_rank'] = flow['current_rank']
    else:
        stats['total_xp'] = 0
        stats['current_rank'] = 'associate_de'

    # Mastery distribution
    mastery_rows = conn.execute("""
        SELECT mastery_level, COUNT(*) as cnt FROM progress
        GROUP BY mastery_level
    """).fetchall()
    stats['mastery_dist'] = {r['mastery_level']: r['cnt'] for r in mastery_rows}

    conn.close()
    return stats


def _calculate_day_streak(conn):
    """Calculate consecutive days with practice."""
    rows = conn.execute("""
        SELECT DISTINCT DATE(created_at) as day
        FROM attempts ORDER BY day DESC
    """).fetchall()
    if not rows:
        return 0
    streak = 0
    today = datetime.now().date()
    from datetime import timedelta
    for row in rows:
        day = datetime.strptime(row['day'], '%Y-%m-%d').date()
        expected = today - timedelta(days=streak)
        if day == expected:
            streak += 1
        else:
            break
    return streak


# ── Weakness Logging ───────────────────────────────────────

def log_weakness(concept_tag, exercise_id=None):
    """Log a detected weakness."""
    if concept_tag not in VALID_SKILL_TAGS:
        return
    conn = get_db()
    conn.execute("INSERT INTO weakness_log (concept_tag, exercise_id) VALUES (?, ?)",
                 (concept_tag, exercise_id))
    conn.commit()
    conn.close()


def mark_drill_passed(concept_tag):
    """Mark the most recent unresolved weakness as remediated."""
    conn = get_db()
    conn.execute("""
        UPDATE weakness_log SET drill_passed = 1, remediated_at = CURRENT_TIMESTAMP
        WHERE concept_tag = ? AND drill_passed = 0
        ORDER BY detected_at DESC LIMIT 1
    """, (concept_tag,))
    conn.commit()
    conn.close()


def get_active_weaknesses(limit=5):
    """Get unresolved weaknesses."""
    conn = get_db()
    rows = conn.execute("""
        SELECT concept_tag, COUNT(*) as occurrences, MAX(detected_at) as last_seen
        FROM weakness_log WHERE drill_passed = 0
        GROUP BY concept_tag ORDER BY occurrences DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Session Management ─────────────────────────────────────

def start_session(focus_areas=None):
    conn = get_db()
    cur = conn.execute("INSERT INTO sessions (focus_areas) VALUES (?)",
                       (json.dumps(focus_areas) if focus_areas else None,))
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid


def end_session(session_id):
    conn = get_db()
    conn.execute("UPDATE sessions SET ended_at = CURRENT_TIMESTAMP WHERE id = ?",
                 (session_id,))
    conn.commit()
    conn.close()
