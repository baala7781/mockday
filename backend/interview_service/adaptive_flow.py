"""Adaptive interview flow logic."""
from typing import Optional, List, Dict
from interview_service.models import (
    InterviewState, Question, SkillWeight, DifficultyLevel,
    QuestionType
)
from interview_service.question_generator import generate_question
from interview_service.skill_weighting import distribute_questions


async def select_next_question(
    state: InterviewState,
    question_distribution: Optional[Dict[str, int]] = None
) -> Optional[Question]:
    """
    Select the next question based on adaptive logic.
    
    Args:
        state: Current interview state
        question_distribution: Pre-calculated question distribution
        
    Returns:
        Next question or None if interview should be completed
    """
    # Check if interview is complete
    if state.total_questions >= state.max_questions:
        return None
    
    # Calculate question distribution if not provided
    if not question_distribution:
        question_distribution = distribute_questions(
            state.skill_weights,
            state.max_questions
        )
    
    # Get skills that need more questions
    skills_needing_questions = []
    for skill_weight in state.skill_weights:
        skill = skill_weight.skill
        expected_questions = question_distribution.get(skill, 0)
        answered_count = len(state.answered_skills.get(skill, []))
        
        if answered_count < expected_questions:
            skills_needing_questions.append({
                "skill": skill,
                "weight": skill_weight.weight,
                "remaining": expected_questions - answered_count
            })
    
    if not skills_needing_questions:
        # All skills covered, focus on weak areas or increase difficulty
        return await select_follow_up_question(state)
    
    # Select skill with highest weight that needs questions
    target_skill_data = max(
        skills_needing_questions,
        key=lambda x: x["weight"]
    )
    target_skill = target_skill_data["skill"]
    
    # Determine difficulty based on previous answers for this skill
    difficulty = state.current_difficulty
    if target_skill in state.answered_skills:
        # Check previous answers for this skill
        previous_answers = state.answered_skills[target_skill]
        if previous_answers:
            last_score = previous_answers[-1].score
            if last_score >= 0.8:
                difficulty = min(difficulty.value + 1, 4)
            elif last_score < 0.6:
                difficulty = max(difficulty.value - 1, 1)
            difficulty = DifficultyLevel(difficulty)
    
    # Determine question type based on difficulty
    question_type = None
    if difficulty <= 2:
        question_type = QuestionType.CONCEPTUAL
    elif difficulty == 3:
        question_type = QuestionType.PRACTICAL
    else:
        # For advanced, use system design or coding
        question_type = QuestionType.SYSTEM_DESIGN
    
    # Get previous questions for context
    previous_questions = [q.question for q in state.questions_asked[-5:]]
    
    # Get previous answers for context
    previous_answers = []
    for skill, evaluations in state.answered_skills.items():
        for eval in evaluations:
            # Add a summary of the answer (we don't store full answers)
            previous_answers.append(f"Skill: {skill}, Score: {eval.score}")
    
    # Generate question
    question = await generate_question(
        skill=target_skill,
        difficulty=difficulty,
        role=state.role.value,
        resume_data=state.resume_data,
        question_type=question_type,
        previous_questions=previous_questions,
        previous_answers=previous_answers[-3:] if previous_answers else None
    )
    
    return question


async def select_follow_up_question(state: InterviewState) -> Optional[Question]:
    """
    Select a follow-up question when all skills are covered.
    Focus on weak areas or increase difficulty on strong areas.
    
    Args:
        state: Current interview state
        
    Returns:
        Follow-up question or None
    """
    # Find weak skills (average score < 0.6)
    weak_skills = []
    for skill, evaluations in state.answered_skills.items():
        if evaluations:
            avg_score = sum(e.score for e in evaluations) / len(evaluations)
            if avg_score < 0.6:
                weak_skills.append({
                    "skill": skill,
                    "avg_score": avg_score,
                    "weight": next(
                        (sw.weight for sw in state.skill_weights if sw.skill == skill),
                        0.0
                    )
                })
    
    if weak_skills:
        # Focus on weakest skill
        target_skill_data = min(weak_skills, key=lambda x: x["avg_score"])
        target_skill = target_skill_data["skill"]
        difficulty = DifficultyLevel.BASIC  # Start simple for weak areas
    else:
        # All skills are strong, increase difficulty on highest weight skill
        target_skill_data = max(state.skill_weights, key=lambda x: x.weight)
        target_skill = target_skill_data.skill
        difficulty = min(state.current_difficulty.value + 1, 4)
        difficulty = DifficultyLevel(difficulty)
    
    # Generate question
    previous_questions = [q.question for q in state.questions_asked[-5:]]
    
    question = await generate_question(
        skill=target_skill,
        difficulty=difficulty,
        role=state.role.value,
        resume_data=state.resume_data,
        previous_questions=previous_questions
    )
    
    return question


def calculate_progress(state: InterviewState) -> Dict[str, any]:
    """
    Calculate interview progress.
    
    Args:
        state: Interview state
        
    Returns:
        Progress dictionary
    """
    total_skills = len(state.skill_weights)
    covered_skills = len(state.answered_skills)
    
    # Calculate skill coverage
    skill_coverage = {}
    for skill_weight in state.skill_weights:
        skill = skill_weight.skill
        evaluations = state.answered_skills.get(skill, [])
        if evaluations:
            avg_score = sum(e.score for e in evaluations) / len(evaluations)
            skill_coverage[skill] = {
                "questions_asked": len(evaluations),
                "average_score": avg_score,
                "status": "strong" if avg_score >= 0.8 else "moderate" if avg_score >= 0.6 else "weak"
            }
        else:
            skill_coverage[skill] = {
                "questions_asked": 0,
                "average_score": 0.0,
                "status": "not_covered"
            }
    
    # Calculate phase progress
    phase_progress = {
        "current_phase": state.current_phase.value,
        "phase_questions": state.phase_questions,
        "projects_answered": len(state.answered_projects)
    }
    
    return {
        "total_questions": state.total_questions,
        "max_questions": state.max_questions,
        "progress_percentage": (state.total_questions / state.max_questions) * 100,
        "skills_covered": covered_skills,
        "total_skills": total_skills,
        "skill_coverage": skill_coverage,
        "current_difficulty": state.current_difficulty.value,
        "status": state.status.value,
        "phase": phase_progress
    }

