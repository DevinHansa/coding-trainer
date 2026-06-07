"""Exercise engine — adaptive practice flow with user-specific flow-state integration."""
import json
import random
from database import (
    get_exercises, get_exercise, get_weak_concepts, get_all_progress,
    get_attempts_for_exercise, insert_exercise, count_exercises,
    get_active_weaknesses, get_user_profile,
)
from coach import generate_exercise, generate_mcq_drill, detect_weakness
from flow_engine import get_adaptive_difficulty, should_trigger_mcq_drill


def pick_next_exercise(user_id, category=None, session_focus=None):
    """Pick the best next exercise — never repeats a passed exercise unless all are passed."""
    weak = get_weak_concepts(user_id, category=category, limit=5)
    target_difficulty = get_adaptive_difficulty(user_id, category)

    # Gather ALL exercises for this category
    all_exercises = get_exercises(category=category, limit=100)
    if not all_exercises:
        return None

    # Split into passed vs not-passed
    passed_ids = {ex['id'] for ex in all_exercises if _has_passed(user_id, ex['id'])}
    unpassed = [ex for ex in all_exercises if ex['id'] not in passed_ids]

    # 1. Try weak-concept exercises that haven't been passed
    if weak and unpassed:
        weak_tags = [w['concept_tag'] for w in weak]
        weak_candidates = [
            ex for ex in unpassed
            if any(tag in (ex.get('tags') or '') for tag in weak_tags)
        ]
        if weak_candidates:
            return _pick_least_recent(user_id, weak_candidates)

    # 2. Try unpassed at target difficulty
    at_target = [ex for ex in unpassed if ex['difficulty'] == target_difficulty]
    if at_target:
        return _pick_least_recent(user_id, at_target)

    # 3. Try unpassed at ANY difficulty (prefer closest to target)
    if unpassed:
        unpassed.sort(key=lambda ex: abs(ex['difficulty'] - target_difficulty))
        return unpassed[0]

    # 4. Everything is passed — return None so /train can generate a new one
    return None


def _has_passed(user_id, exercise_id):
    attempts = get_attempts_for_exercise(exercise_id, user_id, limit=5)
    return any(a['score'] >= 70 for a in attempts)


def _pick_least_recent(user_id, candidates):
    for c in candidates:
        attempts = get_attempts_for_exercise(c['id'], user_id, limit=1)
        c['_last_attempted'] = attempts[0]['created_at'] if attempts else '2000-01-01'
    candidates.sort(key=lambda c: c.get('_last_attempted', '2000-01-01'))
    return candidates[0]


def handle_failure(user_id, exercise_id, issues, user_code="", score=0):
    """Handle a failed submission — check if MCQ drill should trigger."""
    exercise = get_exercise(exercise_id)
    if not exercise:
        return None

    # Check if MCQ drill should be triggered
    if should_trigger_mcq_drill(user_id, exercise.get('category')):
        active_weaknesses = get_active_weaknesses(user_id, limit=1)
        if active_weaknesses:
            tag = active_weaknesses[0]['concept_tag']
            mcq = generate_mcq_drill(tag, exercise['category'])
            return {"type": "mcq_drill", "drill": mcq, "weakness_tag": tag}

    # Otherwise suggest next exercise at lower difficulty
    return {"type": "retry", "suggestion": "Try the next exercise — build momentum."}


def generate_new_exercise(user_id, category, difficulty=None, weak_tags=None):
    """Generate a new AI exercise and save it."""
    if difficulty is None:
        difficulty = get_adaptive_difficulty(user_id, category)
    if weak_tags is None:
        weak = get_weak_concepts(user_id, category=category, limit=3)
        weak_tags = [w['concept_tag'] for w in weak]

    profile = get_user_profile(user_id, category)
    result = generate_exercise(category, difficulty, weak_tags, user_profile=profile)

    if result.get("error"):
        return result

    exercise_id = insert_exercise(
        category=category, difficulty=difficulty,
        title=result.get('title', 'Generated Exercise'),
        description=result.get('description', ''),
        sample_data=result.get('sample_data', ''),
        expected_output=result.get('expected_output', ''),
        solution=result.get('solution', ''),
        tags=result.get('tags', [category]),
        hints=result.get('hints', []),
        is_seed=0,
        test_cases=result.get('test_cases', []),
        time_limit_seconds=result.get('time_limit_seconds', 900),
    )
    result['id'] = exercise_id
    result['category'] = category
    result['difficulty'] = difficulty
    return result


def get_training_plan(user_id, category=None):
    """Generate a training plan based on progress."""
    weak = get_weak_concepts(user_id, category=category, limit=5)
    progress = get_all_progress(user_id)
    total = count_exercises()
    difficulty = get_adaptive_difficulty(user_id, category)

    plan = {
        "focus_areas": [],
        "target_difficulty": difficulty,
        "total_exercises_available": total,
        "recommendation": "",
    }

    if not progress:
        plan["recommendation"] = "Welcome to SDE Prep. Let's assess your level with some foundational exercises."
        plan["focus_areas"] = ["Getting started"]
    elif weak:
        plan["focus_areas"] = [w['concept_tag'] for w in weak]
        w = weak[0]
        mastery = w.get('mastery_level', 'learning')
        plan["recommendation"] = (
            f"Focus on '{w['concept_tag']}' — currently at {mastery} level "
            f"(avg score: {w['avg_score']:.0f}%). Let's push this to proficient."
        )
    else:
        plan["recommendation"] = "Strong progress! Time to tackle harder scenarios and edge cases."
        plan["focus_areas"] = ["Level up!"]

    return plan
