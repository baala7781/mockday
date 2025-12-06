"""Report generation for completed interviews."""
from typing import Dict, Any, Optional, List
from interview_service.models import InterviewState, Evaluation
from shared.providers.gemini_client import gemini_client
from shared.db.firestore_client import firestore_client
from datetime import datetime, timezone
import uuid
import logging

logger = logging.getLogger(__name__)


def build_interview_transcript(state: InterviewState) -> str:
    """
    Build interview transcript from state.
    
    Args:
        state: Interview state
        
    Returns:
        Transcript string
    """
    transcript_parts = []
    
    # Use conversation_history if available (most accurate)
    if state.conversation_history:
        for qa_pair in state.conversation_history:
            question = qa_pair.get("question", "")
            answer = qa_pair.get("answer", "")
            if question and answer:
                transcript_parts.append(f"Interviewer: {question}")
                transcript_parts.append(f"Candidate: {answer}")
    
    # Fallback: Build from questions_asked and answered_skills
    # Match questions with their evaluations to reconstruct answers
    if not transcript_parts and state.questions_asked:
        # Get all evaluations in order
        all_evaluations = []
        for skill, evals in state.answered_skills.items():
            all_evaluations.extend(evals)
        
        # Match questions with evaluations (approximate - by index)
        for i, question in enumerate(state.questions_asked):
            transcript_parts.append(f"Interviewer: {question.question}")
            # Try to get corresponding evaluation
            if i < len(all_evaluations):
                eval_obj = all_evaluations[i]
                # Use feedback as answer summary if available
                if hasattr(eval_obj, 'feedback'):
                    transcript_parts.append(f"Candidate: [Answer evaluated - {eval_obj.feedback[:100]}...]")
                else:
                    transcript_parts.append(f"Candidate: [Answer provided]")
            else:
                transcript_parts.append(f"Candidate: [Answer provided]")
    
    return "\n\n".join(transcript_parts) if transcript_parts else "No transcript available."


def extract_questions_and_answers(state: InterviewState) -> tuple[List[str], List[str]]:
    """
    Extract questions and answers from interview state.
    
    Args:
        state: Interview state
        
    Returns:
        Tuple of (questions list, answers list)
    """
    questions = []
    answers = []
    
    # Use conversation_history if available
    if state.conversation_history:
        for qa_pair in state.conversation_history:
            question = qa_pair.get("question", "")
            answer = qa_pair.get("answer", "")
            if question:
                questions.append(question)
            if answer:
                answers.append(answer)
    
    # Fallback: Extract from questions_asked
    if not questions and state.questions_asked:
        questions = [q.question for q in state.questions_asked]
        # Answers are harder to reconstruct - use evaluation feedback as summary
        for skill, evals in state.answered_skills.items():
            for eval_obj in evals:
                if hasattr(eval_obj, 'feedback'):
                    answers.append(f"[{skill}] {eval_obj.feedback[:200]}")
    
    return questions, answers


def calculate_skill_scores(state: InterviewState) -> Dict[str, float]:
    """
    Calculate average scores per skill from evaluations.
    
    Args:
        state: Interview state
        
    Returns:
        Dictionary mapping skill to average score
    """
    skill_scores = {}
    
    for skill, evals in state.answered_skills.items():
        if evals:
            avg_score = sum(e.score for e in evals) / len(evals)
            skill_scores[skill] = avg_score
    
    return skill_scores


def calculate_coding_performance(state: InterviewState) -> Dict[str, Any]:
    """
    Calculate coding-specific performance metrics.
    
    Args:
        state: Interview state
        
    Returns:
        Dictionary with coding performance data
    """
    from interview_service.models import QuestionType
    
    coding_questions = [q for q in state.questions_asked if q.type == QuestionType.CODING]
    
    if not coding_questions:
        return {
            "total_coding_questions": 0,
            "coding_questions_solved": 0,
            "success_rate": 0.0,
            "by_difficulty": {}
        }
    
    # Get evaluations for coding questions
    total_attempted = len(coding_questions)
    solved_count = 0
    difficulty_breakdown = {"easy": {"attempted": 0, "solved": 0}, "medium": {"attempted": 0, "solved": 0}, "hard": {"attempted": 0, "solved": 0}}
    
    for question in coding_questions:
        # Find corresponding evaluation
        skill = question.skill
        if skill in state.answered_skills:
            # Get evaluation for this question (approximate match by timing)
            for eval_obj in state.answered_skills[skill]:
                # Consider solved if score >= 0.6
                if eval_obj.score >= 0.6:
                    solved_count += 1
                    break
        
        # Track by difficulty
        difficulty_level = question.difficulty.value
        if difficulty_level <= 2:
            diff_key = "easy"
        elif difficulty_level == 3:
            diff_key = "medium"
        else:
            diff_key = "hard"
        
        difficulty_breakdown[diff_key]["attempted"] += 1
        if skill in state.answered_skills:
            for eval_obj in state.answered_skills[skill]:
                if eval_obj.score >= 0.6:
                    difficulty_breakdown[diff_key]["solved"] += 1
                    break
    
    success_rate = (solved_count / total_attempted) if total_attempted > 0 else 0.0
    
    return {
        "total_coding_questions": total_attempted,
        "coding_questions_solved": solved_count,
        "success_rate": round(success_rate * 100, 1),
        "by_difficulty": difficulty_breakdown
    }


