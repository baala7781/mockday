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


def is_technical_role(state: InterviewState) -> bool:
    """
    Check if the role is technical (should get problem-solving coding questions).
    
    Uses dynamic check based on role name, not hardcoded lists.
    """
    role_value = state.role.value if hasattr(state.role, 'value') else str(state.role)
    role_lower = role_value.lower().strip()
    
    # Non-coding roles (explicit exclusion)
    non_coding_keywords = [
        "product-manager", "product manager",
        "tester", "qa", "quality-assurance", "test-engineer"
    ]
    
    # If it's explicitly non-coding, return False
    if any(keyword in role_lower for keyword in non_coding_keywords):
        return False
    
    # Technical roles typically include: developer, engineer, data scientist, etc.
    # Default to True for most roles (let the system decide based on other factors)
    technical_keywords = [
        "developer", "engineer", "programmer", "scientist", "architect"
    ]
    
    # If it contains technical keywords, it's technical
    if any(keyword in role_lower for keyword in technical_keywords):
        return True
    
    # Default: assume technical unless explicitly non-coding
    return True


async def is_technology_skill(skill: str, state: Optional[InterviewState] = None) -> bool:
    """
    Check if a skill is a technology skill (should NOT get coding questions).
    
    Uses LLM-based classification instead of hardcoded list.
    """
    skill_lower = skill.lower().strip()
    
    # Common technology skill patterns (for quick check, but not exhaustive)
    # These are obvious technology names
    obvious_tech_patterns = [
        "javascript", "js", "node.js", "nodejs", "python", "java", "react", "react.js",
        "angular", "vue", "vue.js", "typescript", "html", "css", "sql", "mongodb",
        "postgresql", "mysql", "redis", "aws", "azure", "docker", "kubernetes",
        "express", "django", "flask", "spring", "spring boot", "next.js", "nextjs",
        "graphql", "rest api", "api", "git", "github", "ci/cd", "jenkins",
        "terraform", "ansible", "nginx", "apache", "linux", "unix", "bash",
        "shell scripting", "powershell", "ruby", "php", "go", "golang", "rust",
        "c++", "c#", "swift", "kotlin", "scala", "r", "matlab", "perl"
    ]
    
    # Quick check for obvious technology skills
    if any(tech in skill_lower for tech in obvious_tech_patterns):
        return True
    
    # For ambiguous skills, use LLM to classify (optional, can be added later)
    # For now, if it's not obviously a technology, assume it's not
    # This allows problem-solving, system design, etc. to get through
    
    return False


