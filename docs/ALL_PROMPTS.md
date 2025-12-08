# All LLM Prompts Used in MockDay

This document contains all prompts used for question generation, answer evaluation, and report generation.

---

## 1. Question Generation Prompt

**File**: `backend/interview_service/question_generator.py`  
**Function**: `generate_question()`

### Current Prompt:
```
You are acting as an expert technical interviewer for the role: {role}. 

Your goal is to conduct a realistic, natural-sounding, professional interview.

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

3. **IMPORTANT - VARY question types**: 
   - 70% CONCEPTUAL/GENERAL: Ask about the skill ({skill}) itself, concepts, best practices, tradeoffs
   - 30% PROJECT-BASED: Ask about their specific project experience
   - DO NOT always ask about projects!

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

Do NOT include numbers, prefixes, explanations, or additional commentary.
```

---

## 2. Coding Question Generation Prompt

**File**: `backend/interview_service/question_generator.py`  
**Function**: `generate_coding_question()`

### Current Prompt:
```
You are a LeetCode problem generator. Create an ORIGINAL {leetcode_difficulty} difficulty coding problem.

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
{
  "tts_summary": "Please solve this coding question. [Natural 2-sentence description, NO code symbols]",
  "full_question": "# [Problem Title]\\n\\n## Problem Statement\\n[Clear explanation of what to solve]\\n\\n## Examples\\n\\n**Example 1:**\\n```\\nInput: [sample input]\\nOutput: [expected output]\\nExplanation: [why this output]\\n```\\n\\n**Example 2:**\\n```\\nInput: [sample]\\nOutput: [result]\\n```\\n\\n## Constraints\\n- [constraint 1]\\n- [constraint 2]\\n- [constraint 3]\\n\\n## Function Signature\\n```{language or 'python'}\\n[function definition with types]\\n```"
}

Generate NOW (JSON only):
```

---

## 3. Answer Evaluation Prompt

**File**: `backend/interview_service/answer_evaluator.py`  
**Function**: `evaluate_answer()`

### Current Prompt:
```
You are evaluating a candidate's answer in a technical interview.

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

## Evaluation Rules

- Use ONLY the provided question and answer.

- Do NOT invent information that was not said.

- Score must reflect technical correctness and clarity.

- Follow the scoring weights:

{criteria_desc}

## Output Requirements

Return a VALID JSON object with:

{
  "score": float between 0.0 and 1.0,
  "feedback": "detailed and helpful feedback",
  "strengths": [...],
  "weaknesses": [...],
  "suggestions": [...],
  "next_difficulty": 1 to 4,
  "skill_assessment": {
      "{question.skill}": float between 0.0 and 1.0
  }
}

Rules:

- JSON ONLY. No explanation.

- STRICT JSON. No trailing commas.

- Next difficulty logic:

  - Score >= 0.8 → increase difficulty by 1 (max 4)

  - Score >= 0.6 → keep same

  - Score < 0.6 → decrease by 1 (min 1)
```

---

## 4. Code Evaluation Prompt

**File**: `backend/interview_service/answer_evaluator.py`  
**Function**: `evaluate_code()`

### Current Prompt:
```
Analyze the following code submission:

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
{
    "score": 0.0-1.0,
    "feedback": "Detailed feedback",
    "strengths": ["strength1"],
    "weaknesses": ["weakness1"],
    "suggestions": ["suggestion1"],
    "correctness_score": 0.0-1.0,
    "efficiency_score": 0.0-1.0,
    "code_quality_score": 0.0-1.0,
    "complexity_analysis": {
        "time": "O(n)",
        "space": "O(1)"
    }
}

Return only valid JSON:
```

---

## 5. Report Generation Prompt

**File**: `backend/shared/providers/gemini_client.py`  
**Function**: `generate_report()`

### Current Prompt:
```
Generate a REALISTIC and HONEST interview evaluation report for a {role} position.

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
{self._serialize_profile(user_profile) if user_profile else "Not provided"}

**BE HONEST AND CRITICAL.** Don't inflate scores. If answers were vague, short, or incorrect, score accordingly.

Generate a detailed report in JSON format with:
- overall_score: integer (0-100) - BE REALISTIC based on actual performance
- section_scores: object with scores for different areas (technical, communication, problem_solving, etc.)
- strengths: list of strings (only if genuinely demonstrated)
- weaknesses: list of strings (be specific about gaps)
- detailed_feedback: string (comprehensive, honest feedback)
- recommendation: string (strong_hire, hire, maybe, no_hire)
- improvement_suggestions: list of strings (actionable suggestions)

Response (JSON only):
```

---

## ✅ Issues Fixed (December 2024)

### 1. Report Generation Issues - FIXED ✅
- **Problem**: With only 1 question answered, the report showed:
  - Progress bars for skills that weren't assessed
  - Generic strengths like "Participated in interview"
  - Scores for skills not evaluated
  
- **Solution Implemented**:
  - Report generation now only shows skills that were actually assessed
  - Section scores are filtered to only include evaluated skills
  - Strengths/weaknesses are now specific and only for skills that were evaluated
  - More explicit warnings for incomplete interviews
  - Score capping based on completion percentage

### 2. Question Generation Issues - IMPROVED ✅
- **Problem**: Questions might be too generic or repetitive
- **Solution Implemented**:
  - Better variation instructions (70% conceptual, 30% project-based)
  - Explicit instructions to alternate between question types
  - Better context awareness from previous questions/answers

### 3. Evaluation Issues - IMPROVED ✅
- **Problem**: Evaluation might be too lenient or not critical enough
- **Solution Implemented**:
  - Stricter scoring guidelines (0.9-1.0 exceptional, 0.7-0.89 good, etc.)
  - More critical evaluation instructions
  - Specific feedback requirements (reference what was said correctly/incorrectly)
  - No generic strengths/weaknesses

### 4. UI Issues - FIXED ✅
- **Problem**: Progress bars showing for skills not assessed, score alignment issues
- **Solution Implemented**:
  - UI now only shows progress bars for skills that were actually assessed
  - Better handling of empty skill scores
  - Fixed score circle alignment in ExecutiveSummary
  - Clear messages when no skills were assessed

---

## Updated Prompts (December 2024)

All prompts have been improved with:
- Stricter evaluation criteria
- Better handling of incomplete interviews
- More specific feedback requirements
- Better question variety instructions

