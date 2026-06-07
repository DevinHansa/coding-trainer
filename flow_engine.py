"""Flow state engine — adaptive difficulty, XP, and gamification with user-specific context."""
from config import (
    FLOW_FAST_SOLVE_RATIO, FLOW_FAIL_THRESHOLD, FLOW_STREAK_BONUS, LADDER_RANKS
)
from database import get_flow_state


def get_adaptive_difficulty(user_id, category=None):
    """Determine the next difficulty level based on flow state for a user."""
    flow = get_flow_state(user_id)
    current = flow.get("current_difficulty", 1)
    passes = flow.get("consecutive_passes", 0)
    fails = flow.get("consecutive_fails", 0)

    # Ramp up on consistent passes
    if passes >= 3 and current < 4:
        return min(current + 1, 4)

    # Drop down on repeated failures
    if fails >= FLOW_FAIL_THRESHOLD and current > 1:
        return max(current - 1, 1)

    return current


def should_trigger_mcq_drill(user_id, category=None):
    """Check if we should interrupt with an MCQ drill for a user."""
    flow = get_flow_state(user_id)
    return flow.get("consecutive_fails", 0) >= FLOW_FAIL_THRESHOLD


def calculate_xp_earned(score, consecutive_passes):
    """Calculate XP earned for a submission."""
    if score < 70:
        return max(score // 5, 0)  # Partial XP for effort
    xp = score
    if consecutive_passes >= FLOW_STREAK_BONUS:
        xp = int(xp * 1.5)
    return xp


def get_current_rank(total_xp):
    """Determine rank from XP."""
    current = "associate_de"
    for key, info in sorted(LADDER_RANKS.items(), key=lambda x: x[1]['xp'], reverse=True):
        if total_xp >= info['xp']:
            current = key
            break
    return current


def get_rank_info(total_xp):
    """Get full rank info including progress to next."""
    current_key = get_current_rank(total_xp)
    current_info = LADDER_RANKS[current_key]

    # Find next rank
    sorted_ranks = sorted(LADDER_RANKS.items(), key=lambda x: x[1]['xp'])
    next_rank = None
    for key, info in sorted_ranks:
        if info['xp'] > total_xp:
            next_rank = info
            break

    progress_pct = 100
    xp_to_next = 0
    if next_rank:
        range_total = next_rank['xp'] - current_info['xp']
        xp_in_range = total_xp - current_info['xp']
        progress_pct = min(100, int((xp_in_range / max(range_total, 1)) * 100))
        xp_to_next = next_rank['xp'] - total_xp

    return {
        "rank_key": current_key,
        "label": current_info['label'],
        "icon": current_info['icon'],
        "total_xp": total_xp,
        "progress_pct": progress_pct,
        "xp_to_next": xp_to_next,
        "next_rank": next_rank['label'] if next_rank else "MAX RANK",
    }
