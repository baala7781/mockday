"""Gemini integration tests for interview service."""
import asyncio
import os
import sys
from typing import Optional

# Add parent directory to path (tests directory is one level deep)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interview_service.models import (
    InterviewRole, ResumeData, Skill, Project, Experience,
    DifficultyLevel, QuestionType
)
from interview_service.resume_analyzer import analyze_resume_with_llm, parse_resume_from_profile
from interview_service.question_generator import generate_question
from interview_service.answer_evaluator import evaluate_answer, evaluate_code
from interview_service.skill_weighting import calculate_skill_weights
from interview_service.question_pool import get_question_from_pool, is_common_skill
from shared.config.settings import settings
from shared.providers.gemini_client import gemini_client
from dotenv import load_dotenv

load_dotenv()


def check_api_keys():
    """Check if API keys are configured."""
    print("\n" + "="*60)
    print("Checking API Keys Configuration")
    print("="*60)
    
    gemini_keys = settings.GEMINI_API_KEYS
    if not gemini_keys:
        print("❌ GEMINI_API_KEYS not set in environment")
        print("   Please set GEMINI_API_KEYS in .env file or environment variable")
        print("   Example: GEMINI_API_KEYS=your-gemini-api-key-here")
        return False
    else:
        keys = [k.strip() for k in gemini_keys.split(",") if k.strip()]
        print(f"✅ GEMINI_API_KEYS found: {len(keys)} key(s)")
        for i, key in enumerate(keys, 1):
            masked_key = key[:10] + "..." + key[-4:] if len(key) > 14 else "***"
            print(f"   Key {i}: {masked_key}")
        return True


