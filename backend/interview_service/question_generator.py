"""Question generation using LLM."""
from typing import Dict, Any, Optional, List
from interview_service.models import Question, QuestionType, DifficultyLevel, ResumeData, InterviewState
from shared.providers.gemini_client import gemini_client
from interview_service.memory_controller import (
    get_conversation_context_for_question,
    get_relevant_resume_context_for_skill
)
from interview_service.conversational_framing import get_candidate_name_safely
import uuid
import json
import logging

logger = logging.getLogger(__name__)


DIFFICULTY_NAMES = {
    1: "Basic",
    2: "Intermediate",
    3: "Advanced",
    4: "Expert"
}

QUESTION_TYPE_NAMES = {
    QuestionType.CONCEPTUAL: "conceptual",
    QuestionType.PRACTICAL: "practical",
    QuestionType.CODING: "coding",
    QuestionType.SYSTEM_DESIGN: "system design"
}


async def generate_question(
    skill: str,
    difficulty: DifficultyLevel,
    role: str,
    resume_data: Optional[ResumeData] = None,
    question_type: Optional[QuestionType] = None,
    previous_questions: Optional[List[str]] = None,
    previous_answers: Optional[List[str]] = None,
    state: Optional[InterviewState] = None,
    candidate_name: Optional[str] = None
) -> Question:
    """
    Generate an interview question using LLM.
    
    Args:
        skill: Skill to assess
        difficulty: Difficulty level
        role: Interview role
        resume_data: Candidate's resume data
        question_type: Type of question (optional, will be determined if not provided)
        previous_questions: List of previous questions (to avoid repetition)
        previous_answers: List of previous answers (for context)
        
    Returns:
        Generated question
    """
    # Determine question type if not provided
    if not question_type:
        if difficulty <= 2:
            question_type = QuestionType.CONCEPTUAL
        elif difficulty == 3:
            question_type = QuestionType.PRACTICAL
        else:
            question_type = QuestionType.SYSTEM_DESIGN
    
    # Use memory controller to get minimal context (prevents LLM fatigue)
    if state:
        conv_context = get_conversation_context_for_question(state, skill, resume_data)
        resume_context = conv_context["resume_summary"]
        previous_questions_list = conv_context.get("previous_questions", [])
        previous_answers_list = conv_context.get("previous_answers", [])
    else:
        # Fallback if state not provided (backward compatibility)
        resume_context = get_relevant_resume_context_for_skill(resume_data, skill)
        previous_questions_list = previous_questions or []
        previous_answers_list = previous_answers or []
    
    # Build minimal previous context (last 2 questions)
    previous_context = ""
    if previous_questions_list:
        questions_text = "\n".join([f"- {q}" for q in previous_questions_list[-2:]])
        previous_context = f"Last 2 questions you asked:\n{questions_text}"
    
    # Build minimal answer context (last 2 answer summaries)
    answers_context = ""
    if previous_answers_list:
        answers_text = "\n".join([f"- {a}" for a in previous_answers_list[-2:]])
        answers_context = f"Brief summary of candidate's last 2 answers:\n{answers_text}"
    
    # Safety: Get candidate name safely (never invent names)
    safe_name = candidate_name if candidate_name else None
    name_instruction = f"Address the candidate as '{safe_name}'" if safe_name else "Address the candidate as 'you' (do NOT invent or use any names)"
    
    # Generate prompt with new format (more natural, less rules)
    prompt = f"""You are acting as an expert technical interviewer for the role: {role}. 

Your goal is to conduct a realistic, natural-sounding, professional interview that accurately assesses the candidate's skills.

## Candidate Background

- Target Skill: {skill}

- Difficulty Level: {difficulty} ({DIFFICULTY_NAMES[difficulty]})

- Question Type: {QUESTION_TYPE_NAMES[question_type]}

- Resume Context (if given):

{resume_context if resume_context else "Not provided"}

## Conversation Context

{previous_context if previous_context else "None yet."}

{answers_context if answers_context else "No answers yet."}

## Your Task

Generate ONE natural-sounding interview question that:

1. Flows naturally from the previous conversation.

2. DOES NOT repeat any previous questions.

3. **IMPORTANT - VARY question types and avoid repetition**: 
   - 70% CONCEPTUAL/GENERAL: Ask about the skill ({skill}) itself, concepts, best practices, tradeoffs, real-world scenarios
   - 30% PROJECT-BASED: Ask about their specific project experience (only if relevant and not already covered)
   - DO NOT always ask about projects! Mix conceptual questions with practical scenarios
   - If previous questions were about projects, switch to conceptual/theoretical
   - If previous questions were conceptual, you can ask about projects but make it specific and different

4. Reflects the difficulty level accurately.

5. Focuses on real-world application and problem-solving.

6. Is short (1–2 sentences).

7. **CRITICAL - AVOID THESE BANNED PHRASES**:
   - NEVER start with "Tell me about your..."
   - NEVER start with "Okay..." or "Okay, so..."
   - NEVER start with "Regarding your experience with..."
   - NEVER start with "In your [project name]..."
   - NEVER combine two questions in one message
   
8. **USE THESE OPENERS** (pick randomly):
   - "How would you explain..."
   - "What's your approach to..."
   - "Can you walk me through how..."
   - "What are the key considerations when..."
   - "How do you typically handle..."
   - "What's the difference between..."
   - "When would you choose X over Y..."
   - "What challenges have you seen with..."
   - "How would you optimize..."
   - "What's your experience with..."

9. {name_instruction}. NEVER invent, guess, or use personal names that were not provided.

## Output Format

Return ONLY the question text. 

Do NOT include numbers, prefixes, explanations, or additional commentary."""

    # Log what we're requesting from LLM
    logger.info(f"🤖 [LLM Question Generation] Requesting question from LLM:")
    logger.info(f"   Skill: {skill}, Difficulty: {DIFFICULTY_NAMES[difficulty]}, Type: {QUESTION_TYPE_NAMES[question_type]}, Role: {role}")
    if resume_data and resume_data.projects:
        logger.info(f"   Resume context: {len(resume_data.projects)} projects available for reference")

    try:
        response = await gemini_client.generate_response(
            prompt=prompt,
            model="gemini-2.5-flash-lite",
            max_tokens=500,
            temperature=0.7,
            interview_id=state.interview_id if state else None  # Pass interview_id for BYOK support
        )
        
        if response:
            logger.info(f"🤖 [LLM Question Generation] Received response from LLM (length: {len(response)} chars)")
            logger.debug(f"🤖 [LLM Question Generation] Full LLM response: {response}")
            
            # Clean up response
            question_text = response.strip()
            # Remove quotes if present
            if question_text.startswith('"') and question_text.endswith('"'):
                question_text = question_text[1:-1]
            
            logger.info(f"🤖 [LLM Question Generation] Generated question: '{question_text[:100]}...'")
            
            return Question(
                question_id=str(uuid.uuid4()),
                question=question_text,
                skill=skill,
                difficulty=difficulty,
                type=question_type,
                context={
                    "role": role,
                    "resume_context": resume_context
                }
            )
    except Exception as e:
        print(f"Error generating question: {e}")
    
    # Fallback question
    return Question(
        question_id=str(uuid.uuid4()),
        question=f"Tell me about your experience with {skill}.",
        skill=skill,
        difficulty=difficulty,
        type=question_type
    )


