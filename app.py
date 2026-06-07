"""Flask web application for the SDE Prep platform with user authentication."""
import json
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, g
from flask_cors import CORS
from database import (
    init_db, get_exercise, get_exercises, save_attempt,
    get_attempts_for_exercise, get_dashboard_stats, get_all_progress,
    get_user_profile, get_flow_state, get_active_weaknesses,
    mark_drill_passed, count_exercises, create_user, verify_user,
    create_token, verify_token, revoke_token, get_username_by_id
)
from exercise_engine import (
    pick_next_exercise, handle_failure, generate_new_exercise, get_training_plan
)
from coach import (
    evaluate_submission, give_hint, check_gemini_connection,
    detect_weakness, generate_mcq_drill
)
from executor import execute_code
from flow_engine import get_rank_info
from config import SECRET_KEY, DEBUG, PORT, LADDER_RANKS
from seed_exercises import seed_database

app = Flask(__name__)
app.secret_key = SECRET_KEY
CORS(app)

init_db()
seed_database()


# ── Auth Middleware Decorator ──────────────────────────────

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('x-auth-token')
        if not token:
            return jsonify({'error': 'Unauthorized, no token provided'}), 401
        user_id = verify_token(token)
        if not user_id:
            return jsonify({'error': 'Unauthorized, invalid or expired token'}), 401
        g.user_id = user_id
        return f(*args, **kwargs)
    return decorated


# ── Auth Endpoints ─────────────────────────────────────────

@app.route('/api/auth/register', methods=['POST'])
def auth_register():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    if len(username) < 3 or len(password) < 6:
        return jsonify({'error': 'Username must be at least 3 chars and password at least 6 chars'}), 400

    user_id = create_user(username, password)
    if not user_id:
        return jsonify({'error': 'Username is already taken'}), 409

    token = create_token(user_id)
    return jsonify({
        'token': token,
        'user': {
            'id': user_id,
            'username': username
        }
    })


@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    user_id = verify_user(username, password)
    if not user_id:
        return jsonify({'error': 'Invalid username or password'}), 401

    token = create_token(user_id)
    return jsonify({
        'token': token,
        'user': {
            'id': user_id,
            'username': username
        }
    })


@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def auth_logout():
    token = request.headers.get('x-auth-token')
    if token:
        revoke_token(token)
    return jsonify({'message': 'Logged out successfully'})


@app.route('/api/auth/me', methods=['GET'])
@require_auth
def auth_me():
    username = get_username_by_id(g.user_id)
    return jsonify({
        'id': g.user_id,
        'username': username
    })


# ── Web Pages (Backward Compatible / Single User Mode) ─────

@app.route('/')
def dashboard():
    stats = get_dashboard_stats(1)
    plan = get_training_plan(1)
    gemini = check_gemini_connection()
    flow = get_flow_state(1)
    rank_info = get_rank_info(flow.get('total_xp', 0))
    return render_template('dashboard.html', stats=stats, plan=plan,
                           gemini=gemini, flow=flow, rank_info=rank_info,
                           ladder_ranks=LADDER_RANKS)


@app.route('/train')
@app.route('/train/<category>')
def train(category=None):
    exercise = pick_next_exercise(1, category=category)
    if exercise:
        return redirect(url_for('exercise_view', exercise_id=exercise['id']))

    # All exercises passed — try to generate a new one
    if category:
        result = generate_new_exercise(1, category)
        if result.get('id'):
            return redirect(url_for('exercise_view', exercise_id=result['id']))

    return render_template('no_exercises.html', category=category)


@app.route('/exercise/<int:exercise_id>')
def exercise_view(exercise_id):
    exercise = get_exercise(exercise_id)
    if not exercise:
        return render_template('no_exercises.html')
    exercise['tags'] = json.loads(exercise['tags']) if isinstance(exercise['tags'], str) else exercise['tags']
    exercise['hints'] = json.loads(exercise['hints']) if isinstance(exercise['hints'], str) else exercise['hints']
    attempts = get_attempts_for_exercise(exercise_id, 1, limit=5)
    return render_template('exercise.html', exercise=exercise, attempts=attempts)


@app.route('/progress')
def progress():
    all_progress = get_all_progress(1)
    stats = get_dashboard_stats(1)
    sql_progress = [p for p in all_progress if p['category'] == 'sql']
    python_progress = [p for p in all_progress if p['category'] == 'python']
    pyspark_progress = [p for p in all_progress if p['category'] == 'pyspark']
    flow = get_flow_state(1)
    rank_info = get_rank_info(flow.get('total_xp', 0))
    return render_template('progress.html', sql_progress=sql_progress,
                           python_progress=python_progress,
                           pyspark_progress=pyspark_progress,
                           stats=stats, rank_info=rank_info,
                           ladder_ranks=LADDER_RANKS)


