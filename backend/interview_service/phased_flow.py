"""Phased interview flow: Projects -> Standout Skills -> Role Skills."""
from typing import Optional, Dict, List
from interview_service.models import (
    InterviewState, Question, InterviewPhase, DifficultyLevel,
    QuestionType, SkillWeight, Evaluation, InterviewRole
)
import logging
import random

logger = logging.getLogger(__name__)
from interview_service.question_generator import generate_question, generate_coding_question
from interview_service.question_pool import get_question_from_pool, is_common_skill
from interview_service.skill_weighting import distribute_questions
from interview_service.conversational_framing import generate_conversational_transition, get_candidate_name_safely
import uuid


def is_graduate_role(role: InterviewRole) -> bool:
    """Check if the role is a graduate position."""
    return role in [
        InterviewRole.GRADUATE,
        InterviewRole.GRADUATE_DATA_ENGINEER,
        InterviewRole.GRADUATE_DATA_SCIENTIST
    ]


def should_ask_coding_question(state: InterviewState) -> bool:
    """
    Determine if next question should be a coding question.
    For graduates: 50-60% coding questions
    For others: 20-30% coding questions
    """
    total_questions = len(state.questions_asked)
    coding_questions = sum(1 for q in state.questions_asked if q.type == QuestionType.CODING)
    
    if total_questions == 0:
        return False  # First question is always intro
    
    coding_percentage = coding_questions / total_questions if total_questions > 0 else 0
    
    if is_graduate_role(state.role):
        # Target: 50-60% coding for graduates
        target_percentage = 0.55  # Mid-point of 50-60%
        # Add randomness to avoid strict pattern
        threshold = target_percentage + random.uniform(-0.05, 0.05)
        return coding_percentage < threshold
    else:
        # Target: 20-30% coding for experienced roles
        target_percentage = 0.25
        threshold = target_percentage + random.uniform(-0.03, 0.03)
        return coding_percentage < threshold


async def generate_intro_question(state: InterviewState, candidate_name: Optional[str] = None) -> Question:
    """
    Generate a formal introduction question with name greeting.
    
    Args:
        state: Interview state
        candidate_name: Candidate's first name (optional)
        
    Returns:
        Introduction question
    """
    # Use memory controller to get minimal resume summary (50-80 words)
    from interview_service.memory_controller import create_resume_summary
    resume_context = create_resume_summary(state.resume_data, max_words=80)
    
    # Build name greeting
    name_greeting = f"Hi {candidate_name}, " if candidate_name else "Hi, "
    
    prompt = f"""You are an experienced technical interviewer conducting a {state.role.value.replace('-', ' ')} interview.

Create a formal, professional introduction question that:
1. Starts with: "{name_greeting}how are you doing today?"
2. Then asks them to briefly introduce themselves and their experience
3. Do NOT jump to projects or technical details in the first question
4. Keep it warm but professional
5. Keep it to 2-3 sentences maximum

Guidelines:
- Sound professional and welcoming
- Ask about their overall background and experience
- Do NOT ask about specific projects, technologies, or technical skills yet
- This is the first question - keep it general

Resume context (optional - use only for context, don't mention specific details):
{resume_context}

Return ONLY the final question text starting with the greeting."""

    # Retry logic: Try up to 3 times
    max_retries = 3
    question_text = None
    last_error = None
    
    for attempt in range(max_retries):
        try:
            from shared.providers.gemini_client import gemini_client
            from shared.providers.pool_manager import provider_pool_manager, ProviderType
            
            # Check if Gemini API keys are configured
            if attempt == 0:
                pool_stats = await provider_pool_manager.get_pool_stats(ProviderType.GEMINI)
                logger.info(f"🤖 [Intro Question] Gemini pool stats: {pool_stats}")
                if pool_stats["total_accounts"] == 0:
                    logger.error("❌ [Intro Question] No Gemini API keys configured! Check GEMINI_API_KEYS environment variable.")
                    break
            
            logger.info(f"🤖 [Intro Question] Attempt {attempt + 1}/{max_retries}: Generating intro question...")
            response = await gemini_client.generate_response(
                prompt=prompt,
                model="gemini-2.5-flash-lite",
                max_tokens=150,
                temperature=0.85  # Higher temperature for more variety
            )
            
            logger.info(f"🤖 [Intro Question] Attempt {attempt + 1}: LLM response length: {len(response) if response else 0}")
            
            if response and response.strip():
                question_text = response.strip()
                
                # Remove quotes if present
                if question_text.startswith('"') and question_text.endswith('"'):
                    question_text = question_text[1:-1]
                if question_text.startswith("'") and question_text.endswith("'"):
                    question_text = question_text[1:-1]
                
                # Validate the question is reasonable
                if len(question_text) > 20:
                    # Check if it contains greeting (case-insensitive)
                    greeting_found = name_greeting.lower() in question_text.lower() or "hi" in question_text.lower() or "hello" in question_text.lower()
                    if greeting_found:
                        logger.info(f"✅ [Intro Question] Successfully generated: {question_text[:80]}...")
                        break
                    else:
                        logger.warning(f"⚠️ [Intro Question] Response missing greeting: {question_text[:80]}...")
                        # Still use it if it's reasonable
                        if len(question_text) > 30:
                            logger.info(f"✅ [Intro Question] Using response without explicit greeting: {question_text[:80]}...")
                            break
                        question_text = None  # Retry
                else:
                    logger.warning(f"⚠️ [Intro Question] Response too short: {question_text}")
                    question_text = None  # Retry
            
            if not question_text:
                logger.warning(f"⚠️ [Intro Question] Attempt {attempt + 1}: Empty or invalid response from LLM")
            
        except Exception as e:
            last_error = e
            logger.error(f"❌ [Intro Question] Attempt {attempt + 1} failed: {e}", exc_info=True)
            if attempt < max_retries - 1:
                # Wait before retry (exponential backoff)
                import asyncio
                await asyncio.sleep(0.5 * (attempt + 1))
            else:
                logger.error(f"❌ [Intro Question] All {max_retries} attempts failed. Last error: {last_error}")
    
    # Only use fallback if ALL retries failed
    if not question_text:
        logger.error("❌ [Intro Question] LLM generation failed completely, using fallback with candidate name")
        if candidate_name:
            question_text = f"Hi {candidate_name}, how are you doing today? Can you tell me about yourself and your background?"
        else:
            question_text = "Hi, how are you doing today? Can you tell me about yourself and your background?"
    
    return Question(
        question_id=str(uuid.uuid4()),
        question=question_text,
        skill="Introduction",
        difficulty=DifficultyLevel.BASIC,
        type=QuestionType.CONCEPTUAL,
        context={"phase": "introduction", "source": "dynamic"}
    )


