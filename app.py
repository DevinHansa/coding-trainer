"""Flask web application for the SDE Prep platform."""
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS
from database import (
    init_db, get_exercise, get_exercises, save_attempt,
    get_attempts_for_exercise, get_dashboard_stats, get_all_progress,
    get_user_profile, get_flow_state, get_active_weaknesses,
    mark_drill_passed, count_exercises
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


# ── Pages ──────────────────────────────────────────────────

@app.route('/')
def dashboard():
    stats = get_dashboard_stats()
    plan = get_training_plan()
    gemini = check_gemini_connection()
    flow = get_flow_state()
    rank_info = get_rank_info(flow.get('total_xp', 0))
    return render_template('dashboard.html', stats=stats, plan=plan,
                           gemini=gemini, flow=flow, rank_info=rank_info,
                           ladder_ranks=LADDER_RANKS)


@app.route('/train')
@app.route('/train/<category>')
def train(category=None):
    exercise = pick_next_exercise(category=category)
    if exercise:
        return redirect(url_for('exercise_view', exercise_id=exercise['id']))

    # All exercises passed — try to generate a new one
    if category:
        result = generate_new_exercise(category)
        if result.get('id'):
            return redirect(url_for('exercise_view', exercise_id=result['id']))

    return render_template('no_exercises.html', category=category)


@app.route('/exercise/<int:exercise_id>')
def exercise_view(exercise_id):
    exercise = get_exercise(exercise_id)
    if not exercise:
        return redirect(url_for('dashboard'))
    attempts = get_attempts_for_exercise(exercise_id, limit=5)
    exercise['tags'] = json.loads(exercise['tags']) if isinstance(exercise['tags'], str) else exercise['tags']
    exercise['hints'] = json.loads(exercise['hints']) if isinstance(exercise['hints'], str) else exercise['hints']
    flow = get_flow_state()
    rank_info = get_rank_info(flow.get('total_xp', 0))
    return render_template('exercise.html', exercise=exercise,
                           attempts=attempts, rank_info=rank_info)


@app.route('/progress')
def progress_page():
    all_progress = get_all_progress()
    stats = get_dashboard_stats()
    sql_progress = [p for p in all_progress if p['category'] == 'sql']
    python_progress = [p for p in all_progress if p['category'] == 'python']
    pyspark_progress = [p for p in all_progress if p['category'] == 'pyspark']
    flow = get_flow_state()
    rank_info = get_rank_info(flow.get('total_xp', 0))
    return render_template('progress.html', sql_progress=sql_progress,
                           python_progress=python_progress,
                           pyspark_progress=pyspark_progress,
                           stats=stats, rank_info=rank_info,
                           ladder_ranks=LADDER_RANKS)


@app.route('/exercises')
def exercise_list():
    category = request.args.get('category')
    difficulty = request.args.get('difficulty', type=int)
    exercises = get_exercises(category=category, difficulty=difficulty, limit=200)
    for ex in exercises:
        ex['tags'] = json.loads(ex['tags']) if isinstance(ex['tags'], str) else ex['tags']
    return render_template('exercise_list.html', exercises=exercises,
                           category=category, difficulty=difficulty)


# ── API Endpoints ──────────────────────────────────────────

@app.route('/submit', methods=['POST'])
def submit_code():
    data = request.get_json()
    exercise_id = data.get('exercise_id')
    user_code = data.get('code', '')
    logical_steps = data.get('logical_steps', '')
    time_spent = data.get('time_spent', 0)

    exercise = get_exercise(exercise_id)
    if not exercise:
        return jsonify({'error': 'Exercise not found'}), 404

    # 1. Run hardcoded tests — this is the ONLY thing that determines the score
    exec_result = execute_code(user_code, exercise['category'], exercise)
    all_passed = exec_result.get('passed', False)

    # 2. Score is purely test-based: pass all = 100, otherwise = 0
    final_score = 100 if all_passed else 0

    # 3. AI coaching feedback — ONLY called on failure to explain what went wrong
    #    On pass, we skip AI entirely (faster + no API cost)
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
        # Call AI only to explain the failure — score stays 0
        profile = get_user_profile(exercise['category'])
        coach_feedback = evaluate_submission(
            exercise['description'], user_code, exercise['category'],
            logical_steps=logical_steps, execution_result=exec_result,
            user_profile=profile
        )
        # Keep test-based score, merge in AI coaching text only
        ai_result['feedback'] = coach_feedback.get('overall_feedback', coach_feedback.get('feedback', ''))
        ai_result['what_worked'] = coach_feedback.get('what_worked', '')
        ai_result['efficiency_notes'] = coach_feedback.get('efficiency_notes', '')
        ai_result['issues'] = coach_feedback.get('issues', [])
        ai_result['detected_weaknesses'] = coach_feedback.get('detected_weaknesses', [])

    # 4. Detect weaknesses on failure
    weaknesses = ai_result.get('detected_weaknesses', [])
    if not all_passed and not weaknesses:
        weaknesses = detect_weakness(
            user_code, exercise['category'],
            exercise['description'], final_score
        )

    # 5. Save attempt
    save_attempt(
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

    # 7. Trigger drill only on failure
    if not all_passed:
        failure_action = handle_failure(exercise_id, ai_result.get('issues', []),
                                        user_code, final_score)
        response['failure_action'] = failure_action

    # 8. Updated rank info
    flow = get_flow_state()
    response['rank_info'] = get_rank_info(flow.get('total_xp', 0))

    return jsonify(response)


@app.route('/run-tests', methods=['POST'])
def run_tests():
    """Execute code against test cases without full AI evaluation."""
    data = request.get_json()
    exercise_id = data.get('exercise_id')
    user_code = data.get('code', '')

    exercise = get_exercise(exercise_id)
    if not exercise:
        return jsonify({'error': 'Exercise not found'}), 404

    result = execute_code(user_code, exercise['category'], exercise)
    return jsonify(result)


@app.route('/hint', methods=['POST'])
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
def check_mcq():
    """Check MCQ drill answer."""
    data = request.get_json()
    selected = data.get('selected_index')
    correct = data.get('correct_index')
    concept_tag = data.get('concept_tag', '')

    passed = selected == correct
    if passed and concept_tag:
        mark_drill_passed(concept_tag)

    return jsonify({"passed": passed})


@app.route('/mcq/generate', methods=['POST'])
def generate_mcq():
    """Generate a new MCQ drill for a specific weakness."""
    data = request.get_json()
    concept_tag = data.get('concept_tag', '')
    category = data.get('category', 'python')

    result = generate_mcq_drill(concept_tag, category)
    return jsonify(result)


@app.route('/generate', methods=['POST'])
def generate_exercise_route():
    data = request.get_json()
    category = data.get('category', 'sql')
    difficulty = data.get('difficulty')

    result = generate_new_exercise(category, difficulty)
    if result.get('error'):
        return jsonify(result), 500
    return jsonify(result)


# ── API Status ─────────────────────────────────────────────

@app.route('/api/stats')
def api_stats():
    return jsonify(get_dashboard_stats())


@app.route('/api/gemini-status')
def api_gemini_status():
    return jsonify(check_gemini_connection())


@app.route('/api/flow-state')
def api_flow_state():
    flow = get_flow_state()
    rank_info = get_rank_info(flow.get('total_xp', 0))
    return jsonify({**flow, "rank_info": rank_info})


@app.route('/api/user-profile')
def api_user_profile():
    category = request.args.get('category')
    return jsonify(get_user_profile(category))


@app.route('/api/dashboard')
def api_dashboard():
    stats = get_dashboard_stats()
    plan = get_training_plan()
    gemini = check_gemini_connection()
    flow = get_flow_state()
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
def api_exercises():
    category = request.args.get('category')
    difficulty = request.args.get('difficulty', type=int)
    exercises = get_exercises(category=category, difficulty=difficulty, limit=200)
    for ex in exercises:
        ex['tags'] = json.loads(ex['tags']) if isinstance(ex['tags'], str) else ex['tags']
    return jsonify(exercises)

@app.route('/api/exercises/<int:exercise_id>')
def api_exercise_detail(exercise_id):
    exercise = get_exercise(exercise_id)
    if not exercise:
        return jsonify({'error': 'Not found'}), 404
    exercise['tags'] = json.loads(exercise['tags']) if isinstance(exercise['tags'], str) else exercise['tags']
    exercise['hints'] = json.loads(exercise['hints']) if isinstance(exercise['hints'], str) else exercise['hints']
    attempts = get_attempts_for_exercise(exercise_id, limit=5)
    return jsonify({'exercise': exercise, 'attempts': attempts})

@app.route('/api/progress')
def api_progress():
    all_progress = get_all_progress()
    stats = get_dashboard_stats()
    sql_progress = [p for p in all_progress if p['category'] == 'sql']
    python_progress = [p for p in all_progress if p['category'] == 'python']
    pyspark_progress = [p for p in all_progress if p['category'] == 'pyspark']
    flow = get_flow_state()
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
def api_next_exercise():
    category = request.args.get('category')
    current_id = request.args.get('current_id', type=int)
    exercise = pick_next_exercise(category=category)
    if exercise and exercise.get('id') != current_id:
        return jsonify({
            'id': exercise['id'],
            'title': exercise.get('title', 'Next Exercise'),
            'category': exercise.get('category', ''),
            'difficulty': exercise.get('difficulty', 1),
        })
    # All done in this category — suggest a different one
    return jsonify({'id': None, 'message': 'All exercises in this category complete!'})


if __name__ == '__main__':
    app.run(debug=DEBUG, port=PORT)
