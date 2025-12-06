"""Conversation Memory Controller - Limits context to prevent LLM fatigue and hallucinations."""
from typing import Optional, List, Dict, Any
from interview_service.models import InterviewState, Question, Answer, Evaluation, ResumeData
import logging

logger = logging.getLogger(__name__)


def create_resume_summary(resume_data: Optional[ResumeData], max_words: int = 80) -> str:
    """
    Create a very short summary of candidate background (50-80 words).
    
    Args:
        resume_data: Resume data
        max_words: Maximum words in summary
        
    Returns:
        Concise summary string
    """
    if not resume_data:
        return "Candidate background not provided."
    
    summary_parts = []
    word_count = 0
    
    # Add top skills (limit to 3-4)
    if resume_data.skills:
        top_skills = [s.name for s in resume_data.skills[:4]]
        skills_text = f"Skills: {', '.join(top_skills)}"
        summary_parts.append(skills_text)
        word_count += len(skills_text.split())
    
    # Add top projects (limit to 2)
    if resume_data.projects and word_count < max_words - 20:
        top_projects = [p.name for p in resume_data.projects[:2]]
        projects_text = f"Projects: {', '.join(top_projects)}"
        summary_parts.append(projects_text)
        word_count += len(projects_text.split())
    
    # Add recent experience (limit to 1)
    if resume_data.experience and word_count < max_words - 15:
        latest_exp = resume_data.experience[0]
        exp_text = f"Experience: {latest_exp.role} at {latest_exp.company}"
        summary_parts.append(exp_text)
        word_count += len(exp_text.split())
    
    summary = ". ".join(summary_parts)
    
    # Ensure we don't exceed max_words
    words = summary.split()
    if len(words) > max_words:
        summary = " ".join(words[:max_words]) + "..."
    
    return summary if summary else "Candidate background not provided."


def get_last_question_answer_pair(state: InterviewState) -> Optional[Dict[str, str]]:
    """
    Get only the last question-answer pair (not full history).
    
    Args:
        state: Interview state
        
    Returns:
        Dict with 'question' and 'answer' keys, or None if no previous QA
    """
    if not state.questions_asked or len(state.questions_asked) == 0:
        return None
    
    # Get the last question
    last_question = state.questions_asked[-1]
    
    # Find the answer for this question (from answered_skills or answered_projects)
    last_answer = None
    
    # Check answered_skills
    if last_question.skill in state.answered_skills:
        evaluations = state.answered_skills[last_question.skill]
        if evaluations:
            # Get the last evaluation's feedback as a proxy for the answer quality
            # Note: We don't store the actual answer text, so we use feedback summary
            last_eval = evaluations[-1]
            last_answer = f"[Previous answer scored {last_eval.score:.2f}/1.0. {last_eval.feedback[:100]}...]"
    
    # Check answered_projects
    if not last_answer and last_question.context and last_question.context.get("project"):
        project_name = last_question.context.get("project")
        if project_name in state.answered_projects:
            evaluations = state.answered_projects[project_name]
            if evaluations:
                last_eval = evaluations[-1]
                last_answer = f"[Previous answer scored {last_eval.score:.2f}/1.0. {last_eval.feedback[:100]}...]"
    
    if not last_answer:
        return None
    
    return {
        "question": last_question.question,
        "answer": last_answer
    }


def get_last_two_question_answer_pairs(state: InterviewState) -> List[Dict[str, str]]:
    """
    Get the last 2 question-answer pairs for context.
    
    Args:
        state: Interview state
        
    Returns:
        List of dicts with 'question' and 'answer' keys (up to 2 items)
    """
    if not state.questions_asked or len(state.questions_asked) == 0:
        return []
    
    # Get last 2 questions
    last_questions = state.questions_asked[-2:] if len(state.questions_asked) >= 2 else state.questions_asked
    
    qa_pairs = []
    for question in last_questions:
        last_answer = None
        
        # Check answered_skills
        if question.skill in state.answered_skills:
            evaluations = state.answered_skills[question.skill]
            if evaluations:
                last_eval = evaluations[-1]
                last_answer = f"[Scored {last_eval.score:.2f}/1.0. {last_eval.feedback[:80]}...]"
        
        # Check answered_projects
        if not last_answer and question.context and question.context.get("project"):
            project_name = question.context.get("project")
            if project_name in state.answered_projects:
                evaluations = state.answered_projects[project_name]
                if evaluations:
                    last_eval = evaluations[-1]
                    last_answer = f"[Scored {last_eval.score:.2f}/1.0. {last_eval.feedback[:80]}...]"
        
        if last_answer:
            qa_pairs.append({
                "question": question.question,
                "answer": last_answer
            })
    
    return qa_pairs