async def select_next_question_phased(
    state: InterviewState,
    last_evaluation: Optional[Evaluation] = None,
    candidate_name: Optional[str] = None
) -> Optional[Question]:
    """
    Select next question based on phased interview approach.
    
    Phases:
    0. INTRODUCTION: General introduction question (1 question)
    1. PROJECTS: Ask questions about candidate's projects (2-3 questions)
    2. STANDOUT_SKILLS: Ask about skills that demonstrate capabilities (3-4 questions)
    3. ROLE_SKILLS: Ask about skills required for the role (5-6 questions)
    
    Args:
        state: Current interview state
        
    Returns:
        Next question or None if interview complete
    """
    # Check if interview is complete (time-based: 30 minutes)
    if state.started_at:
        from datetime import datetime, timedelta
        elapsed = (datetime.utcnow() - state.started_at).total_seconds() / 60  # minutes
        if elapsed >= state.interview_duration_minutes:
            logger.info(f"Interview time limit reached: {elapsed:.1f} minutes")
            return None
    
    # Track questions per phase
    phase_count = state.phase_questions.get(state.current_phase.value, 0)
    
    # Phase 0: INTRODUCTION (1 question)
    if state.current_phase == InterviewPhase.INTRODUCTION:
        if phase_count >= 1:
            # Move to projects phase
            state.current_phase = InterviewPhase.PROJECTS
            state.phase_questions[InterviewPhase.INTRODUCTION.value] = phase_count
            return await select_next_question_phased(state)
        
        # Generate introduction question
        intro_question = await generate_intro_question(state, candidate_name)
        state.phase_questions[InterviewPhase.INTRODUCTION.value] = 1
        return intro_question
    
    # Phase 1: PROJECTS (2-3 questions)
    elif state.current_phase == InterviewPhase.PROJECTS:
        if phase_count >= 3:
            # Move to next phase
            state.current_phase = InterviewPhase.STANDOUT_SKILLS
            state.phase_questions[InterviewPhase.PROJECTS.value] = phase_count
            return await select_next_question_phased(state)
        
        # Select a project that hasn't been asked about
        asked_projects = set(state.answered_projects.keys())
        available_projects = [
            p for p in (state.resume_data.projects or [])
            if p.name not in asked_projects
        ]
        
        # If no projects available, skip to next phase
        if not available_projects:
            state.current_phase = InterviewPhase.STANDOUT_SKILLS
            state.phase_questions[InterviewPhase.PROJECTS.value] = phase_count
            return await select_next_question_phased(state)
        
        if available_projects:
            # Select project with most relevant technologies
            target_project = max(
                available_projects,
                key=lambda p: len([s for s in p.technologies if any(
                    sw.skill.lower() in s.lower() or s.lower() in sw.skill.lower()
                    for sw in state.skill_weights
                )])
            )
            
            state.current_project = target_project.name
            
            # Generate project-specific question (always dynamic, personalized)
            question = await generate_project_question(
                project=target_project,
                role=state.role.value,
                difficulty=state.current_difficulty,
                previous_questions=[q.question for q in state.questions_asked[-3:]],
                state=state
            )
            return question
        else:
            # All projects covered, move to next phase
            state.current_phase = InterviewPhase.STANDOUT_SKILLS
            return await select_next_question_phased(state)
    
    # Phase 2: STANDOUT_SKILLS (3-4 questions)
    elif state.current_phase == InterviewPhase.STANDOUT_SKILLS:
        if phase_count >= 4:
            # Move to next phase
            state.current_phase = InterviewPhase.ROLE_SKILLS
            state.phase_questions[InterviewPhase.STANDOUT_SKILLS.value] = phase_count
            return await select_next_question_phased(state)
        
        # Find standout skills (skills with high weight from resume, not yet asked)
        # Standout skills are skills that the candidate has significant experience with
        standout_skills = [
            sw for sw in state.skill_weights
            if sw.weight >= 0.5 and sw.skill not in state.answered_skills and sw.resume_experience > 0
        ]
        
        # If no standout skills with resume experience, use high-weight skills from role
        if not standout_skills:
            standout_skills = [
                sw for sw in state.skill_weights
                if sw.weight >= 0.6 and sw.skill not in state.answered_skills
            ]
        
        if not standout_skills:
            # No standout skills, move to role skills
            state.current_phase = InterviewPhase.ROLE_SKILLS
            state.phase_questions[InterviewPhase.STANDOUT_SKILLS.value] = phase_count
            return await select_next_question_phased(state)
        
        # Select highest weight standout skill (prioritize skills with resume experience)
        target_skill_data = max(
            standout_skills,
            key=lambda x: (x.resume_experience, x.weight)  # Prioritize resume experience, then weight
        )
        target_skill = target_skill_data.skill
        state.current_skill = target_skill
        
        # Determine difficulty
        difficulty = state.current_difficulty
        
        # Determine if this should be a coding question
        ask_coding = should_ask_coding_question(state)
        
        if ask_coding:
            # Adaptive difficulty for coding questions based on previous performance
            coding_difficulty = difficulty
            if target_skill in state.answered_skills:
                previous_answers = state.answered_skills[target_skill]
                if previous_answers:
                    last_score = previous_answers[-1].score
                    # If they did well on previous coding questions, increase difficulty
                    if last_score >= 0.8:
                        coding_difficulty = DifficultyLevel(min(difficulty.value + 1, 5))
                        logger.info(f"🎯 Increasing coding difficulty to {coding_difficulty.name} (previous score: {last_score})")
                    # If they struggled, decrease difficulty
                    elif last_score < 0.5:
                        coding_difficulty = DifficultyLevel(max(difficulty.value - 1, 1))
                        logger.info(f"🎯 Decreasing coding difficulty to {coding_difficulty.name} (previous score: {last_score})")
            
            # Generate coding question for this skill
            logger.info(f"Generating coding question for skill: {target_skill}, difficulty: {coding_difficulty.name}")
            question = await generate_coding_question(
                skill=target_skill,
                difficulty=coding_difficulty,
                role=state.role.value,
                language="python" if is_graduate_role(state.role) else None
            )
            return question
        
        # Check if skill is common (use pool) or unique (generate dynamically)
        # Option: Use LLM for all questions if configured (skip pool)
        use_llm_for_all = state.use_llm_for_all_questions
        
        if not use_llm_for_all and is_common_skill(target_skill):
            # Use question pool for common skills
            used_questions = [q.question for q in state.questions_asked if q.skill == target_skill]
            pool_question = get_question_from_pool(target_skill, difficulty, used_questions)
            
            if pool_question:
                return Question(
                    question_id=str(uuid.uuid4()),
                    question=pool_question,
                    skill=target_skill,
                    difficulty=difficulty,
                    type=QuestionType.PRACTICAL if difficulty >= 3 else QuestionType.CONCEPTUAL,
                    context={"phase": "standout_skills", "source": "pool"}
                )
        
        # Generate dynamically (for unique skills, if pool exhausted, or if use_llm_for_all is True)
        question = await generate_question(
            skill=target_skill,
            difficulty=difficulty,
            role=state.role.value,
            resume_data=state.resume_data,
            previous_questions=[q.question for q in state.questions_asked[-5:]],
            state=state,
            candidate_name=candidate_name
        )
        
        # Generate conversational transition
        if state.questions_asked:  # Only add transition if not first question
            try:
                transition = await generate_conversational_transition(
                    state=state,
                    next_question=question,
                    last_evaluation=last_evaluation,
                    candidate_name=candidate_name
                )
                question.context = question.context or {}
                question.context["transition"] = transition
            except Exception as e:
                logger.warning(f"Failed to generate conversational transition: {e}")
        
        question.context = question.context or {}
        question.context["phase"] = "standout_skills"
        question.context["source"] = "dynamic"
        return question
    
    # Phase 3: ROLE_SKILLS (5-6 questions)
    elif state.current_phase == InterviewPhase.ROLE_SKILLS:
        if phase_count >= 6:
            # All phases complete
            return None
        
        # Get role-required skills (prioritize high-weight skills that are relevant to the role)
        # Filter to only skills that are actually in the role mapping or have high relevance
        role_skills = [
            sw for sw in state.skill_weights
            if sw.role_relevance > 0.3  # Only include skills relevant to the role
        ]
        
        # Sort by weight (higher weight = more important)
        role_skills = sorted(role_skills, key=lambda x: x.weight, reverse=True)
        
        # If no role-relevant skills, use all skills (fallback)
        if not role_skills:
            role_skills = sorted(state.skill_weights, key=lambda x: x.weight, reverse=True)
        
        # Find skills that need questions (not yet asked or need more questions)
        skills_needing_questions = []
        for skill_weight in role_skills:
            skill = skill_weight.skill
            answered_count = len(state.answered_skills.get(skill, []))
            
            # Calculate expected questions based on weight and role relevance
            # Higher weight and relevance = more questions
            base_questions = max(1, int(skill_weight.weight * 4))  # Scale to 4 questions max per skill
            expected_questions = min(base_questions, 2)  # Max 2 questions per skill in role phase
            
            if answered_count < expected_questions:
                skills_needing_questions.append({
                    "skill": skill,
                    "weight": skill_weight.weight,
                    "role_relevance": skill_weight.role_relevance,
                    "remaining": expected_questions - answered_count
                })
        
        if not skills_needing_questions:
            return None
        
        # Select skill with highest combined score (prioritize role relevance)
        target_skill_data = max(
            skills_needing_questions,
            key=lambda x: (x["role_relevance"] * 0.6 + x["weight"] * 0.4)  # Prioritize role relevance
        )
        target_skill = target_skill_data["skill"]
        state.current_skill = target_skill
        
        # Adjust difficulty based on previous answers
        difficulty = state.current_difficulty
        if target_skill in state.answered_skills:
            evaluations = state.answered_skills[target_skill]
            if evaluations:
                last_score = evaluations[-1].score
                if last_score >= 0.8:
                    difficulty = DifficultyLevel(min(difficulty.value + 1, 4))
                elif last_score < 0.6:
                    difficulty = DifficultyLevel(max(difficulty.value - 1, 1))
        
        # Determine if this should be a coding question
        ask_coding = should_ask_coding_question(state)
        
        if ask_coding:
            # Adaptive difficulty for coding questions based on previous performance
            coding_difficulty = difficulty
            if target_skill in state.answered_skills:
                previous_answers = state.answered_skills[target_skill]
                if previous_answers:
                    last_score = previous_answers[-1].score
                    # If they did well on previous coding questions, increase difficulty
                    if last_score >= 0.8:
                        coding_difficulty = DifficultyLevel(min(difficulty.value + 1, 5))
                        logger.info(f"🎯 Increasing coding difficulty to {coding_difficulty.name} (score: {last_score})")
                    # If they struggled, make it easier
                    elif last_score < 0.5:
                        coding_difficulty = DifficultyLevel(max(difficulty.value - 1, 1))
                        logger.info(f"🎯 Decreasing coding difficulty to {coding_difficulty.name} (score: {last_score})")
            
            # Generate coding question for this skill
            logger.info(f"Generating coding question for skill: {target_skill}, difficulty: {coding_difficulty.name}")
            question = await generate_coding_question(
                skill=target_skill,
                difficulty=coding_difficulty,
                role=state.role.value,
                language="python" if is_graduate_role(state.role) else None
            )
            question.context = {"phase": "role_skills", "source": "coding", "adaptive_difficulty": coding_difficulty.name}
            return question
        
        # Check if skill is common (use pool) or unique (generate dynamically)
        # Option: Use LLM for all questions if configured (skip pool)
        use_llm_for_all = state.use_llm_for_all_questions
        
        if not use_llm_for_all and is_common_skill(target_skill):
            # Use question pool for common skills
            used_questions = [q.question for q in state.questions_asked if q.skill == target_skill]
            pool_question = get_question_from_pool(target_skill, difficulty, used_questions)
            
            if pool_question:
                question_type = QuestionType.PRACTICAL if difficulty >= 3 else QuestionType.CONCEPTUAL
                return Question(
                    question_id=str(uuid.uuid4()),
                    question=pool_question,
                    skill=target_skill,
                    difficulty=difficulty,
                    type=question_type,
                    context={"phase": "role_skills", "source": "pool"}
                )
        
        # Generate dynamically (for unique skills, if pool exhausted, or if use_llm_for_all is True)
        question_type = QuestionType.PRACTICAL if difficulty >= 3 else QuestionType.CONCEPTUAL
        question = await generate_question(
            skill=target_skill,
            difficulty=difficulty,
            role=state.role.value,
            resume_data=state.resume_data,
            question_type=question_type,
            previous_questions=[q.question for q in state.questions_asked[-5:]],
            state=state,
            candidate_name=candidate_name
        )
        
        # Generate conversational transition
        if state.questions_asked:  # Only add transition if not first question
            try:
                transition = await generate_conversational_transition(
                    state=state,
                    next_question=question,
                    last_evaluation=last_evaluation,
                    candidate_name=candidate_name
                )
                question.context = question.context or {}
                question.context["transition"] = transition
            except Exception as e:
                logger.warning(f"Failed to generate conversational transition: {e}")
        
        question.context = question.context or {}
        question.context["phase"] = "role_skills"
        question.context["source"] = "dynamic"
        return question
    
    return None


