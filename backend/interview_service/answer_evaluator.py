"""Answer evaluation using LLM."""
from typing import Dict, Any, Optional
from interview_service.models import Evaluation, Question, QuestionType, DifficultyLevel, Answer, InterviewState
from shared.providers.gemini_client import gemini_client
from interview_service.memory_controller import get_conversation_context_for_evaluation
from interview_service.difficulty_manager import calculate_smoothed_difficulty, get_recent_evaluations_for_skill
import json
import logging

logger = logging.getLogger(__name__)


EVALUATION_CRITERIA = {
    QuestionType.CONCEPTUAL: {
        "accuracy": 0.4,
        "completeness": 0.3,
        "clarity": 0.2,
        "examples": 0.1
    },
    QuestionType.PRACTICAL: {
        "approach": 0.3,
        "correctness": 0.3,
        "best_practices": 0.2,
        "edge_cases": 0.2
    },
    QuestionType.CODING: {
        "correctness": 0.4,
        "efficiency": 0.2,
        "readability": 0.2,
        "best_practices": 0.2
    },
    QuestionType.SYSTEM_DESIGN: {
        "architecture": 0.3,
        "scalability": 0.2,
        "reliability": 0.2,
        "tradeoffs": 0.3
    }
}


async def evaluate_answer(
    question: Question,
    answer: Answer,
    previous_evaluations: Optional[list] = None,
    state: Optional[InterviewState] = None
) -> Evaluation:
    """
    Evaluate candidate's answer using LLM.
    
    Args:
        question: The question that was answered
        answer: Candidate's answer
        previous_evaluations: Previous evaluations for context
        
    Returns:
        Evaluation with score, feedback, and next difficulty
    """
    criteria = EVALUATION_CRITERIA.get(question.type, EVALUATION_CRITERIA[QuestionType.CONCEPTUAL])
    
    # Build criteria description
    criteria_desc = "\n".join([
        f"- {key}: {value * 100}% weight" for key, value in criteria.items()
    ])
    
    # Use memory controller to get minimal context (only last score, not full history)
    context = ""
    if state:
        eval_context = get_conversation_context_for_evaluation(state, question, answer)
        if eval_context.get("last_score") is not None:
            context = f"\nCandidate's last score on this skill: {eval_context['last_score']:.2f}/1.0"
    elif previous_evaluations:
        # Fallback: use last evaluation score only
        if previous_evaluations:
            last_eval = previous_evaluations[-1]
            last_score = last_eval.get("score", 0) if isinstance(last_eval, dict) else getattr(last_eval, "score", 0)
            context = f"\nCandidate's last score: {last_score:.2f}/1.0"
    
    # Build prompt with improved format (more reliable, less hallucination)
    prompt = f"""You are evaluating a candidate's answer in a technical interview. Be CRITICAL and HONEST.

Question:

{question.question}

Question Type: {question.type.value}

Skill Area: {question.skill}

Difficulty: {question.difficulty}

Candidate's Answer:

{answer.answer}

{f"Candidate's Code:\n{answer.code}" if answer.code else ""}

Additional Context:

{context if context else "No previous evaluations."}

## Evaluation Rules (STRICT)

- Use ONLY the provided question and answer. Do NOT assume or invent information.

- Be CRITICAL: If the answer is vague, incomplete, or incorrect, score accordingly (0.3-0.5 range).

- Score must reflect technical correctness, completeness, and clarity.

- Follow the scoring weights:

{criteria_desc}

- Scoring Guidelines:
  * 0.9-1.0: Exceptional - Complete, accurate, demonstrates deep understanding
  * 0.7-0.89: Good - Mostly correct, minor gaps or lack of depth
  * 0.5-0.69: Average - Partially correct, some understanding but significant gaps
  * 0.3-0.49: Below Average - Vague, incorrect, or missing key concepts
  * 0.0-0.29: Poor - Incorrect, no understanding demonstrated

## Output Requirements

Return a VALID JSON object with:

{{
  "score": float between 0.0 and 1.0,
  "feedback": "detailed, specific, and constructive feedback - be honest about gaps",
  "strengths": ["specific strength 1", "specific strength 2"] - ONLY if genuinely demonstrated,
  "weaknesses": ["specific weakness 1", "specific weakness 2"] - be specific about what was missing or incorrect,
  "suggestions": ["actionable suggestion 1", "actionable suggestion 2"],
  "next_difficulty": 1 to 4,
  "skill_assessment": {{
      "{question.skill}": float between 0.0 and 1.0
  }}
}}

Rules:

- JSON ONLY. No explanation.

- STRICT JSON. No trailing commas.

- Feedback must be SPECIFIC: Reference what was said correctly/incorrectly, what was missing, what could be improved.

- Strengths/weaknesses must be SPECIFIC to the answer given - NO generic statements.

- Next difficulty logic:

  - Score >= 0.8 → increase difficulty by 1 (max 4)

  - Score >= 0.6 → keep same

  - Score < 0.6 → decrease by 1 (min 1)"""

    # Log what we're sending to LLM for evaluation
    logger.info(f"🤖 [LLM Evaluation] Sending to LLM for evaluation:")
    logger.info(f"   Question: {question.question[:100]}...")
    logger.info(f"   Question Type: {question.type.value}, Difficulty: {question.difficulty}, Skill: {question.skill}")
    logger.info(f"   Answer length: {len(answer.answer)} chars")
    logger.info(f"   Answer text: {answer.answer[:200]}..." if len(answer.answer) > 200 else f"   Answer text: {answer.answer}")
    if answer.code:
        logger.info(f"   Code length: {len(answer.code)} chars")
        logger.info(f"   Code: {answer.code[:200]}..." if len(answer.code) > 200 else f"   Code: {answer.code}")

    try:
        response = await gemini_client.generate_response(
            prompt=prompt,
            model="gemini-2.5-flash-lite",
            max_tokens=1000,
            temperature=0.3
        )
        
        if response:
            logger.info(f"🤖 [LLM Evaluation] Received response from LLM (length: {len(response)} chars)")
            logger.debug(f"🤖 [LLM Evaluation] Full LLM response: {response}")
            # Extract JSON from response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                data = json.loads(response[json_start:json_end])
                
                # Determine next difficulty using smoothed progression
                score = float(data.get("score", 0.5))
                suggested_difficulty = data.get("next_difficulty", question.difficulty.value)
                
                # Use smoothed difficulty calculation (moving average of last 2-3 answers)
                if state:
                    recent_evaluations = get_recent_evaluations_for_skill(state, question.skill, window_size=3)
                    # Add current evaluation to the list for smoothing
                    temp_evaluation = Evaluation(
                        score=score,
                        feedback="",
                        next_difficulty=question.difficulty
                    )
                    recent_evaluations.append(temp_evaluation)
                    
                    # Calculate smoothed difficulty
                    next_difficulty = calculate_smoothed_difficulty(
                        question.difficulty,
                        recent_evaluations,
                        window_size=3
                    )
                else:
                    # Fallback to simple algorithm if no state
                    if score >= 0.8:
                        next_difficulty = DifficultyLevel(min(question.difficulty.value + 1, 4))
                    elif score >= 0.6:
                        next_difficulty = question.difficulty
                    else:
                        next_difficulty = DifficultyLevel(max(question.difficulty.value - 1, 1))
                
                # Log if LLM suggestion differs significantly (for monitoring)
                if isinstance(next_difficulty, DifficultyLevel):
                    next_difficulty_value = next_difficulty.value
                else:
                    next_difficulty_value = next_difficulty
                    
                if abs(int(suggested_difficulty) - next_difficulty_value) > 1:
                    logger.debug(f"LLM suggested difficulty {suggested_difficulty} but smoothed algorithm chose {next_difficulty_value} based on score {score:.2f}")
                
                evaluation = Evaluation(
                    score=score,
                    feedback=data.get("feedback", ""),
                    strengths=data.get("strengths", []),
                    weaknesses=data.get("weaknesses", []),
                    suggestions=data.get("suggestions", []),
                    next_difficulty=DifficultyLevel(next_difficulty),
                    skill_assessment=data.get("skill_assessment", {})
                )
                
                # Log evaluation result
                logger.info(f"🔵🔵🔵🔵")
                logger.info(f"   Score: {score:.2f}/1.0")
                logger.info(f"🤖 [LLM Evaluation] Evaluation Result:")
                logger.info(f"   Score: {score:.2f}/1.0")
                logger.info(f"   Next Difficulty: {next_difficulty} (was {question.difficulty})")
                logger.info(f"   Feedback: {evaluation.feedback[:150]}..." if len(evaluation.feedback) > 150 else f"   Feedback: {evaluation.feedback}")
                logger.info(f"   Strengths: {evaluation.strengths}")
                logger.info(f"   Weaknesses: {evaluation.weaknesses}")
                
                return evaluation
    except Exception as e:
        logger.error(f"🤖 [LLM Evaluation] Error evaluating answer: {e}", exc_info=True)
    
    # Fallback evaluation
    return Evaluation(
        score=0.5,
        feedback="Unable to evaluate answer automatically.",
        next_difficulty=question.difficulty
    )


