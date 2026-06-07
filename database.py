"""Database layer for the SDE Prep platform — SQLite with full schema and multi-user support."""
import sqlite3
import json
import secrets
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
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
    
    # 1. Create static tables and basic user tables
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
        
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS user_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)

    # 2. Build other tables with user_id support
    conn.executescript("""
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
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (exercise_id) REFERENCES exercises(id)
        );

        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concept_tag TEXT NOT NULL,
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
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, concept_tag)
        );

        CREATE TABLE IF NOT EXISTS weakness_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concept_tag TEXT NOT NULL,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            exercise_id INTEGER,
            drill_passed INTEGER DEFAULT 0,
            remediated_at TIMESTAMP,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
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
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP,
            exercises_attempted INTEGER DEFAULT 0,
            exercises_passed INTEGER DEFAULT 0,
            avg_score REAL DEFAULT 0,
            focus_areas TEXT,
            notes TEXT,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_attempts_exercise ON attempts(exercise_id);
        CREATE INDEX IF NOT EXISTS idx_progress_tag ON progress(concept_tag);
        CREATE INDEX IF NOT EXISTS idx_progress_category ON progress(category);
        CREATE INDEX IF NOT EXISTS idx_exercises_category ON exercises(category, difficulty);
        CREATE INDEX IF NOT EXISTS idx_exercises_topic ON exercises(category, topic, difficulty);
        CREATE INDEX IF NOT EXISTS idx_weakness_tag ON weakness_log(concept_tag);
    """)

    # 3. Perform schema upgrades and migrate legacy records
    _migrate_database(conn)

    conn.commit()
    conn.close()


def _add_column_if_missing(conn, table_name, column_name, column_def):
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    if column_name not in columns:
        try:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
        except sqlite3.OperationalError:
            pass


def _migrate_database(conn):
    # original basic migrations
    _migrate_columns(conn)

    # 1. First, seed a default user with id = 1 if the users table is empty.
    # This prevents FOREIGN KEY check failures when adding records scoped to user_id = 1.
    has_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if has_users == 0:
        print("Migrating schema: Seeding default user 'default_user' with password 'password'...")
        from werkzeug.security import generate_password_hash
        hashed = generate_password_hash("password")
        conn.execute("INSERT OR IGNORE INTO users (id, username, password_hash) VALUES (1, 'default_user', ?)", (hashed,))

    # Make attempts, weakness_log, flow_state, sessions user-aware
    _add_column_if_missing(conn, "attempts", "user_id", "INTEGER REFERENCES users(id) ON DELETE CASCADE")
    _add_column_if_missing(conn, "weakness_log", "user_id", "INTEGER REFERENCES users(id) ON DELETE CASCADE")
    _add_column_if_missing(conn, "flow_state", "user_id", "INTEGER REFERENCES users(id) ON DELETE CASCADE")
    _add_column_if_missing(conn, "sessions", "user_id", "INTEGER REFERENCES users(id) ON DELETE CASCADE")

    # Migrate progress table to add user_id UNIQUE constraint
    cursor = conn.execute("PRAGMA table_info(progress)")
    columns = [row[1] for row in cursor.fetchall()]
    if "user_id" not in columns:
        print("Migrating progress table unique constraint for multi-user support...")
        conn.execute("ALTER TABLE progress RENAME TO progress_old")
        conn.execute("""
            CREATE TABLE progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                concept_tag TEXT NOT NULL,
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
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, concept_tag)
            )
        """)
        
        # Copy data, defaulting user_id to 1 (will be the default user)
        conn.execute("""
            INSERT INTO progress (
                id, concept_tag, category, attempts_count, success_count, current_streak,
                best_streak, difficulty_level, avg_score, mastery_level, total_time_spent,
                last_practiced, updated_at, user_id
            ) SELECT 
                id, concept_tag, category, attempts_count, success_count, current_streak,
                best_streak, difficulty_level, avg_score, mastery_level, total_time_spent,
                last_practiced, updated_at, 1
            FROM progress_old
        """)
        conn.execute("DROP TABLE progress_old")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_progress_tag ON progress(concept_tag)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_progress_category ON progress(category)")

    # Scope all legacy items to default user
    conn.execute("UPDATE attempts SET user_id = 1 WHERE user_id IS NULL")
    conn.execute("UPDATE progress SET user_id = 1 WHERE user_id IS NULL")
    conn.execute("UPDATE weakness_log SET user_id = 1 WHERE user_id IS NULL")
    conn.execute("UPDATE flow_state SET user_id = 1 WHERE user_id IS NULL")
    conn.execute("UPDATE sessions SET user_id = 1 WHERE user_id IS NULL")

    # Ensure existing users have a flow_state row
    users_rows = conn.execute("SELECT id FROM users").fetchall()
    for u in users_rows:
        uid = u['id']
        flow_exists = conn.execute("SELECT COUNT(*) FROM flow_state WHERE user_id = ?", (uid,)).fetchone()[0]
        if flow_exists == 0:
            conn.execute("INSERT INTO flow_state (category, user_id) VALUES (NULL, ?)", (uid,))


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


