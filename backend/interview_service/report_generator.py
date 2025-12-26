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
    
    The score is calculated as:
    - Base score: Average of all evaluation scores
    - Completion factor: Multiplied by completion ratio (questions answered / expected)
    - Minimum threshold: At least 80% completion for full score consideration
    
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
    
    # Base score: Average of all answer evaluations
    base_score = sum(all_scores) / len(all_scores)
    
    # Calculate completion ratio
    questions_answered = len(state.questions_asked)
    expected_questions = state.total_questions or 15
    completion_ratio = min(1.0, questions_answered / expected_questions) if expected_questions > 0 else 0.0
    
    # Apply completion factor: Score is multiplied by completion ratio
    # This ensures that answering 2/15 questions correctly doesn't give 85%
    # Instead, if you answered 2/15 (13% completion) and got perfect scores,
    # your overall score would be: base_score * 0.13
    adjusted_score = base_score * completion_ratio
    
    # Additional penalty for very incomplete interviews
    # If less than 50% complete, apply additional penalty
    if completion_ratio < 0.5:
        # Cap at 60% of base score for very incomplete interviews
        adjusted_score = min(adjusted_score, base_score * 0.6)
    elif completion_ratio < 0.75:
        # Cap at 80% of base score for partially complete interviews
        adjusted_score = min(adjusted_score, base_score * 0.8)
    
    # Ensure score doesn't exceed base_score (can't get more than 100% of what you answered)
    final_score = min(adjusted_score, base_score)
    
    logger.info(f"📊 Score calculation: base={base_score:.2f}, completion={completion_ratio:.2f} ({questions_answered}/{expected_questions}), final={final_score:.2f}")
    
    return final_score


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
        
        # Determine completion status FIRST
        questions_answered = len(state.questions_asked)
        expected_questions = state.total_questions or 10
        
        # CRITICAL: If no questions answered, return a "no assessment" report
        if questions_answered == 0:
            logger.warning(f"⚠️ No questions answered for interview {interview_id}. Generating 'no assessment' report.")
            report_data = {
                "overall_score": None,  # No score when no questions answered
                "section_scores": {},
                "skill_scores": {},
                "strengths": [],
                "weaknesses": ["No interview questions were answered. Cannot provide assessment."],
                "detailed_feedback": "This interview was started but no questions were answered. A comprehensive assessment cannot be provided without interview responses. Please complete an interview to receive a detailed performance report.",
                "recommendation": "no_assessment",
                "improvement_suggestions": [
                    "Complete a full interview to receive an accurate assessment",
                    "Answer all interview questions to get detailed feedback on your performance"
                ],
                "interview_id": interview_id,
                "role": state.role.value,
                "total_questions": expected_questions,
                "questions_answered": 0,
                "is_complete": False,
                "completion_percentage": 0,
                "completion_warning": "No questions were answered. This report contains no assessment data.",
                "coding_performance": {
                    "total_coding_questions": 0,
                    "coding_questions_solved": 0,
                    "success_rate": 0,
                    "by_difficulty": {
                        "easy": {"attempted": 0, "solved": 0},
                        "medium": {"attempted": 0, "solved": 0},
                        "hard": {"attempted": 0, "solved": 0}
                    }
                },
                "questions": [],
                "answers": [],
                "interview_duration": (state.completed_at - state.started_at).total_seconds() / 60 if (state.completed_at and state.started_at) else 0,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Store report in Firestore
            report_id = str(uuid.uuid4())
            report_doc = {
                "report_id": report_id,
                "interview_id": interview_id,
                "user_id": state.user_id,
                "role": state.role.value,
                "report_data": report_data,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "overall_score": None  # No score
            }
            
            success = await firestore_client.set_document(
                "reports",
                report_id,
                report_doc
            )
            
            if not success:
                logger.error(f"Failed to save 'no assessment' report to Firestore for interview: {interview_id}")
                return None
            
            # Update interview state with report_id
            from interview_service.interview_state import update_interview_state
            await update_interview_state(interview_id, {"report_id": report_id})
            
            logger.info(f"✅ 'No assessment' report generated and stored: {report_id} for interview: {interview_id}")
            return report_data
        
        # Build transcript (only if questions were answered)
        transcript = build_interview_transcript(state)
        questions, answers = extract_questions_and_answers(state)
        
        # Calculate scores
        skill_scores = calculate_skill_scores(state)
        overall_score = calculate_overall_score(state)
        coding_performance = calculate_coding_performance(state)
        
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
        
        # Add completion warning only if significantly incomplete (< 80% complete)
        completion_percentage = (questions_answered / expected_questions * 100) if expected_questions > 0 else 0
        if completion_percentage < 80:
            report_data["completion_warning"] = f"This is a partial assessment based on {questions_answered} of {expected_questions} expected questions."
        
        # Only include skill scores that were actually assessed
        report_data["skill_scores"] = {skill: float(score) for skill, score in skill_scores.items()}
        
        # Clean up section_scores: Remove any scores for skills that weren't actually assessed
        # Only keep section_scores that correspond to skills in skill_scores
        if "section_scores" in report_data:
            # Get list of actually assessed skills (normalized to lowercase for comparison)
            assessed_skills_lower = {skill.lower() for skill in skill_scores.keys()}
            
            # Filter section_scores to only include skills that were actually assessed
            # Map common section names to skill names
            section_to_skill_map = {
                "technical": ["technical", "programming", "coding", "development"],
                "communication": ["communication", "verbal", "presentation"],
                "problem_solving": ["problem solving", "problem-solving", "algorithm", "logic"]
            }
            
            filtered_section_scores = {}
            for section_name, section_value in report_data.get("section_scores", {}).items():
                # Check if this section corresponds to an assessed skill
                section_lower = section_name.lower()
                should_include = False
                
                # Direct match
                if section_lower in assessed_skills_lower:
                    should_include = True
                # Check mapped skills
                elif section_lower in section_to_skill_map:
                    mapped_skills = section_to_skill_map[section_lower]
                    if any(mapped_skill in assessed_skills_lower for mapped_skill in mapped_skills):
                        should_include = True
                
                # Only include if it was actually assessed
                if should_include:
                    filtered_section_scores[section_name] = section_value
            
            # If no section scores match assessed skills, use skill_scores directly
            if not filtered_section_scores and skill_scores:
                # Create section_scores from actual skill_scores (only for skills that were assessed)
                for skill, score in skill_scores.items():
                    # Normalize skill name to section name
                    skill_lower = skill.lower()
                    if "communication" in skill_lower or "verbal" in skill_lower:
                        filtered_section_scores["communication"] = int(score * 100)
                    elif "problem" in skill_lower or "algorithm" in skill_lower or "logic" in skill_lower:
                        filtered_section_scores["problem_solving"] = int(score * 100)
                    elif "technical" in skill_lower or "programming" in skill_lower or "coding" in skill_lower:
                        filtered_section_scores["technical"] = int(score * 100)
                    else:
                        # Use skill name as section name
                        filtered_section_scores[skill] = int(score * 100)
            
            report_data["section_scores"] = filtered_section_scores
        
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