@app.route('/exercises')
def exercises_list():
    category = request.args.get('category')
    difficulty = request.args.get('difficulty', type=int)
    exercises = get_exercises(category=category, difficulty=difficulty, limit=200)
    for ex in exercises:
        ex['tags'] = json.loads(ex['tags']) if isinstance(ex['tags'], str) else ex['tags']
    return render_template('exercise_list.html', exercises=exercises,
                           category=category, difficulty=difficulty)


# ── REST API Endpoints (Fully User-Scoped & Protected) ─────

@app.route('/submit', methods=['POST'])
@require_auth
def submit_code():
    data = request.get_json()
    exercise_id = data.get('exercise_id')
    user_code = data.get('code', '')
    logical_steps = data.get('logical_steps', '')
    time_spent = data.get('time_spent', 0)

    exercise = get_exercise(exercise_id)
    if not exercise:
        return jsonify({'error': 'Exercise not found'}), 404

    # 1. Run hardcoded tests
    exec_result = execute_code(user_code, exercise['category'], exercise)
    all_passed = exec_result.get('passed', False)

    # 2. Score is purely test-based
    final_score = 100 if all_passed else 0

    # 3. AI coaching feedback only on failure
    ai_result = {
        'score': final_score,
        'works_correctly': all_passed,
        'feedback': '',
        'what_worked': '',
        'efficiency_notes': '',
        'issues': [],
        'detected_weaknesses': [],
        'overall_feedback': '',
    }

    if all_passed:
        ai_result['feedback'] = '✅ All tests passed! Great work.'
        ai_result['what_worked'] = 'Your solution produced the correct output for all test cases.'
    else:
        profile = get_user_profile(g.user_id, exercise['category'])
        coach_feedback = evaluate_submission(
            exercise['description'], user_code, exercise['category'],
            logical_steps=logical_steps, execution_result=exec_result,
            user_profile=profile
        )
        ai_result['feedback'] = coach_feedback.get('overall_feedback', coach_feedback.get('feedback', ''))
        ai_result['what_worked'] = coach_feedback.get('what_worked', '')
        ai_result['efficiency_notes'] = coach_feedback.get('efficiency_notes', '')
        ai_result['issues'] = coach_feedback.get('issues', [])
        ai_result['detected_weaknesses'] = coach_feedback.get('detected_weaknesses', [])

    # 4. Detect weaknesses
    weaknesses = ai_result.get('detected_weaknesses', [])
    if not all_passed and not weaknesses:
        weaknesses = detect_weakness(
            user_code, exercise['category'],
            exercise['description'], final_score
        )

    # 5. Save attempt under user ID
    save_attempt(
        user_id=g.user_id,
        exercise_id=exercise_id,
        user_code=user_code,
        logical_steps=logical_steps,
        score=final_score,
        hints_used=data.get('hints_used', 0),
        time_spent=time_spent,
        feedback=json.dumps(ai_result),
        execution_result=exec_result,
        weakness_detected=weaknesses,
    )

    # 6. Build response
    response = {
        **ai_result,
        'score': final_score,
        'execution': exec_result,
        'weaknesses': weaknesses,
        'solution': exercise.get('solution', '') if not all_passed else '',
    }

    # 7. Trigger drill on failure
    if not all_passed:
        failure_action = handle_failure(g.user_id, exercise_id, ai_result.get('issues', []),
                                        user_code, final_score)
        response['failure_action'] = failure_action

    # 8. Updated rank info
    flow = get_flow_state(g.user_id)
    response['rank_info'] = get_rank_info(flow.get('total_xp', 0))

    return jsonify(response)


@app.route('/run-tests', methods=['POST'])
@require_auth
def run_tests():
    data = request.get_json()
    exercise_id = data.get('exercise_id')
    user_code = data.get('code', '')

    exercise = get_exercise(exercise_id)
    if not exercise:
        return jsonify({'error': 'Exercise not found'}), 404

    result = execute_code(user_code, exercise['category'], exercise)
    return jsonify(result)


@app.route('/hint', methods=['POST'])
@require_auth
def get_hint():
    data = request.get_json()
    exercise_id = data.get('exercise_id')
    user_code = data.get('code', '')
    hint_level = data.get('hint_level', 1)

    exercise = get_exercise(exercise_id)
    if not exercise:
        return jsonify({'error': 'Exercise not found'}), 404

    hints = exercise.get('hints')
    if isinstance(hints, str):
        try:
            hints = json.loads(hints)
        except json.JSONDecodeError:
            hints = []
    hints = hints or []

    if 1 <= hint_level <= len(hints):
        return jsonify({
            'hint': hints[hint_level - 1],
            'encouragement': "Use this to guide your next step.",
            'source': 'built-in'
        })

    result = give_hint(exercise['description'], user_code, hint_level, exercise['category'])
    return jsonify(result)