# ── User Account & Token CRUD ──────────────────────────────

def create_user(username, password):
    """Create a new user and return their user_id, or None if username exists."""
    conn = get_db()
    hashed = generate_password_hash(password)
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, hashed)
        )
        user_id = cur.lastrowid
        # Initialize flow state for the new user
        conn.execute(
            "INSERT INTO flow_state (category, user_id) VALUES (NULL, ?)",
            (user_id,)
        )
        conn.commit()
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        conn.close()
        return None


def verify_user(username, password):
    """Verify credentials and return user_id or None if invalid."""
    conn = get_db()
    row = conn.execute(
        "SELECT id, password_hash FROM users WHERE username = ?",
        (username,)
    ).fetchone()
    conn.close()
    if row and check_password_hash(row['password_hash'], password):
        return row['id']
    return None


def create_token(user_id):
    """Generate a secure random token, store it, and return it."""
    token = secrets.token_hex(32)
    conn = get_db()
    conn.execute(
        "INSERT INTO user_tokens (token, user_id) VALUES (?, ?)",
        (token, user_id)
    )
    conn.commit()
    conn.close()
    return token


def verify_token(token):
    """Check token validity and return user_id, or None if invalid."""
    conn = get_db()
    row = conn.execute(
        "SELECT user_id FROM user_tokens WHERE token = ?",
        (token,)
    ).fetchone()
    conn.close()
    return row['user_id'] if row else None


def revoke_token(token):
    """Delete token from user_tokens table."""
    conn = get_db()
    conn.execute(
        "DELETE FROM user_tokens WHERE token = ?",
        (token,)
    )
    conn.commit()
    conn.close()


def get_username_by_id(user_id):
    """Fetch username by user id."""
    conn = get_db()
    row = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return row['username'] if row else None


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

def save_attempt(user_id, exercise_id, user_code, logical_steps, score, hints_used,
                  time_spent, feedback, execution_result=None,
                  weakness_detected=None):
    """Save an attempt and update progress."""
    conn = get_db()
    exec_str = json.dumps(execution_result) if isinstance(execution_result, dict) else execution_result
    weak_str = json.dumps(weakness_detected) if isinstance(weakness_detected, list) else weakness_detected

    conn.execute("""
        INSERT INTO attempts (exercise_id, user_code, logical_steps, score,
                              hints_used, time_spent_seconds, feedback,
                              execution_result, weakness_detected, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (exercise_id, user_code, logical_steps, score, hints_used,
          time_spent, feedback, exec_str, weak_str, user_id))

    # Update progress for each tag
    exercise = conn.execute("SELECT * FROM exercises WHERE id = ?", (exercise_id,)).fetchone()
    if exercise:
        tags = json.loads(exercise['tags']) if exercise['tags'] else []
        category = exercise['category']
        passed = score >= 70

        for tag in tags:
            concept = tag if ':' in tag else f"{category}:{tag}"
            _update_progress(conn, user_id, concept, category, score, passed, time_spent)

    # Update flow state
    _update_flow_state(conn, user_id, exercise['category'] if exercise else None, score, time_spent)

    # Log weaknesses
    if weakness_detected:
        weak_list = weakness_detected if isinstance(weakness_detected, list) else json.loads(weakness_detected or "[]")
        for tag in weak_list:
            if tag in VALID_SKILL_TAGS:
                conn.execute("""
                    INSERT INTO weakness_log (concept_tag, exercise_id, user_id)
                    VALUES (?, ?, ?)
                """, (tag, exercise_id, user_id))

    conn.commit()
    conn.close()


def _update_progress(conn, user_id, concept, category, score, passed, time_spent):
    """Update progress for a single concept tag for a specific user."""
    existing = conn.execute(
        "SELECT * FROM progress WHERE concept_tag = ? AND user_id = ?", (concept, user_id)
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
            WHERE concept_tag = ? AND user_id = ?
        """, (new_count, new_success, new_streak, best_streak,
              new_avg, mastery, total_time, concept, user_id))
    else:
        mastery = _calculate_mastery(score, 1, 1 if passed else 0)
        cat = category
        if concept.startswith("py:"):
            cat = "python"
        elif concept.startswith("sql:"):
            cat = "sql"
        elif concept.startswith("spark:"):
            cat = "pyspark"
        elif concept.startswith("gotcha:"):
            cat = category

        conn.execute("""
            INSERT INTO progress (concept_tag, category, attempts_count, success_count,
                                  current_streak, best_streak, avg_score, mastery_level,
                                  total_time_spent, last_practiced, user_id)
            VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
        """, (concept, cat, 1 if passed else 0, 1 if passed else 0,
              1 if passed else 0, score, mastery, time_spent, user_id))


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