def calculate_overall_score(state: InterviewState) -> float:
    """
    Calculate overall interview score with completion penalty.
    
    Args:
        state: Interview state
        
    Returns:
        Overall score (0.0 to 1.0)
    """
    all_scores = []
    
    for skill, evals in state.answered_skills.items():
        for eval_obj in evals:
            all_scores.append(eval_obj.score)
    
    if not all_scores:
        return 0.0
    
    raw_score = sum(all_scores) / len(all_scores)
    
    # Apply completion penalty for incomplete interviews
    questions_answered = len(state.questions_asked)
    expected_questions = state.total_questions or 10
    completion_ratio = min(1.0, questions_answered / expected_questions)
    
    # If interview is less than 50% complete, cap score at 60%
    if completion_ratio < 0.5:
        raw_score = min(raw_score, 0.60)
    # If interview is less than 75% complete, cap score at 75%
    elif completion_ratio < 0.75:
        raw_score = min(raw_score, 0.75)
    
    return raw_score


async def generate_interview_report(
    interview_id: str,
    state: InterviewState,
    user_profile: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Generate comprehensive interview report.
    
    Args:
        interview_id: Interview ID
        state: Interview state
        user_profile: Optional user profile data
        
    Returns:
        Report dictionary or None on failure
    """
    try:
        logger.info(f"📊 Generating report for interview: {interview_id}")
        
        # Build transcript
        transcript = build_interview_transcript(state)
        questions, answers = extract_questions_and_answers(state)
        
        # Calculate scores
        skill_scores = calculate_skill_scores(state)
        overall_score = calculate_overall_score(state)
        coding_performance = calculate_coding_performance(state)
        
        # Determine completion status
        questions_answered = len(state.questions_asked)
        expected_questions = state.total_questions or 10
        is_complete = state.status.value == "completed" and questions_answered >= expected_questions * 0.8
        
        logger.info(f"📊 Calculated metrics - Overall: {overall_score:.2f}, Skills: {len(skill_scores)}, Coding: {coding_performance['total_coding_questions']} questions")
        logger.info(f"📊 Interview completion: {questions_answered}/{expected_questions} questions ({questions_answered/expected_questions*100:.0f}%), is_complete={is_complete}")
        
        # Generate report using LLM with completion context
        report_data = await gemini_client.generate_report(
            interview_transcript=transcript,
            questions=questions,
            answers=answers,
            role=state.role.value,
            user_profile=user_profile,
            is_complete=is_complete,
            expected_questions=expected_questions,
            actual_questions=questions_answered
        )
        
        if not report_data:
            logger.warning("LLM report generation returned None, creating fallback report")
            # Create fallback report with realistic scoring
            base_score = int(overall_score * 100)
            # Cap score based on completion
            if questions_answered < expected_questions * 0.5:
                base_score = min(base_score, 55)
                recommendation = "no_hire"
                detailed = f"Interview was incomplete ({questions_answered}/{expected_questions} questions). Cannot make a full assessment."
            elif questions_answered < expected_questions * 0.75:
                base_score = min(base_score, 70)
                recommendation = "maybe"
                detailed = f"Interview was partially complete ({questions_answered}/{expected_questions} questions). Limited assessment available."
            else:
                recommendation = "maybe" if base_score < 70 else "hire"
                detailed = "Interview completed. Performance was assessed across all areas."
            
            report_data = {
                "overall_score": base_score,
                "section_scores": {
                    "technical": base_score,
                    "communication": base_score,
                    "problem_solving": base_score
                },
                "strengths": ["Participated in interview"],
                "weaknesses": ["Interview was incomplete" if not is_complete else "Some areas need improvement"],
                "detailed_feedback": detailed,
                "recommendation": recommendation,
                "improvement_suggestions": ["Complete the full interview for accurate assessment", "Practice more technical questions"]
            }
        
        # Enhance report with calculated data
        report_data["interview_id"] = interview_id
        report_data["role"] = state.role.value
        report_data["total_questions"] = expected_questions
        report_data["questions_answered"] = questions_answered
        report_data["is_complete"] = is_complete
        report_data["completion_percentage"] = round(questions_answered / expected_questions * 100)
        
        # Add completion warning if incomplete
        if not is_complete:
            report_data["completion_warning"] = f"This is a partial assessment based on {questions_answered} of {expected_questions} expected questions."
        report_data["skill_scores"] = {skill: float(score) for skill, score in skill_scores.items()}
        report_data["coding_performance"] = coding_performance
        report_data["questions"] = questions
        report_data["answers"] = answers
        report_data["interview_duration"] = (state.completed_at - state.started_at).total_seconds() / 60 if (state.completed_at and state.started_at) else 0
        report_data["created_at"] = datetime.now(timezone.utc).isoformat()
        
        # Store report in Firestore
        report_id = str(uuid.uuid4())
        report_doc = {
            "report_id": report_id,
            "interview_id": interview_id,
            "user_id": state.user_id,
            "role": state.role.value,
            "report_data": report_data,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "overall_score": report_data.get("overall_score", int(overall_score * 100))
        }
        
        success = await firestore_client.set_document(
            "reports",
            report_id,
            report_doc
        )
        
        if not success:
            logger.error(f"Failed to save report to Firestore for interview: {interview_id}")
            return None
        
        # Update interview state with report_id
        from interview_service.interview_state import update_interview_state
        await update_interview_state(interview_id, {"report_id": report_id})
        
        logger.info(f"✅ Report generated and stored: {report_id} for interview: {interview_id}")
        
        return report_data
        
    except Exception as e:
        logger.error(f"Error generating report for interview {interview_id}: {e}", exc_info=True)
        return None