@app.route('/mcq/check', methods=['POST'])
@require_auth
def check_mcq():
    data = request.get_json()
    selected = data.get('selected_index')
    correct = data.get('correct_index')
    concept_tag = data.get('concept_tag', '')

    passed = selected == correct
    if passed and concept_tag:
        mark_drill_passed(g.user_id, concept_tag)

    return jsonify({"passed": passed})


@app.route('/mcq/generate', methods=['POST'])
@require_auth
def generate_mcq():
    data = request.get_json()
    concept_tag = data.get('concept_tag', '')
    category = data.get('category', 'python')

    result = generate_mcq_drill(concept_tag, category)
    return jsonify(result)


@app.route('/generate', methods=['POST'])
@require_auth
def generate_exercise_route():
    data = request.get_json()
    category = data.get('category', 'sql')
    difficulty = data.get('difficulty')

    result = generate_new_exercise(g.user_id, category, difficulty)
    if result.get('error'):
        return jsonify(result), 500
    return jsonify(result)


@app.route('/api/stats')
@require_auth
def api_stats():
    return jsonify(get_dashboard_stats(g.user_id))


@app.route('/api/gemini-status')
@require_auth
def api_gemini_status():
    return jsonify(check_gemini_connection())


@app.route('/api/flow-state')
@require_auth
def api_flow_state():
    flow = get_flow_state(g.user_id)
    rank_info = get_rank_info(flow.get('total_xp', 0))
    return jsonify({**flow, "rank_info": rank_info})


@app.route('/api/user-profile')
@require_auth
def api_user_profile():
    category = request.args.get('category')
    return jsonify(get_user_profile(g.user_id, category))


@app.route('/api/dashboard')
@require_auth
def api_dashboard():
    stats = get_dashboard_stats(g.user_id)
    plan = get_training_plan(g.user_id)
    gemini = check_gemini_connection()
    flow = get_flow_state(g.user_id)
    rank_info = get_rank_info(flow.get('total_xp', 0))
    return jsonify({
        'stats': stats,
        'plan': plan,
        'gemini': gemini,
        'flow': flow,
        'rank_info': rank_info,
        'ladder_ranks': LADDER_RANKS
    })


@app.route('/api/exercises')
@require_auth
def api_exercises():
    category = request.args.get('category')
    difficulty = request.args.get('difficulty', type=int)
    exercises = get_exercises(category=category, difficulty=difficulty, limit=200)
    for ex in exercises:
        ex['tags'] = json.loads(ex['tags']) if isinstance(ex['tags'], str) else ex['tags']
    return jsonify(exercises)


@app.route('/api/exercises/<int:exercise_id>')
@require_auth
def api_exercise_detail(exercise_id):
    exercise = get_exercise(exercise_id)
    if not exercise:
        return jsonify({'error': 'Not found'}), 404
    exercise['tags'] = json.loads(exercise['tags']) if isinstance(exercise['tags'], str) else exercise['tags']
    exercise['hints'] = json.loads(exercise['hints']) if isinstance(exercise['hints'], str) else exercise['hints']
    attempts = get_attempts_for_exercise(exercise_id, g.user_id, limit=5)
    return jsonify({'exercise': exercise, 'attempts': attempts})


@app.route('/api/progress')
@require_auth
def api_progress():
    all_progress = get_all_progress(g.user_id)
    stats = get_dashboard_stats(g.user_id)
    sql_progress = [p for p in all_progress if p['category'] == 'sql']
    python_progress = [p for p in all_progress if p['category'] == 'python']
    pyspark_progress = [p for p in all_progress if p['category'] == 'pyspark']
    flow = get_flow_state(g.user_id)
    rank_info = get_rank_info(flow.get('total_xp', 0))
    return jsonify({
        'sql_progress': sql_progress,
        'python_progress': python_progress,
        'pyspark_progress': pyspark_progress,
        'stats': stats,
        'rank_info': rank_info,
        'ladder_ranks': LADDER_RANKS
    })


@app.route('/api/next-exercise')
@require_auth
def api_next_exercise():
    category = request.args.get('category')
    current_id = request.args.get('current_id', type=int)
    exercise = pick_next_exercise(g.user_id, category=category)
    if exercise and exercise.get('id') != current_id:
        return jsonify({
            'id': exercise['id'],
            'title': exercise.get('title', 'Next Exercise'),
            'category': exercise.get('category', ''),
            'difficulty': exercise.get('difficulty', 1),
        })
    return jsonify({'id': None, 'message': 'All exercises in this category complete!'})


if __name__ == '__main__':
    app.run(debug=DEBUG, port=PORT)
