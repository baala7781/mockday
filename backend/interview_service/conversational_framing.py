"""Conversational framing generator for natural interview transitions."""
from typing import Optional
from interview_service.models import InterviewState, Question, Evaluation
from interview_service.memory_controller import create_resume_summary
from shared.providers.gemini_client import gemini_client
import logging

logger = logging.getLogger(__name__)


async def generate_conversational_transition(
    state: InterviewState,
    next_question: Question,
    last_evaluation: Optional[Evaluation] = None,
    candidate_name: Optional[str] = None
) -> str:
    """
    Generate a natural conversational transition before asking the next question.
    
    Examples:
    - "Thanks for explaining that. Now let's talk about database indexing..."
    - "Interesting, I see you have experience with REST APIs. Let's move to system design..."
    - "Alright, let's discuss your experience with Python..."
    
    Args:
        state: Interview state
        next_question: The next question to be asked
        last_evaluation: Last evaluation (if available)
        candidate_name: Candidate's first name (optional, for personalization)
        
    Returns:
        Conversational transition text (1-2 sentences)
    """
    # Safety: Never use candidate name if not explicitly provided
    # Strip any name from prompts to prevent LLM from inventing one
    name_placeholder = "you" if not candidate_name else candidate_name
    
    # Build minimal context
    last_skill = None
    last_score = None
    if last_evaluation:
        # Get last skill from state
        if state.questions_asked:
            last_question = state.questions_asked[-1]
            last_skill = last_question.skill
            last_score = last_evaluation.score
    
    # Build context with answer quality feedback
    context_parts = []
    if last_skill and last_skill != next_question.skill:
        context_parts.append(f"Last topic: {last_skill}")
    
    # Add feedback based on answer quality
    feedback_instruction = ""
    if last_evaluation and last_score is not None:
        # Get last answer text if available
        last_answer_text = ""
        if state.questions_asked and len(state.questions_asked) > 0:
            # Try to get last answer from conversation history
            if state.conversation_history:
                last_conv = state.conversation_history[-1]
                last_answer_text = last_conv.get("answer", "")[:100]  # First 100 chars
        
        if last_score >= 0.75:
            # Good answer - neutral acknowledgment, no positive feedback
            feedback_instruction = "Acknowledge neutrally (e.g., 'I understand what X is, that's it' or 'Okay, let's move on'). Do NOT give positive feedback."
        elif last_score >= 0.5 and last_score < 0.75:
            # Close but needs elaboration
            feedback_instruction = "Give constructive one-line feedback: 'Please elaborate your answers more' or similar, then transition."
        elif last_score < 0.5:
            # Poor answer or "I don't know"
            if "don't know" in last_answer_text.lower() or "idk" in last_answer_text.lower() or "not sure" in last_answer_text.lower():
                feedback_instruction = "Acknowledge honesty: 'Thanks for your honesty, let's move to the next question' or similar."
            else:
                feedback_instruction = "Briefly acknowledge and move on without being harsh."
    
    context = ". ".join(context_parts) if context_parts else "Starting new topic"
    
    # Generate transition
    prompt = f"""You are an experienced technical interviewer conducting a {state.role.value.replace('-', ' ')} interview.

Generate a natural, conversational transition (1-2 sentences) before asking the next question.

Context:
- {context}
- Next topic: {next_question.skill}
- Next question type: {next_question.type.value}
- Next difficulty: {next_question.difficulty}
- Last answer score: {last_score if last_score is not None else 'N/A'}

Feedback Guidelines:
{feedback_instruction if feedback_instruction else "- Acknowledge the previous topic if relevant"}

General Guidelines:
- Sound natural and conversational
- Be professional but not overly positive
- Smoothly transition to the next topic
- Use phrases like "Thanks for explaining...", "I understand...", "Let's talk about...", "Now let's move to..."
- Keep it brief (1-2 sentences maximum)
- Do NOT include the actual question
- Do NOT use any personal names or invent names
- Address the candidate as "you" or use the provided name: {name_placeholder}
- Do NOT give excessive positive feedback - keep it neutral or constructive

Examples:
- "I understand what async in JS is, that's it. Let's talk about database indexing."
- "Please elaborate your answers more. Now let's move to system design."
- "Thanks for your honesty, let's move to the next question."
- "Alright, let's discuss your experience with Python."

Generate ONLY the transition text, no additional explanation:"""

    try:
        response = await gemini_client.generate_response(
            prompt=prompt,
            model="gemini-2.0-flash-lite",
            max_tokens=100,
            temperature=0.7
        )
        
        if response:
            transition = response.strip()
            # Remove quotes if present
            if transition.startswith('"') and transition.endswith('"'):
                transition = transition[1:-1]
            if transition.startswith("'") and transition.endswith("'"):
                transition = transition[1:-1]
            
            # Safety check: Remove any invented names
            # This is a simple check - in production, you might want more sophisticated name detection
            transition = transition.replace("Bala", name_placeholder).replace("bala", name_placeholder)
            
            logger.debug(f"Generated transition: {transition[:100]}...")
            return transition
    except Exception as e:
        logger.warning(f"Error generating conversational transition: {e}")
    
    # Fallback
    return f"Let's talk about {next_question.skill}."


def get_candidate_name_safely(user_profile: Optional[dict] = None) -> Optional[str]:
    """
    Safely extract candidate's first name from profile.
    
    Args:
        user_profile: User profile dict (from Firestore)
        
    Returns:
        First name if available, None otherwise
    """
    if not user_profile:
        return None
    
    # Try to get name from profile
    name = user_profile.get("name") or user_profile.get("displayName")
    
    if not name:
        return None
    
    # Extract first name only
    first_name = name.split()[0] if name else None
    
    # Basic validation: ensure it's a reasonable name (not empty, not too long)
    if first_name and len(first_name) > 1 and len(first_name) < 50:
        return first_name
    
    return None