async def should_ask_coding_question(state: InterviewState, target_skill: Optional[str] = None) -> bool:
    """
    Determine if next question should be a coding question.
    
    Rules:
    - Coding questions are ONLY for problem-solving skills, NOT for specific technology skills
    - Never ask coding questions for specific technologies (JavaScript, Node.js, Python, React, etc.) - these should be theory/conceptual
    - Never ask coding questions for non-coding roles (DevOps, Tester, QA, Product Manager, etc.)
    - Never ask coding questions for experience > 4 years (senior/executive)
    - If candidate has struggled with 2+ recent coding questions (score < 0.4), stop asking coding questions
    
    Args:
        state: Interview state
        target_skill: The skill being assessed (if provided, check if it's a technology skill)
    """
    # If target_skill is provided, check if it's a specific technology skill
    # Technology skills should get theory/conceptual questions, NOT coding questions
    if target_skill:
        # Use dynamic check instead of hardcoded list
        is_tech_skill = await is_technology_skill(target_skill, state)
        if is_tech_skill:
            logger.info(f"🚫 Skipping coding question for technology skill: {target_skill} (will ask theory/conceptual instead)")
            return False
    
    # Check if candidate has been struggling with recent coding questions
    recent_coding_struggles = 0
    recent_coding_questions = [q for q in state.questions_asked[-5:] if q.type == QuestionType.CODING]
    
    # Check evaluations for recent coding questions
    for q in recent_coding_questions:
        if q.skill in state.answered_skills:
            skill_evals = state.answered_skills[q.skill]
            # Find the most recent evaluation for this skill (likely corresponds to this question)
            if skill_evals:
                last_eval = skill_evals[-1]
                if last_eval.score < 0.4:  # Low score indicates struggle
                    recent_coding_struggles += 1
                    logger.info(f"⚠️ Coding struggle detected: {q.skill} (score: {last_eval.score:.2f})")
    
    # If candidate struggled with 2+ recent coding questions, stop asking coding questions
    if recent_coding_struggles >= 2:
        logger.info(f"🚫 Stopping coding questions - candidate struggled with {recent_coding_struggles} recent coding questions")
        return False
    # Check if role is technical (should get problem-solving coding questions)
    # Remove hardcoded role lists - use dynamic check instead
    # Technical roles typically include: developer, engineer (except specific non-coding roles)
    role_value = state.role.value if hasattr(state.role, 'value') else str(state.role)
    role_lower = role_value.lower().strip()
    
    # Non-coding roles (explicit list for exclusion - minimal, only truly non-coding)
    # These roles should NOT get coding questions, even for problem-solving
    non_coding_keywords = [
        "product-manager", "product manager", "product-manager",
        "tester", "qa", "quality-assurance", "test-engineer"
    ]
    
    # Only exclude if role explicitly matches non-coding keywords
    # Don't exclude broadly - let technical roles get problem-solving coding questions
    if any(keyword in role_lower for keyword in non_coding_keywords):
        logger.info(f"🚫 Skipping coding question for non-coding role: {role_value}")
        return False
    
    # Check experience level - determine coding question percentage based on experience
    experience_level = state.experience_level
    total_questions = len(state.questions_asked)
    coding_questions = sum(1 for q in state.questions_asked if q.type == QuestionType.CODING)
    
    if total_questions == 0:
        return False  # First question is always intro
    
    coding_percentage = coding_questions / total_questions if total_questions > 0 else 0
    
    # Base coding question percentage on experience level
    if experience_level:
        # Map experience levels to years
        experience_years_map = {
            "entry": 1,      # 0-2 years
            "mid": 3.5,      # 3-5 years
            "senior": 8,     # 6-10 years
            "executive": 12  # 10+ years
        }
        
        years = experience_years_map.get(experience_level, 0)
        
        # No coding questions for 4+ years (senior/executive)
        if years >= 4:
            logger.info(f"🚫 Skipping coding question for experience level: {experience_level} ({years} years)")
            return False
        
        # Entry level (0-2 years) = 50-60% coding questions (like graduates)
        if experience_level == "entry":
            target_percentage = 0.55  # Mid-point of 50-60%
            threshold = target_percentage + random.uniform(-0.05, 0.05)
            return coding_percentage < threshold
        # Mid level (3-5 years) = 20-30% coding questions
        elif experience_level == "mid":
            target_percentage = 0.25  # Mid-point of 20-30%
            threshold = target_percentage + random.uniform(-0.03, 0.03)
            return coding_percentage < threshold
    
    # Fallback: if no experience level, check if it's a graduate role (for backwards compatibility)
    if is_graduate_role(state.role):
        # Target: 50-60% coding for graduates
        target_percentage = 0.55  # Mid-point of 50-60%
        threshold = target_percentage + random.uniform(-0.05, 0.05)
        return coding_percentage < threshold
    
    # Default: 20-30% coding for roles without experience level specified
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
            from interview_service.llm_helpers import generate_with_task_and_byok
            
            logger.info(f"🤖 [Intro Question] Attempt {attempt + 1}/{max_retries}: Generating intro question...")
            response = await generate_with_task_and_byok(
                task="question_generation",
                prompt=prompt,
                max_tokens=150,
                temperature=0.85,  # Higher temperature for more variety
                interview_id=state.interview_id
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
    
    # Phase 1: PROJECTS (2-4 questions: 1 high-level per project, then 1 deep-dive per project)
    elif state.current_phase == InterviewPhase.PROJECTS:
        if phase_count >= 4:
            # Move to next phase
            state.current_phase = InterviewPhase.STANDOUT_SKILLS
            state.phase_questions[InterviewPhase.PROJECTS.value] = phase_count
            return await select_next_question_phased(state)
        
        # Track project states: high-level vs deep-dive
        # answered_projects tracks: project_name -> [evaluations]
        # Strategy: For each project, ask high-level first, then deep-dive
        
        # Find projects that need deep-dive (have 1 answer = high-level, need deep-dive)
        projects_needing_deep_dive = []
        for project_name, evals in state.answered_projects.items():
            if evals and len(evals) == 1:  # Only high-level asked, need deep-dive
                # Verify last question was high-level
                last_project_question = None
                for q in reversed(state.questions_asked):
                    if q.context and q.context.get("project") == project_name:
                        last_project_question = q
                        break
                
                if last_project_question and last_project_question.context.get("question_type") == "high_level":
                    projects_needing_deep_dive.append(project_name)
        
        is_deep_dive = False
        target_project = None
        
        if projects_needing_deep_dive:
            # Prioritize deep-dive for projects that have been asked high-level
            target_project_name = projects_needing_deep_dive[0]
            is_deep_dive = True
            # Find the project object
            for p in (state.resume_data.projects or []):
                if p.name == target_project_name:
                    target_project = p
                    state.current_project = p.name
                    break
        else:
            # No projects need deep-dive, find new projects for high-level
            asked_projects = set(state.answered_projects.keys())
            available_projects = [
                p for p in (state.resume_data.projects or [])
                if p.name not in asked_projects
            ]
            
            if not available_projects:
                # All projects covered (high-level + deep-dive), move to next phase
                state.current_phase = InterviewPhase.STANDOUT_SKILLS
                state.phase_questions[InterviewPhase.PROJECTS.value] = phase_count
                return await select_next_question_phased(state)
            
            # Select project with most relevant technologies
            target_project = max(
                available_projects,
                key=lambda p: len([s for s in p.technologies if any(
                    sw.skill.lower() in s.lower() or s.lower() in sw.skill.lower()
                    for sw in state.skill_weights
                )])
            )
            state.current_project = target_project.name
            is_deep_dive = False
        
        # Generate project question (high-level or deep-dive)
        question = await generate_project_question(
            project=target_project,
            role=state.role.value,
            difficulty=state.current_difficulty,
            previous_questions=[q.question for q in state.questions_asked[-3:]],
            state=state,
            is_deep_dive=is_deep_dive,
            previous_answers=[e.feedback for e in (state.answered_projects.get(target_project.name, []) or [])]
        )
        return question
    
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
        # Problem-solving skill gets coding questions (LeetCode-style)
        # Technology skills do NOT get coding questions
        is_problem_solving = target_skill.lower() in ["problem-solving", "problem solving", "problem_solving"]
        
        ask_coding = False
        if is_problem_solving:
            # Problem-solving always gets coding questions for technical roles
            ask_coding = await should_ask_coding_question(state, target_skill="problem-solving")
        else:
            # For other skills, check if it's a technology skill (should NOT get coding)
            ask_coding = await should_ask_coding_question(state, target_skill=target_skill)
        
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
            
            # Generate coding question (LeetCode-style for problem-solving)
            logger.info(f"Generating coding question for skill: {target_skill}, difficulty: {coding_difficulty.name}")
            question = await generate_coding_question(
                skill=target_skill if is_problem_solving else target_skill,
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
        
        # For technical roles, periodically inject problem-solving coding questions
        # Check if we should ask a problem-solving coding question instead of a regular skill question
        if is_technical_role(state):
            total_questions_asked = len(state.questions_asked)
            problem_solving_asked = sum(1 for q in state.questions_asked if q.skill.lower() in ["problem-solving", "problem solving", "problem_solving"])
            
            # Calculate target: 1-2 problem-solving coding questions in role skills phase for technical roles
            # Ask after 2-3 regular questions, then again if needed
            should_ask_problem_solving = False
            
            # First problem-solving question: after 2 regular role skill questions
            if problem_solving_asked == 0 and phase_count >= 2:
                should_ask_problem_solving = True
            # Second problem-solving question: after 4 regular role skill questions (if we have room)
            elif problem_solving_asked == 1 and phase_count >= 4 and phase_count < 6:
                should_ask_problem_solving = True
            
            if should_ask_problem_solving:
                # Check if we should ask coding question for problem-solving
                ask_coding = await should_ask_coding_question(state, target_skill="problem-solving")
                if ask_coding:
                    # Generate problem-solving coding question
                    problem_solving_difficulty = state.current_difficulty
                    
                    # Adjust difficulty based on previous problem-solving answers
                    if "problem-solving" in state.answered_skills:
                        problem_solving_evals = state.answered_skills["problem-solving"]
                        if problem_solving_evals:
                            last_score = problem_solving_evals[-1].score
                            if last_score >= 0.8:
                                problem_solving_difficulty = DifficultyLevel(min(problem_solving_difficulty.value + 1, 5))
                            elif last_score < 0.5:
                                problem_solving_difficulty = DifficultyLevel(max(problem_solving_difficulty.value - 1, 1))
                    
                    logger.info(f"💻 Injecting problem-solving coding question for technical role: {state.role.value}")
                    question = await generate_coding_question(
                        skill="problem-solving",
                        difficulty=problem_solving_difficulty,
                        role=state.role.value,
                        language="python" if is_graduate_role(state.role) else None
                    )
                    question.context = {
                        "phase": "role_skills",
                        "source": "problem_solving_coding",
                        "adaptive_difficulty": problem_solving_difficulty.name,
                        "injected": True  # Mark as injected problem-solving question
                    }
                    state.current_skill = "problem-solving"
                    return question
        
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
        # Pass target_skill to check if it's a technology skill (should NOT get coding questions)
        ask_coding = await should_ask_coding_question(state, target_skill=target_skill)
        
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
    state: Optional[InterviewState] = None,
    is_deep_dive: bool = False,
    previous_answers: Optional[List[str]] = None
) -> Question:
    """
    Generate a question about a specific project.
    
    Two-stage flow:
    1. High-level: Ask about the project (what, why, overview)
    2. Deep-dive: Pick a specific functionality and ask detailed questions
    
    Args:
        project: Project object from resume
        role: Interview role
        difficulty: Difficulty level
        previous_questions: Previous questions to avoid repetition
        state: Interview state
        is_deep_dive: If True, ask deep-dive about specific functionality. If False, ask high-level.
        previous_answers: Previous answers about this project (for context in deep-dive)
        
    Returns:
        Generated question about the project
    """
    from interview_service.question_generator import generate_question
    from interview_service.models import ResumeData
    
    # Build project context for prompt
    project_description = project.description or "N/A"
    technologies = ", ".join(project.technologies) if project.technologies else "Various technologies"
    
    import random
    from interview_service.llm_helpers import generate_with_task_and_byok
    
    if not is_deep_dive:
        # HIGH-LEVEL: Ask about the project overview, integrations, and work done
        prompt = f"""You are a technical interviewer conducting a {role.replace('-', ' ')} interview.

The candidate has a project called "{project.name}" on their resume.
Technologies: {technologies}
Description: {project_description}

Generate a HIGH-LEVEL question about this project that:
1. Asks them to explain the project (what it is, why they built it, overview)
2. OR asks about integrations, APIs, or external services they worked with
3. OR asks about the type of work they did (features, modules, components)
4. Is conversational and natural (like a real interviewer)
5. Keeps it to 2-3 sentences
6. DO NOT ask for specific technical implementation details yet
7. Focus on understanding the project's purpose, scope, integrations, or work done

Examples:
- "I see you worked on [project name]. Can you tell me about this project - what it does, what integrations or APIs you worked with, and what motivated you to build it?"
- "Tell me about your [project name] project. What was the main goal, what kind of work did you do on it, and what problem were you trying to solve?"
- "I noticed [project name] on your resume. Can you walk me through what this project is about and any integrations or external services you worked with?"

Previous questions asked:
{chr(10).join([f"- {q}" for q in previous_questions[-2:]])}

Return ONLY the question text, starting with a natural introduction."""
        
        question_text = await generate_with_task_and_byok(
            task="question_generation",
            prompt=prompt,
            max_tokens=200,
            temperature=0.8,
            interview_id=state.interview_id if state else None
        )
        
        if not question_text or len(question_text.strip()) < 20:
            # Fallback
            question_text = f"I see you worked on '{project.name}'. Can you tell me about this project - what it does and what motivated you to build it?"
        else:
            question_text = question_text.strip()
            # Remove quotes if present
            if question_text.startswith('"') and question_text.endswith('"'):
                question_text = question_text[1:-1]
            if question_text.startswith("'") and question_text.endswith("'"):
                question_text = question_text[1:-1]
        
        # Create question object
        question = Question(
            question_id=str(uuid.uuid4()),
            question=question_text,
            skill=f"{project.name} (Project Overview)",
            difficulty=difficulty,
            type=QuestionType.PRACTICAL,
            context={
                "project": project.name,
                "project_description": project_description,
                "technologies": project.technologies,
                "phase": "projects",
                "source": "dynamic_project",
                "question_type": "high_level"
            }
        )
        return question
    
    else:
        # DEEP-DIVE: Ask about specific functionality with detailed technical questions
        # Use previous answer to pick a functionality to drill into
        previous_context = ""
        if previous_answers and len(previous_answers) > 0:
            # Get full last answer (not just 300 chars) for better context
            last_answer = previous_answers[-1][:500]  # Last 500 chars for more context
            previous_context = f"Candidate's previous answer about this project:\n{last_answer}"
        
        prompt = f"""You are a technical interviewer conducting a {role.replace('-', ' ')} interview.

The candidate has a project called "{project.name}" on their resume.
Technologies: {technologies}
Description: {project_description}

{previous_context}

The candidate already explained the project overview, integrations, or work done. Now, based on their answer, identify a SPECIFIC functionality, feature, integration, or component they mentioned (or could have implemented) and ask a DETAILED technical question about it.

Your question should:
1. Pick ONE specific functionality/feature/integration/component (e.g., authentication system, payment integration, data processing pipeline, API endpoint, real-time updates, database design, etc.)
2. Ask about HOW they implemented it or HOW they would implement it
3. Be technical and detailed - ask about:
   - Architecture and design decisions
   - Algorithms or data structures used
   - Technologies and frameworks
   - Challenges faced and how they solved them
   - Edge cases or error handling
   - Performance considerations
4. Keep it to 2-3 sentences but be specific
5. Sound natural and conversational
6. Drill deep into the technical implementation

Examples:
- "You mentioned [specific feature/integration]. Can you walk me through how you implemented that in detail? What was your architecture, what technologies did you use, and what were the main challenges you faced?"
- "I'm curious about [specific functionality]. Can you explain how you built that? What design decisions did you make, and how did you handle edge cases or error scenarios?"
- "You talked about [specific component]. Can you dive deeper into the implementation? What algorithms or data structures did you use, and how did you ensure it performs well?"

Return ONLY the question text."""
        
        question_text = await generate_with_task_and_byok(
            task="question_generation",
            prompt=prompt,
            max_tokens=250,
            temperature=0.75,
            interview_id=state.interview_id if state else None
        )
        
        if not question_text or len(question_text.strip()) < 20:
            # Fallback
            question_text = f"Great! Now, can you dive deeper into a specific functionality of '{project.name}'? Pick one key feature and walk me through how you implemented it - the technologies you used and any challenges you faced."
        else:
            question_text = question_text.strip()
            # Remove quotes if present
            if question_text.startswith('"') and question_text.endswith('"'):
                question_text = question_text[1:-1]
            if question_text.startswith("'") and question_text.endswith("'"):
                question_text = question_text[1:-1]
        
        # Create question object
        question = Question(
            question_id=str(uuid.uuid4()),
            question=question_text,
            skill=f"{project.name} (Deep Dive)",
            difficulty=difficulty,
            type=QuestionType.PRACTICAL,
            context={
                "project": project.name,
                "project_description": project_description,
                "technologies": project.technologies,
                "phase": "projects",
                "source": "dynamic_project",
                "question_type": "deep_dive"
            }
        )
        return question


def update_phase_question_count(state: InterviewState):
    """Update question count for current phase."""
    phase_key = state.current_phase.value
    state.phase_questions[phase_key] = state.phase_questions.get(phase_key, 0) + 1