async def generate_coding_question(
    skill: str,
    difficulty: DifficultyLevel,
    role: str,
    language: Optional[str] = None
) -> Question:
    """
    Generate a coding question.
    
    Args:
        skill: Skill to assess
        difficulty: Difficulty level
        role: Interview role
        language: Programming language (optional)
        
    Returns:
        Generated coding question
    """
    # Map difficulty to LeetCode difficulty
    leetcode_difficulty = "Easy" if difficulty.value <= 2 else "Medium" if difficulty.value <= 3 else "Hard"
    
    prompt = f"""You are a LeetCode problem generator. Create an ORIGINAL {leetcode_difficulty} difficulty coding problem.

**CRITICAL**: Return ONLY valid JSON. No markdown, no explanations, just pure JSON.

Problem Requirements:
- Skill focus: {skill}
- Difficulty: {leetcode_difficulty}
- Language: {language or "Python"}
- Interview role: {role}

Create a problem inspired by real LeetCode patterns:
- Easy: Arrays, strings, hash maps, basic iteration (e.g., Two Sum, Palindrome)
- Medium: Two pointers, sliding window, linked lists, stacks (e.g., Longest Substring)
- Hard: Dynamic programming, graphs, backtracking (e.g., Edit Distance)

Return this EXACT JSON structure (no markdown blocks):
{{
  "tts_summary": "Please solve this coding question. [Natural 2-sentence description, NO code symbols]",
  "full_question": "# [Problem Title]\\n\\n## Problem Statement\\n[Clear explanation of what to solve]\\n\\n## Examples\\n\\n**Example 1:**\\n```\\nInput: [sample input]\\nOutput: [expected output]\\nExplanation: [why this output]\\n```\\n\\n**Example 2:**\\n```\\nInput: [sample]\\nOutput: [result]\\n```\\n\\n## Constraints\\n- [constraint 1]\\n- [constraint 2]\\n- [constraint 3]\\n\\n## Function Signature\\n```{language or 'python'}\\n[function definition with types]\\n```"
}}

Generate NOW (JSON only):"""

    try:
        # Try LLM generation first with increased temperature for variety
        response = await gemini_client.generate_response(
            prompt=prompt,
            model="gemini-2.5-flash-lite",
            max_tokens=1500,
            temperature=0.85,  # Higher for more creative/varied problems
            interview_id=state.interview_id if state else None  # Pass interview_id for BYOK support
        )
        
        if response:
            import json
            import re
            import logging
            logger = logging.getLogger(__name__)
            
            logger.info(f"[Coding Q] Raw LLM response length: {len(response)}")
            logger.debug(f"[Coding Q] Raw response: {response[:500]}")
            
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if not json_match:
                # Try without code blocks
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1) if json_match.lastindex else json_match.group()
                try:
                    data = json.loads(json_str)
                    full_question = data.get("full_question", "")
                    tts_summary = data.get("tts_summary", "")
                    
                    if full_question and tts_summary:
                        logger.info(f"[Coding Q] ✓ Successfully parsed JSON question")
                        return Question(
                            question_id=str(uuid.uuid4()),
                            question=full_question,
                            skill=skill,
                            difficulty=difficulty,
                            type=QuestionType.CODING,
                            context={
                                "language": language,
                                "role": role,
                                "tts_text": tts_summary,
                                "leetcode_difficulty": leetcode_difficulty
                            }
                        )
                    else:
                        logger.warning(f"[Coding Q] JSON missing fields: full_question={bool(full_question)}, tts_summary={bool(tts_summary)}")
                except json.JSONDecodeError as je:
                    logger.error(f"[Coding Q] JSON parse error: {je}")
                    logger.debug(f"[Coding Q] Failed JSON string: {json_str[:200]}")
            else:
                logger.warning(f"[Coding Q] No JSON found in response")
            
            # Fallback: Use response as-is with simple TTS
            question_text = response.strip()
            if question_text.startswith('"') and question_text.endswith('"'):
                question_text = question_text[1:-1]
            
            # Extract first 2 sentences for TTS
            sentences = question_text.split('.')[:2]
            tts_fallback = '. '.join(sentences) + '.'
            
            logger.info(f"[Coding Q] Using fallback formatting")
            return Question(
                question_id=str(uuid.uuid4()),
                question=question_text,
                skill=skill,
                difficulty=difficulty,
                type=QuestionType.CODING,
                context={
                    "language": language,
                    "role": role,
                    "tts_text": f"Please solve this coding question. {tts_fallback}"
                }
            )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating coding question: {e}", exc_info=True)
    
    # Hardcoded fallback - Real LeetCode problems (for reliability and variety)
    leetcode_problems = {
        "easy": {
            "Reverse String": {
                "full": """# Reverse String

## Problem Statement
Write a function that reverses a string. The input string is given as an array of characters `s`.

You must do this by modifying the input array in-place with O(1) extra memory.

## Examples

**Example 1:**
```
Input: s = ["h","e","l","l","o"]
Output: ["o","l","l","e","h"]
```

**Example 2:**
```
Input: s = ["H","a","n","n","a","h"]
Output: ["h","a","n","n","a","H"]
```

## Constraints
- 1 <= s.length <= 10^5
- s[i] is a printable ascii character

## Function Signature
```python
def reverseString(s: List[str]) -> None:
    \"\"\"
    Do not return anything, modify s in-place instead.
    \"\"\"
    pass
```""",
                "tts": "Please solve this coding question. Reverse a string in-place using only constant extra space."
            },
            "Two Sum": {
                "full": """# Two Sum

## Problem Statement
Given an array of integers `nums` and an integer `target`, return indices of the two numbers such that they add up to `target`.

You may assume that each input would have exactly one solution, and you may not use the same element twice.

## Examples

**Example 1:**
```
Input: nums = [2,7,11,15], target = 9
Output: [0,1]
Explanation: Because nums[0] + nums[1] == 9, we return [0, 1].
```

**Example 2:**
```
Input: nums = [3,2,4], target = 6
Output: [1,2]
```

## Constraints
- 2 <= nums.length <= 10^4
- -10^9 <= nums[i] <= 10^9
- -10^9 <= target <= 10^9
- Only one valid answer exists

## Function Signature
```python
def twoSum(nums: List[int], target: int) -> List[int]:
    pass
```""",
                "tts": "Please solve this coding question. Given an array of integers and a target value, find the indices of two numbers that add up to the target."
            },
            "Valid Parentheses": {
                "full": """# Valid Parentheses

## Problem Statement
Given a string `s` containing just the characters '(', ')', '{', '}', '[' and ']', determine if the input string is valid.

An input string is valid if:
- Open brackets must be closed by the same type of brackets.
- Open brackets must be closed in the correct order.
- Every close bracket has a corresponding open bracket of the same type.

## Examples

**Example 1:**
```
Input: s = "()"
Output: true
```

**Example 2:**
```
Input: s = "()[]{}"
Output: true
```

**Example 3:**
```
Input: s = "(]"
Output: false
```

## Constraints
- 1 <= s.length <= 10^4
- s consists of parentheses only '()[]{}'

## Function Signature
```python
def isValid(s: str) -> bool:
    pass
```""",
                "tts": "Please solve this coding question. Check if a string of parentheses is valid, where each opening bracket has a matching closing bracket in the correct order."
            },
            "Palindrome Number": {
                "full": """# Palindrome Number

## Problem Statement
Given an integer `x`, return `true` if `x` is a palindrome, and `false` otherwise.

## Examples

**Example 1:**
```
Input: x = 121
Output: true
Explanation: 121 reads as 121 from left to right and from right to left.
```

**Example 2:**
```
Input: x = -121
Output: false
Explanation: From left to right, it reads -121. From right to left, it becomes 121-. Therefore it is not a palindrome.
```

**Example 3:**
```
Input: x = 10
Output: false
```

## Constraints
- -2^31 <= x <= 2^31 - 1

## Function Signature
```python
def isPalindrome(x: int) -> bool:
    pass
```""",
                "tts": "Please solve this coding question. Determine if an integer is a palindrome without converting it to a string."
            },
            "Merge Two Sorted Lists": {
                "full": """# Merge Two Sorted Lists

## Problem Statement
You are given the heads of two sorted linked lists `list1` and `list2`.

Merge the two lists into one sorted list. The list should be made by splicing together the nodes of the first two lists.

Return the head of the merged linked list.

## Examples

**Example 1:**
```
Input: list1 = [1,2,4], list2 = [1,3,4]
Output: [1,1,2,3,4,4]
```

**Example 2:**
```
Input: list1 = [], list2 = []
Output: []
```

**Example 3:**
```
Input: list1 = [], list2 = [0]
Output: [0]
```

## Constraints
- The number of nodes in both lists is in the range [0, 50]
- -100 <= Node.val <= 100
- Both list1 and list2 are sorted in non-decreasing order

## Function Signature
```python
def mergeTwoLists(list1: Optional[ListNode], list2: Optional[ListNode]) -> Optional[ListNode]:
    pass
```""",
                "tts": "Please solve this coding question. Merge two sorted linked lists into one sorted list."
            }
        },
        "medium": {
            "Add Two Numbers": {
                "full": """# Add Two Numbers

## Problem Statement
You are given two non-empty linked lists representing two non-negative integers. The digits are stored in reverse order, and each of their nodes contains a single digit. Add the two numbers and return the sum as a linked list.

## Examples

**Example 1:**
```
Input: l1 = [2,4,3], l2 = [5,6,4]
Output: [7,0,8]
Explanation: 342 + 465 = 807
```

**Example 2:**
```
Input: l1 = [0], l2 = [0]
Output: [0]
```

**Example 3:**
```
Input: l1 = [9,9,9,9,9,9,9], l2 = [9,9,9,9]
Output: [8,9,9,9,0,0,0,1]
```

## Constraints
- The number of nodes in each linked list is in the range [1, 100]
- 0 <= Node.val <= 9
- It is guaranteed that the list represents a number that does not have leading zeros

## Function Signature
```python
def addTwoNumbers(l1: Optional[ListNode], l2: Optional[ListNode]) -> Optional[ListNode]:
    pass
```""",
                "tts": "Please solve this coding question. Add two numbers represented as reversed linked lists and return the sum as a linked list."
            },
            "Longest Substring Without Repeating Characters": {
                "full": """# Longest Substring Without Repeating Characters

## Problem Statement
Given a string `s`, find the length of the longest substring without repeating characters.

## Examples

**Example 1:**
```
Input: s = "abcabcbb"
Output: 3
Explanation: The answer is "abc", with the length of 3.
```

**Example 2:**
```
Input: s = "bbbbb"
Output: 1
Explanation: The answer is "b", with the length of 1.
```

**Example 3:**
```
Input: s = "pwwkew"
Output: 3
Explanation: The answer is "wke", with the length of 3.
```

## Constraints
- 0 <= s.length <= 5 * 10^4
- s consists of English letters, digits, symbols and spaces

## Function Signature
```python
def lengthOfLongestSubstring(s: str) -> int:
    pass
```""",
                "tts": "Please solve this coding question. Find the length of the longest substring in a string where no character repeats."
            }
        }
    }
    
    # Select appropriate problem based on difficulty
    problem_set = leetcode_problems.get("easy" if difficulty.value <= 2 else "medium", leetcode_problems["easy"])
    import random
    problem_name = random.choice(list(problem_set.keys()))
    problem_data = problem_set[problem_name]
    
    return Question(
        question_id=str(uuid.uuid4()),
        question=problem_data["full"],
        skill=skill,
        difficulty=difficulty,
        type=QuestionType.CODING,
        context={
            "language": language,
            "role": role,
            "tts_text": problem_data["tts"],
            "leetcode_difficulty": leetcode_difficulty,
            "problem_name": problem_name
        }
    )

