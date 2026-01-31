"""OpenRouter client wrapper with pool management for multiple API keys."""
import logging
from typing import Optional
from shared.providers.openrouter_client import OpenRouterClient
from shared.providers.pool_manager import provider_pool_manager, ProviderType

logger = logging.getLogger(__name__)


def get_openrouter_client(api_key: Optional[str] = None) -> OpenRouterClient:
    """
    Get OpenRouter client - uses pool if no key provided, otherwise uses provided key (BYOK).
    
    Args:
        api_key: Optional API key (BYOK). If provided, uses this key directly.
        
    Returns:
        OpenRouterClient instance
    """
    if api_key:
        # BYOK - use provided key directly
        return OpenRouterClient(api_key=api_key, use_pool=False)
    else:
        # Use pool management for multiple keys
        return OpenRouterClient(api_key=None, use_pool=True)


# Task-specific model mappings
TASK_MODELS = {
    "question_generation": "openai/gpt-4o-mini",
    "follow_up": "openai/gpt-4o-mini",
    "clarification": "openai/gpt-4o-mini",
    "answer_evaluation": "anthropic/claude-3-haiku",
    "resume_parsing": "openai/gpt-4o-mini",
    "report_generation": "anthropic/claude-3-sonnet",
}


async def generate_with_task_model(
    task: str,
    prompt: str,
    max_tokens: int = 2000,
    temperature: float = 0.7,
    api_key: Optional[str] = None
) -> Optional[str]:
    """
    Generate response using task-specific model via OpenRouter.
    
    Args:
        task: Task type (question_generation, answer_evaluation, etc.)
        prompt: Input prompt
        max_tokens: Maximum tokens
        temperature: Temperature
        api_key: Optional API key (BYOK)
        
    Returns:
        Generated text or None on error
    """
    model = TASK_MODELS.get(task)
    if not model:
        logger.error(f"Unknown task type: {task}")
        return None
    
    client = get_openrouter_client(api_key)
    return await client.generate_response(
        prompt=prompt,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature
    )


async def generate_report(
    interview_transcript: str,
    questions: list,
    answers: list,
    role: str,
    user_profile: Optional[dict] = None,
    is_complete: bool = True,
    expected_questions: int = 10,
    actual_questions: int = 0,
    api_key: Optional[str] = None
) -> Optional[dict]:
    """
    Generate interview report using OpenRouter (anthropic/claude-3-sonnet).
    
    Args:
        interview_transcript: Full interview transcript
        questions: List of questions asked
        answers: List of answers provided
        role: Role being interviewed for
        user_profile: User profile information
        is_complete: Whether the interview was completed
        expected_questions: Number of questions expected in full interview
        actual_questions: Number of questions actually answered
        api_key: Optional API key (BYOK)
        
    Returns:
        Report dict with score, feedback, analysis, etc.
    """
    import json
    
    completion_percentage = (actual_questions / expected_questions * 100) if expected_questions > 0 else 0
    completion_note = ""
    if not is_complete or completion_percentage < 80:
        completion_note = f"""
⚠️ CRITICAL: This is an INCOMPLETE interview ({actual_questions}/{expected_questions} questions = {completion_percentage:.0f}% complete).

**STRICT RULES FOR INCOMPLETE INTERVIEWS:**
1. ONLY assess skills that were ACTUALLY evaluated in the questions/answers provided
2. DO NOT create section_scores for skills that were NOT assessed (e.g., if only 1 question was asked, only assess that ONE skill)
3. DO NOT generate strengths/weaknesses for skills that were NOT evaluated
4. Maximum possible score should be capped based on completion:
   - <50% complete: Cap at 50-60%
   - 50-75% complete: Cap at 60-70%
   - 75-80% complete: Cap at 70-75%
5. Recommendation MUST reflect incomplete assessment (use "maybe" or "no_hire" unless exceptional)
6. Be EXPLICITLY honest: "Limited assessment due to incomplete interview"
7. Only include skills in section_scores that were actually evaluated in the transcript
"""
    
    # Serialize user profile
    profile_text = "Not provided"
    if user_profile:
        try:
            profile_text = json.dumps(user_profile, indent=2)
        except:
            profile_text = str(user_profile)
    
    prompt = f"""Generate a REALISTIC and HONEST interview evaluation report for a {role} position.

**SCORING GUIDELINES (STRICT):**
- 90-100: Exceptional - Almost perfect answers, deep expertise, hire immediately
- 80-89: Strong - Very good answers, clear expertise, confident hire
- 70-79: Good - Solid answers, competent, likely hire
- 60-69: Average - Basic understanding, some gaps, maybe hire with reservations  
- 50-59: Below Average - Significant gaps, weak answers, likely no hire
- 40-49: Poor - Major deficiencies, unclear answers, no hire
- 0-39: Very Poor - Did not demonstrate competency, definite no hire

**RECOMMENDATION CRITERIA:**
- "strong_hire": Score 80+ AND demonstrated clear expertise
- "hire": Score 70-79 AND no major red flags
- "maybe": Score 60-69 OR mixed performance
- "no_hire": Score below 60 OR significant concerns
{completion_note}

Interview Transcript:
{interview_transcript}

Questions Asked ({len(questions)} total):
{chr(10).join(f"{i+1}. {q}" for i, q in enumerate(questions))}

Answers Provided ({len(answers)} total):
{chr(10).join(f"{i+1}. {a}" for i, a in enumerate(answers))}

User Profile:
{profile_text}

**BE HONEST AND CRITICAL.** Don't inflate scores. If answers were vague, short, or incorrect, score accordingly.

**CRITICAL RULES:**
1. ONLY include skills in section_scores that were ACTUALLY evaluated in the questions/answers
2. If only 1 question was asked, ONLY assess that ONE skill - do NOT create scores for communication, problem_solving, etc. unless they were explicitly evaluated
3. DO NOT generate generic strengths like "Participated in interview" - only real, demonstrated strengths
4. If interview is incomplete, be explicit: "This assessment is limited due to incomplete interview"
5. Strengths and weaknesses must be SPECIFIC to what was actually said/demonstrated

Generate a detailed report in JSON format with:
- overall_score: integer (0-100) - BE REALISTIC based on actual performance, cap appropriately for incomplete interviews
- section_scores: object with scores ONLY for areas that were actually evaluated (e.g., if only "Introduction" was asked, only include that skill, NOT communication/problem_solving)
- strengths: list of strings (ONLY if genuinely demonstrated in the actual answers - NO generic statements)
- weaknesses: list of strings (be specific about gaps, or "Limited assessment due to incomplete interview" if incomplete)
- detailed_feedback: string (comprehensive, honest feedback - mention if incomplete)
- recommendation: string (strong_hire, hire, maybe, no_hire) - reflect incomplete status if applicable
- improvement_suggestions: list of strings (actionable suggestions, include "Complete full interview for accurate assessment" if incomplete)

Response (JSON only):"""
    
    client = get_openrouter_client(api_key)
    response = await client.generate_response(
        prompt=prompt,
        model=TASK_MODELS["report_generation"],
        max_tokens=3000,
        temperature=0.3
    )
    
    if response:
        # Extract JSON from response
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            try:
                report = json.loads(response[json_start:json_end])
                return report
            except json.JSONDecodeError:
                pass
    
    return None

