"""Question validation layer - ensures role-specific constraints are met."""
from interview_service.models import QuestionType
import logging

logger = logging.getLogger(__name__)


def validate_question(
    question: str,
    role: str,
    question_type: QuestionType
) -> tuple[bool, str]:
    """
    Validate question meets role-specific constraints.
    
    Returns:
        (is_valid, reason_if_invalid)
    """
    question_lower = question.lower()
    role_lower = role.lower()
    
    # HARD RULE: No coding questions for non-coding roles
    if question_type == QuestionType.CODING:
        non_coding_roles = ["tester", "qa", "devops", "product", "quality-assurance", "test-engineer"]
        if any(ncr in role_lower for ncr in non_coding_roles):
            return False, f"Coding questions not allowed for role: {role}"
    
    # Scenario enforcement - questions must include context/scenario
    scenario_keywords = [
        "scenario", "suppose", "imagine", "given", "consider",
        "situation", "example", "case", "context"
    ]
    has_scenario = any(kw in question_lower for kw in scenario_keywords)
    
    if not has_scenario and question_type != QuestionType.CODING:
        return False, "Question missing scenario/context keywords"
    
    # QA/Tester-specific enforcement - must ask for test cases/scenarios
    if "tester" in role_lower or "qa" in role_lower or "quality-assurance" in role_lower:
        test_keywords = ["test case", "test scenario", "testing", "verify", "validate", "test plan"]
        if not any(kw in question_lower for kw in test_keywords):
            return False, "QA/Tester role question missing testing keywords"
    
    # Generic question ban - avoid vague questions
    banned_phrases = ["tell me about", "explain", "what is"]
    for banned in banned_phrases:
        if banned in question_lower:
            # Allow only if followed by specific scenario (has_scenario check above)
            if not has_scenario:
                return False, f"Generic phrase '{banned}' without context"
    
    return True, ""