def get_conversation_context_for_question(
    state: InterviewState,
    skill: str,
    resume_data: Optional[ResumeData] = None
) -> Dict[str, Any]:
    """
    Get minimal conversation context for question generation.
    
    Returns only:
    - Last 2 questions (if any)
    - Last 2 answer summaries (if any)
    - Very short resume summary (50-80 words)
    
    Args:
        state: Interview state
        skill: Current skill being assessed
        resume_data: Resume data (optional, will use state.resume_data if not provided)
        
    Returns:
        Dict with 'previous_questions' (list), 'previous_answers' (list), 'resume_summary'
    """
    resume_data = resume_data or state.resume_data
    
    # Get resume summary (very short)
    resume_summary = create_resume_summary(resume_data, max_words=80)
    
    # Get last 2 QA pairs
    last_qa_pairs = get_last_two_question_answer_pairs(state)
    
    previous_questions = [qa["question"] for qa in last_qa_pairs]
    previous_answers = [qa["answer"] for qa in last_qa_pairs]
    
    return {
        "previous_questions": previous_questions,
        "previous_answers": previous_answers,
        "resume_summary": resume_summary
    }


def get_conversation_context_for_evaluation(
    state: InterviewState,
    question: Question,
    answer: Answer
) -> Dict[str, Any]:
    """
    Get minimal context for answer evaluation.
    
    Returns only:
    - Last evaluation score (if any) - just the number, not full history
    
    Args:
        state: Interview state
        question: Current question
        answer: Current answer
        
    Returns:
        Dict with 'last_score' (optional)
    """
    # Get last evaluation score for this skill (if exists)
    last_score = None
    if question.skill in state.answered_skills:
        evaluations = state.answered_skills[question.skill]
        if evaluations:
            last_score = evaluations[-1].score
    
    # If not found in skills, check projects
    if last_score is None and question.context and question.context.get("project"):
        project_name = question.context.get("project")
        if project_name in state.answered_projects:
            evaluations = state.answered_projects[project_name]
            if evaluations:
                last_score = evaluations[-1].score
    
    return {
        "last_score": last_score
    }


def get_relevant_resume_context_for_skill(
    resume_data: Optional[ResumeData],
    skill: str,
    max_projects: int = 2,
    max_experience: int = 1
) -> str:
    """
    Get only relevant resume context for a specific skill (very limited).
    
    Args:
        resume_data: Resume data
        skill: Skill to get context for
        max_projects: Maximum projects to include
        max_experience: Maximum experience entries to include
        
    Returns:
        Short context string (50-80 words max)
    """
    if not resume_data:
        return "Not provided"
    
    skill_lower = skill.lower()
    context_parts = []
    word_count = 0
    
    # Find relevant projects (limit to 2)
    if resume_data.projects:
        relevant_projects = [
            p for p in resume_data.projects[:max_projects]
            if any(skill_lower in tech.lower() or tech.lower() in skill_lower 
                   for tech in (p.technologies or []))
        ]
        if relevant_projects:
            project_names = [p.name for p in relevant_projects]
            projects_text = f"Projects using {skill}: {', '.join(project_names)}"
            context_parts.append(projects_text)
            word_count += len(projects_text.split())
    
    # Find relevant experience (limit to 1)
    if resume_data.experience and word_count < 60:
        relevant_experience = [
            e for e in resume_data.experience[:max_experience]
            if any(skill_lower in s.lower() or s.lower() in skill_lower 
                   for s in (e.skills_used or []))
        ]
        if relevant_experience:
            exp = relevant_experience[0]
            exp_text = f"Used {skill} as {exp.role} at {exp.company}"
            context_parts.append(exp_text)
            word_count += len(exp_text.split())
    
    context = ". ".join(context_parts)
    
    # Ensure we don't exceed ~80 words
    words = context.split()
    if len(words) > 80:
        context = " ".join(words[:80]) + "..."
    
    return context if context else "Not provided"