async def evaluate_code(
    problem: str,
    code: str,
    language: str = "python"
) -> Evaluation:
    """
    Evaluate code submission.
    
    Args:
        problem: Problem statement
        code: Submitted code
        language: Programming language
        
    Returns:
        Code evaluation
    """
    prompt = f"""Analyze the following code submission:

Problem: {problem}
Language: {language}
Code:
```{language}
{code}
```

Evaluate:
1. Correctness: Does it solve the problem?
2. Efficiency: Time and space complexity
3. Code Quality: Readability, structure, naming
4. Best Practices: Follows language conventions
5. Edge Cases: Handles edge cases
6. Security: Any security issues

Provide JSON response:
{{
    "score": 0.0-1.0,
    "feedback": "Detailed feedback",
    "strengths": ["strength1"],
    "weaknesses": ["weakness1"],
    "suggestions": ["suggestion1"],
    "correctness_score": 0.0-1.0,
    "efficiency_score": 0.0-1.0,
    "code_quality_score": 0.0-1.0,
    "complexity_analysis": {{
        "time": "O(n)",
        "space": "O(1)"
    }}
}}

Return only valid JSON:"""

    try:
        response = await gemini_client.generate_response(
            prompt=prompt,
            model="gemini-2.5-flash-lite",
            max_tokens=1500,
            temperature=0.3
        )
        
        if response:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                data = json.loads(response[json_start:json_end])
                
                return Evaluation(
                    score=float(data.get("score", 0.5)),
                    feedback=data.get("feedback", ""),
                    strengths=data.get("strengths", []),
                    weaknesses=data.get("weaknesses", []),
                    suggestions=data.get("suggestions", []),
                    next_difficulty=DifficultyLevel(2),  # Default for coding
                    skill_assessment={
                        "correctness": data.get("correctness_score", 0.5),
                        "efficiency": data.get("efficiency_score", 0.5),
                        "code_quality": data.get("code_quality_score", 0.5)
                    }
                )
    except Exception as e:
        print(f"Error evaluating code: {e}")
    
    # Fallback
    return Evaluation(
        score=0.5,
        feedback="Unable to evaluate code automatically.",
        next_difficulty=DifficultyLevel(2)
    )

