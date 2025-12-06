"""Smoothed difficulty progression with moving averages."""
from typing import List, Optional
from interview_service.models import DifficultyLevel, Evaluation, InterviewState
import logging

logger = logging.getLogger(__name__)


def calculate_moving_average_scores(
    evaluations: List[Evaluation],
    window_size: int = 3
) -> float:
    """
    Calculate moving average of last N evaluation scores.
    
    Args:
        evaluations: List of evaluations
        window_size: Number of recent evaluations to consider
        
    Returns:
        Moving average score (0.0-1.0)
    """
    if not evaluations:
        return 0.5  # Default neutral score
    
    recent_scores = [e.score for e in evaluations[-window_size:]]
    return sum(recent_scores) / len(recent_scores)


def calculate_smoothed_difficulty(
    current_difficulty: DifficultyLevel,
    recent_evaluations: List[Evaluation],
    window_size: int = 3,
    min_change_interval: int = 2
) -> DifficultyLevel:
    """
    Calculate difficulty with smoothed progression.
    
    Uses moving average of last N scores and clamps changes to prevent jumps.
    
    Args:
        current_difficulty: Current difficulty level
        recent_evaluations: Recent evaluations (last N)
        window_size: Number of evaluations for moving average
        min_change_interval: Minimum questions between difficulty changes
        
    Returns:
        New difficulty level
    """
    if not recent_evaluations:
        return current_difficulty
    
    # Calculate moving average
    avg_score = calculate_moving_average_scores(recent_evaluations, window_size)
    
    # Determine difficulty change based on smoothed score
    current_value = current_difficulty.value
    
    if avg_score >= 0.8:
        # Excellent performance: increase difficulty
        new_difficulty = min(current_value + 1, 4)
    elif avg_score >= 0.6:
        # Good performance: maintain or slight increase
        new_difficulty = current_value
    elif avg_score >= 0.4:
        # Fair performance: maintain or slight decrease
        new_difficulty = max(current_value - 1, 1)
    else:
        # Poor performance: decrease difficulty
        new_difficulty = max(current_value - 1, 1)
    
    # Clamp: max change of ±1 per adjustment
    change = new_difficulty - current_value
    if abs(change) > 1:
        new_difficulty = current_value + (1 if change > 0 else -1)
    
    # Ensure bounds
    new_difficulty = max(1, min(4, new_difficulty))
    
    logger.debug(f"Difficulty adjustment: {current_value} -> {new_difficulty} (avg_score: {avg_score:.2f}, evaluations: {len(recent_evaluations)})")
    
    return DifficultyLevel(new_difficulty)


def get_recent_evaluations_for_skill(
    state: InterviewState,
    skill: Optional[str] = None,
    window_size: int = 3
) -> List[Evaluation]:
    """
    Get recent evaluations for a skill or across all skills.
    
    Args:
        state: Interview state
        skill: Specific skill (if None, uses all skills)
        window_size: Number of recent evaluations to return
        
    Returns:
        List of recent evaluations
    """
    all_evaluations = []
    
    if skill:
        # Get evaluations for specific skill
        if skill in state.answered_skills:
            all_evaluations.extend(state.answered_skills[skill])
    else:
        # Get evaluations from all skills
        for skill_name, evaluations in state.answered_skills.items():
            all_evaluations.extend(evaluations)
        # Also include project evaluations
        for project_name, evaluations in state.answered_projects.items():
            all_evaluations.extend(evaluations)
    
    # Sort by recency (assuming last in list is most recent)
    # Return last N
    return all_evaluations[-window_size:]