async def generate_project_question(
    project,
    role: str,
    difficulty: DifficultyLevel,
    previous_questions: List[str],
    state: Optional[InterviewState] = None
) -> Question:
    """
    Generate a question about a specific project.
    Always generated dynamically (personalized to candidate's project).
    
    Args:
        project: Project object from resume
        role: Interview role
        difficulty: Difficulty level
        previous_questions: Previous questions to avoid repetition
        
    Returns:
        Generated question about the project
    """
    from interview_service.question_generator import generate_question
    from interview_service.models import ResumeData
    
    # Build project context for prompt
    project_description = project.description or "N/A"
    technologies = ", ".join(project.technologies) if project.technologies else "Various technologies"
    
    # Create a minimal resume data with just this project
    project_resume_data = ResumeData(
        skills=[],
        projects=[project],
        experience=[],
        education=[]
    )
    
    # Use the main technology for skill context
    main_tech = project.technologies[0] if project.technologies else "software development"
    
    # Generate project-specific question
    question = await generate_question(
        skill=main_tech,
        difficulty=difficulty,
        role=role,
        resume_data=project_resume_data,
        question_type=QuestionType.PRACTICAL,
        previous_questions=previous_questions,
        state=state
    )
    
    # Enhance question to be project-specific with VARIED framing
    import random
    project_openers = [
        f"I noticed your '{project.name}' project on your resume. {question.question}",
        f"Let's dive into your '{project.name}' project. {question.question}",
        f"Regarding your '{project.name}' project - {question.question}",
        f"Walk me through your '{project.name}' project. {question.question}",
        f"I'd like to hear about '{project.name}'. {question.question}",
    ]
    question.question = random.choice(project_openers)
    question.context = question.context or {}
    question.context["project"] = project.name
    question.context["project_description"] = project_description
    question.context["technologies"] = project.technologies
    question.context["phase"] = "projects"
    question.context["source"] = "dynamic_project"
    
    return question


def update_phase_question_count(state: InterviewState):
    """Update question count for current phase."""
    phase_key = state.current_phase.value
    state.phase_questions[phase_key] = state.phase_questions.get(phase_key, 0) + 1