def _update_flow_state(conn, user_id, category, score, time_spent):
    """Update the flow state tracker for a specific user."""
    row = conn.execute("SELECT * FROM flow_state WHERE user_id = ? LIMIT 1", (user_id,)).fetchone()
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
        WHERE user_id = ?
    """, (category, new_passes, new_fails, total_xp, current_rank, user_id))


def get_attempts_for_exercise(exercise_id, user_id, limit=10):
    """Get recent attempts for an exercise by a specific user."""
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM attempts WHERE exercise_id = ? AND user_id = ?
        ORDER BY created_at DESC LIMIT ?
    """, (exercise_id, user_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Progress & Stats ───────────────────────────────────────

def get_all_progress(user_id):
    """Get all progress records for a user."""
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM progress WHERE user_id = ?
        ORDER BY avg_score ASC, attempts_count DESC
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_weak_concepts(user_id, category=None, limit=5):
    """Get weakest concepts with at least 1 attempt for a user."""
    conn = get_db()
    query = """
        SELECT *, CAST(success_count AS REAL) / MAX(attempts_count, 1) as success_rate
        FROM progress WHERE attempts_count > 0 AND user_id = ?
    """
    params = [user_id]
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY success_rate ASC, last_practiced ASC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_profile(user_id, category=None):
    """Build a user profile dict for Gemini context scoped to user."""
    conn = get_db()

    total_attempts = conn.execute("SELECT COUNT(*) FROM attempts WHERE user_id = ?", (user_id,)).fetchone()[0]
    avg_score_row = conn.execute("SELECT AVG(score) FROM attempts WHERE user_id = ?", (user_id,)).fetchone()
    avg_score = round(avg_score_row[0], 1) if avg_score_row[0] else 0

    weak = get_weak_concepts(user_id, category=category, limit=5)

    recent_weak = conn.execute("""
        SELECT concept_tag, COUNT(*) as freq
        FROM weakness_log
        WHERE detected_at > datetime('now', '-7 days') AND user_id = ?
        GROUP BY concept_tag ORDER BY freq DESC LIMIT 5
    """, (user_id,)).fetchall()

    mastery_dist = {}
    rows = conn.execute("SELECT mastery_level, COUNT(*) as cnt FROM progress WHERE user_id = ? GROUP BY mastery_level", (user_id,)).fetchall()
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


def get_flow_state(user_id):
    """Get current flow state for a user."""
    conn = get_db()
    row = conn.execute("SELECT * FROM flow_state WHERE user_id = ? LIMIT 1", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else {
        "current_difficulty": 1, "consecutive_passes": 0,
        "consecutive_fails": 0, "total_xp": 0, "current_rank": "associate_de",
    }


def get_dashboard_stats(user_id):
    """Get comprehensive stats for the dashboard scoped to a user."""
    conn = get_db()
    stats = {}

    stats['total_exercises'] = conn.execute("SELECT COUNT(*) FROM exercises").fetchone()[0]
    stats['total_attempts'] = conn.execute("SELECT COUNT(*) FROM attempts WHERE user_id = ?", (user_id,)).fetchone()[0]

    row = conn.execute("SELECT AVG(score) FROM attempts WHERE user_id = ?", (user_id,)).fetchone()
    stats['avg_score'] = round(row[0], 1) if row[0] else 0

    stats['today_attempts'] = conn.execute("""
        SELECT COUNT(*) FROM attempts WHERE DATE(created_at) = DATE('now') AND user_id = ?
    """, (user_id,)).fetchone()[0]

    stats['current_streak'] = _calculate_day_streak(conn, user_id)

    for cat in ['sql', 'python', 'pyspark']:
        cat_row = conn.execute("""
            SELECT COUNT(*) as cnt, AVG(a.score) as avg
            FROM attempts a JOIN exercises e ON a.exercise_id = e.id
            WHERE e.category = ? AND a.user_id = ?
        """, (cat, user_id)).fetchone()
        stats[f'{cat}_attempts'] = cat_row['cnt']
        stats[f'{cat}_avg'] = round(cat_row['avg'], 1) if cat_row['avg'] else 0

    stats['exercises_passed'] = conn.execute("""
        SELECT COUNT(DISTINCT exercise_id) FROM attempts WHERE score >= 70 AND user_id = ?
    """, (user_id,)).fetchone()[0]

    weak = conn.execute("""
        SELECT concept_tag, avg_score, mastery_level
        FROM progress WHERE attempts_count > 0 AND user_id = ?
        ORDER BY avg_score ASC LIMIT 5
    """, (user_id,)).fetchall()
    stats['weak_areas'] = [{'tag': w['concept_tag'], 'score': round(w['avg_score'], 1),
                             'mastery': w['mastery_level']} for w in weak]

    recent = conn.execute("""
        SELECT a.*, e.title, e.category, e.difficulty
        FROM attempts a JOIN exercises e ON a.exercise_id = e.id
        WHERE a.user_id = ?
        ORDER BY a.created_at DESC LIMIT 7
    """, (user_id,)).fetchall()
    stats['recent_activity'] = [dict(r) for r in recent]

    flow = conn.execute("SELECT * FROM flow_state WHERE user_id = ?", (user_id,)).fetchone()
    if flow:
        stats['total_xp'] = flow['total_xp']
        stats['current_rank'] = flow['current_rank']
    else:
        stats['total_xp'] = 0
        stats['current_rank'] = 'associate_de'

    mastery_rows = conn.execute("""
        SELECT mastery_level, COUNT(*) as cnt FROM progress WHERE user_id = ?
        GROUP BY mastery_level
    """, (user_id,)).fetchall()
    stats['mastery_dist'] = {r['mastery_level']: r['cnt'] for r in mastery_rows}

    conn.close()
    return stats


def _calculate_day_streak(conn, user_id):
    """Calculate consecutive days with practice for a specific user."""
    rows = conn.execute("""
        SELECT DISTINCT DATE(created_at) as day
        FROM attempts WHERE user_id = ? ORDER BY day DESC
    """, (user_id,)).fetchall()
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

def log_weakness(user_id, concept_tag, exercise_id=None):
    """Log a detected weakness for a user."""
    if concept_tag not in VALID_SKILL_TAGS:
        return
    conn = get_db()
    conn.execute("INSERT INTO weakness_log (concept_tag, exercise_id, user_id) VALUES (?, ?, ?)",
                 (concept_tag, exercise_id, user_id))
    conn.commit()
    conn.close()


def mark_drill_passed(user_id, concept_tag):
    """Mark the most recent unresolved weakness as remediated for a user."""
    conn = get_db()
    conn.execute("""
        UPDATE weakness_log SET drill_passed = 1, remediated_at = CURRENT_TIMESTAMP
        WHERE concept_tag = ? AND drill_passed = 0 AND user_id = ?
        ORDER BY detected_at DESC LIMIT 1
    """, (concept_tag, user_id))
    conn.commit()
    conn.close()


def get_active_weaknesses(user_id, limit=5):
    """Get unresolved weaknesses for a user."""
    conn = get_db()
    rows = conn.execute("""
        SELECT concept_tag, COUNT(*) as occurrences, MAX(detected_at) as last_seen
        FROM weakness_log WHERE drill_passed = 0 AND user_id = ?
        GROUP BY concept_tag ORDER BY occurrences DESC LIMIT ?
    """, (user_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Session Management ─────────────────────────────────────

def start_session(user_id, focus_areas=None):
    conn = get_db()
    cur = conn.execute("INSERT INTO sessions (focus_areas, user_id) VALUES (?, ?)",
                       (json.dumps(focus_areas) if focus_areas else None, user_id))
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid


def end_session(user_id, session_id):
    conn = get_db()
    conn.execute("UPDATE sessions SET ended_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                 (session_id, user_id))
    conn.commit()
    conn.close()
