"""Flow decision logic - human-like interview behavior (decoupled from scoring)."""
from typing import Optional
from interview_service.models import AnswerQuality, NextAction, DifficultyLevel, QuestionType
import logging

logger = logging.getLogger(__name__)


def categorize_answer(score: float, answer_text: str, question_type: QuestionType) -> AnswerQuality:
    """
    Categorize answer into quality bucket for flow decisions.
    
    Args:
        score: Numeric score (0.0-1.0)
        answer_text: Answer text (for detecting "no idea" signals)
        question_type: Question type
        
    Returns:
        AnswerQuality bucket
    """
    answer_lower = answer_text.lower()
    
    # Check for explicit "no idea" signals
    no_idea_phrases = [
        "don't know", "no idea", "not sure", "haven't worked",
        "never used", "unfamiliar", "haven't tried", "i don't know",
        "idk", "not familiar", "don't have experience"
    ]
    
    has_no_idea_signal = any(phrase in answer_lower for phrase in no_idea_phrases)
    
    # Strong signal: explicit "no idea" + low score
    if has_no_idea_signal and score < 0.5:
        return AnswerQuality.NO_IDEA
    
    # Bucket based on score
    if score < 0.3:
        return AnswerQuality.NO_IDEA
    elif score < 0.6:
        return AnswerQuality.PARTIAL
    elif score < 0.8:
        return AnswerQuality.GOOD
    else:
        return AnswerQuality.STRONG


def decide_next_action(
    quality: AnswerQuality,
    consecutive_stuck: int = 0
) -> NextAction:
    """
    Decide next action based on answer quality (human-like interview behavior).
    
    Args:
        quality: Answer quality bucket
        consecutive_stuck: Number of consecutive NO_IDEA answers (for topic switching)
        
    Returns:
        NextAction to take
    """
    if quality == AnswerQuality.NO_IDEA:
        # If stuck multiple times, switch topic (don't drill)
        if consecutive_stuck >= 1:
            logger.info(f"🔄 Candidate stuck ({consecutive_stuck} times), switching topic")
            return NextAction.SWITCH_TOPIC
        # Single "no idea" → move on (don't follow up)
        return NextAction.CONTINUE
    
    elif quality == AnswerQuality.PARTIAL:
        # Partial answer → follow up for clarification
        logger.info("🔄 Partial answer detected, following up")
        return NextAction.FOLLOW_UP
    
    elif quality == AnswerQuality.GOOD:
        # Good answer → continue to next question
        return NextAction.CONTINUE
    
    else:  # STRONG
        # Strong answer → increase difficulty
        logger.info("⬆️ Strong answer, increasing difficulty")
        return NextAction.INCREASE_DIFFICULTY