async def test_gemini_connection():
    """Test Gemini API connection."""
    print("\n" + "="*60)
    print("TEST 1: Gemini API Connection")
    print("="*60)
    
    try:
        response = await gemini_client.generate_response(
            prompt="Say 'Hello, World!' and nothing else.",
            model="gemini-2.0-flash-lite",
            max_tokens=50,
            temperature=0.7
        )
        
        if response:
            print(f"✅ Gemini API connection successful")
            print(f"   Response: {response}")
            return True
        else:
            print(f"❌ Gemini API connection failed: No response")
            return False
            
    except Exception as e:
        print(f"❌ Gemini API connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_question_generation():
    """Test question generation."""
    print("\n" + "="*60)
    print("TEST 2: Question Generation")
    print("="*60)
    
    try:
        # Create test resume data
        resume_data = ResumeData(
            skills=[
                Skill(name="Java", years=3, projects=["E-Commerce Platform"]),
                Skill(name="Python", years=2, projects=["Data Analytics Tool"]),
            ],
            projects=[
                Project(
                    name="E-Commerce Platform",
                    description="Built a scalable e-commerce platform",
                    technologies=["Java", "Spring Boot", "React"],
                    duration="6 months"
                ),
            ],
            experience=[
                Experience(
                    role="Backend Developer",
                    company="Tech Corp",
                    duration="2 years",
                    skills_used=["Java", "Spring Boot"]
                ),
            ],
            education=[]
        )
        
        # Generate question for Java skill
        question = await generate_question(
            skill="Java",
            difficulty=DifficultyLevel.INTERMEDIATE,
            role="backend-developer",
            resume_data=resume_data,
            question_type=QuestionType.PRACTICAL,
            previous_questions=None
        )
        
        if question:
            print(f"✅ Question generated successfully")
            print(f"   Question ID: {question.question_id}")
            print(f"   Skill: {question.skill}")
            print(f"   Difficulty: {question.difficulty}")
            print(f"   Type: {question.type.value}")
            print(f"   Question: {question.question}")
            return True
        else:
            print(f"❌ Question generation failed")
            return False
            
    except Exception as e:
        print(f"❌ Question generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_answer_evaluation():
    """Test answer evaluation."""
    print("\n" + "="*60)
    print("TEST 3: Answer Evaluation")
    print("="*60)
    
    try:
        from interview_service.models import Question, Answer
        
        # Create test question
        question = Question(
            question_id="test-q-1",
            question="How would you handle memory leaks in a long-running Java application?",
            skill="Java",
            difficulty=DifficultyLevel.INTERMEDIATE,
            type=QuestionType.PRACTICAL
        )
        
        # Create test answer
        answer = Answer(
            answer="I would use profiling tools like JProfiler or VisualVM to identify memory leaks. I would also implement proper resource management, use weak references where appropriate, and ensure that all resources are properly closed using try-with-resources statements.",
            code=None,
            language=None
        )
        
        # Evaluate answer
        evaluation = await evaluate_answer(
            question=question,
            answer=answer,
            previous_evaluations=None
        )
        
        if evaluation:
            print(f"✅ Answer evaluation successful")
            print(f"   Score: {evaluation.score:.2f}")
            print(f"   Feedback: {evaluation.feedback[:100]}...")
            print(f"   Strengths: {evaluation.strengths}")
            print(f"   Weaknesses: {evaluation.weaknesses}")
            print(f"   Next Difficulty: {evaluation.next_difficulty}")
            return True
        else:
            print(f"❌ Answer evaluation failed")
            return False
            
    except Exception as e:
        print(f"❌ Answer evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_resume_analysis():
    """Test resume analysis with Gemini."""
    print("\n" + "="*60)
    print("TEST 4: Resume Analysis")
    print("="*60)
    
    try:
        resume_text = """
        John Doe
        Backend Developer
        
        Experience:
        - Backend Developer at Tech Corp (2022-2024)
          * Developed microservices using Java and Spring Boot
          * Implemented REST APIs and database optimization
          * Worked with PostgreSQL and Redis
        
        Projects:
        - E-Commerce Platform (2023)
          * Built scalable e-commerce platform
          * Technologies: Java, Spring Boot, React, PostgreSQL
          * Duration: 6 months
        
        Skills:
        - Java (3 years)
        - Python (2 years)
        - Spring Boot (2 years)
        - PostgreSQL (2 years)
        - Redis (1 year)
        """
        
        resume_data = await analyze_resume_with_llm(resume_text)
        
        if resume_data:
            print(f"✅ Resume analysis successful")
            print(f"   Skills: {[s.name for s in resume_data.skills]}")
            print(f"   Projects: {[p.name for p in resume_data.projects]}")
            print(f"   Experience: {[e.role for e in resume_data.experience]}")
            return True
        else:
            print(f"❌ Resume analysis failed")
            return False
            
    except Exception as e:
        print(f"❌ Resume analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_phased_flow_with_gemini():
    """Test phased flow with Gemini integration."""
    print("\n" + "="*60)
    print("TEST 5: Phased Flow with Gemini")
    print("="*60)
    
    try:
        from interview_service.phased_flow import select_next_question_phased
        from interview_service.interview_state import create_interview_state
        
        # Create test resume data
        resume_data = ResumeData(
            skills=[
                Skill(name="Java", years=3, projects=["E-Commerce Platform"]),
                Skill(name="Python", years=2, projects=["Data Analytics Tool"]),
            ],
            projects=[
                Project(
                    name="E-Commerce Platform",
                    description="Built a scalable e-commerce platform",
                    technologies=["Java", "Spring Boot", "React"],
                    duration="6 months"
                ),
            ],
            experience=[
                Experience(
                    role="Backend Developer",
                    company="Tech Corp",
                    duration="2 years",
                    skills_used=["Java", "Spring Boot"]
                ),
            ],
            education=[]
        )
        
        # Calculate skill weights
        skill_weights = calculate_skill_weights(InterviewRole.BACKEND_DEVELOPER, resume_data)
        
        # Create interview state
        interview_state = await create_interview_state(
            user_id="test_user_123",
            role=InterviewRole.BACKEND_DEVELOPER,
            resume_data=resume_data,
            skill_weights=skill_weights,
            max_questions=12
        )
        
        print(f"✅ Interview state created")
        print(f"   Phase: {interview_state.current_phase.value}")
        print(f"   Projects: {len(interview_state.resume_data.projects)}")
        
        # Generate first question (should be project question)
        first_question = await select_next_question_phased(interview_state)
        
        if first_question:
            print(f"✅ First question generated")
            print(f"   Skill: {first_question.skill}")
            print(f"   Phase: {first_question.context.get('phase') if first_question.context else 'N/A'}")
            print(f"   Source: {first_question.context.get('source') if first_question.context else 'N/A'}")
            print(f"   Question: {first_question.question[:100]}...")
            return True
        else:
            print(f"❌ Failed to generate first question")
            return False
            
    except Exception as e:
        print(f"❌ Phased flow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all Gemini integration tests."""
    print("\n" + "="*60)
    print("GEMINI INTEGRATION TEST SUITE")
    print("="*60)
    print("\nThis test suite tests LLM integration with Google Gemini.")
    print("Make sure GEMINI_API_KEYS is set in .env file or environment variable.")
    
    # Check API keys
    if not check_api_keys():
        print("\n⚠️  Please set GEMINI_API_KEYS before running tests")
        print("   Create a .env file in the backend directory with:")
        print("   GEMINI_API_KEYS=your-gemini-api-key-here")
        return
    
    results = []
    
    try:
        # Test 1: Gemini connection
        results.append(("Gemini Connection", await test_gemini_connection()))
        
        # Test 2: Question generation
        results.append(("Question Generation", await test_question_generation()))
        
        # Test 3: Answer evaluation
        results.append(("Answer Evaluation", await test_answer_evaluation()))
        
        # Test 4: Resume analysis
        results.append(("Resume Analysis", await test_resume_analysis()))
        
        # Test 5: Phased flow with Gemini
        results.append(("Phased Flow with Gemini", await test_phased_flow_with_gemini()))
        
        # Print summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"   {test_name}: {status}")
        
        print(f"\n   Total: {passed}/{total} tests passed")
        
        if passed == total:
            print("\n✅ ALL TESTS PASSED")
        else:
            print(f"\n⚠️  {total - passed} test(s) failed")
        
    except Exception as e:
        print(f"\n❌ TEST SUITE FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

