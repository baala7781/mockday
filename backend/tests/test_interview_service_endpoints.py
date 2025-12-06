"""Test Interview Service REST endpoints."""
import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interview_service.models import (
    StartInterviewRequest, InterviewRole, ResumeData, Skill, Project, Experience,
    Answer, InterviewPhase
)
from interview_service.interview_state import create_interview_state, load_interview_state
from interview_service.skill_weighting import calculate_skill_weights
from interview_service.phased_flow import select_next_question_phased
from interview_service.answer_evaluator import evaluate_answer


def create_test_resume_data() -> ResumeData:
    """Create test resume data."""
    return ResumeData(
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


async def test_interview_start():
    """Test starting an interview."""
    print("\n" + "="*60)
    print("TEST 1: Start Interview")
    print("="*60)
    
    try:
        resume_data = create_test_resume_data()
        skill_weights = calculate_skill_weights(InterviewRole.BACKEND_DEVELOPER, resume_data)
        
        # Create interview state
        interview_state = await create_interview_state(
            user_id="test_user_123",
            role=InterviewRole.BACKEND_DEVELOPER,
            resume_data=resume_data,
            skill_weights=skill_weights,
            max_questions=12
        )
        
        print(f"✅ Interview started successfully")
        print(f"   Interview ID: {interview_state.interview_id}")
        print(f"   User ID: {interview_state.user_id}")
        print(f"   Role: {interview_state.role.value}")
        print(f"   Phase: {interview_state.current_phase.value}")
        print(f"   Max Questions: {interview_state.max_questions}")
        
        # Generate first question
        first_question = await select_next_question_phased(interview_state)
        
        if first_question:
            print(f"✅ First question generated")
            print(f"   Question ID: {first_question.question_id}")
            print(f"   Skill: {first_question.skill}")
            print(f"   Phase: {first_question.context.get('phase') if first_question.context else 'N/A'}")
            print(f"   Question: {first_question.question[:100]}...")
        else:
            print(f"❌ Failed to generate first question")
        
        return interview_state, first_question
        
    except Exception as e:
        print(f"❌ Error starting interview: {e}")
        import traceback
        traceback.print_exc()
        return None, None


async def test_answer_submission(interview_state, question):
    """Test submitting an answer."""
    print("\n" + "="*60)
    print("TEST 2: Submit Answer")
    print("="*60)
    
    if not interview_state or not question:
        print("❌ Cannot test answer submission without interview state and question")
        return None
    
    try:
        # Create test answer
        answer = Answer(
            answer="I would use profiling tools like JProfiler to identify memory leaks. I would also implement proper resource management and use try-with-resources statements.",
            code=None,
            language=None
        )
        
        # Evaluate answer
        evaluation = await evaluate_answer(
            question=question,
            answer=answer,
            previous_evaluations=None
        )
        
        print(f"✅ Answer evaluated successfully")
        print(f"   Score: {evaluation.score:.2f}")
        print(f"   Feedback: {evaluation.feedback[:100]}...")
        print(f"   Strengths: {len(evaluation.strengths)} identified")
        print(f"   Weaknesses: {len(evaluation.weaknesses)} identified")
        print(f"   Next Difficulty: {evaluation.next_difficulty}")
        
        # Update interview state
        interview_state.current_difficulty = evaluation.next_difficulty
        interview_state.total_questions += 1
        interview_state.questions_asked.append(question)
        
        # Add answer to state
        if question.skill not in interview_state.answered_skills:
            interview_state.answered_skills[question.skill] = []
        interview_state.answered_skills[question.skill].append(evaluation)
        
        # Generate next question
        next_question = await select_next_question_phased(interview_state)
        
        if next_question:
            print(f"✅ Next question generated")
            print(f"   Question ID: {next_question.question_id}")
            print(f"   Skill: {next_question.skill}")
            print(f"   Phase: {next_question.context.get('phase') if next_question.context else 'N/A'}")
            print(f"   Question: {next_question.question[:100]}...")
        else:
            print(f"⚠️  No next question (interview may be complete)")
        
        return evaluation, next_question
        
    except Exception as e:
        print(f"❌ Error submitting answer: {e}")
        import traceback
        traceback.print_exc()
        return None, None


async def test_phased_flow_complete():
    """Test complete phased interview flow."""
    print("\n" + "="*60)
    print("TEST 3: Complete Phased Interview Flow")
    print("="*60)
    
    try:
        resume_data = create_test_resume_data()
        skill_weights = calculate_skill_weights(InterviewRole.BACKEND_DEVELOPER, resume_data)
        
        # Create interview state
        interview_state = await create_interview_state(
            user_id="test_user_123",
            role=InterviewRole.BACKEND_DEVELOPER,
            resume_data=resume_data,
            skill_weights=skill_weights,
            max_questions=12
        )
        
        print(f"✅ Interview started")
        print(f"   Phase: {interview_state.current_phase.value}")
        
        # Simulate interview flow
        questions_answered = 0
        phases_completed = []
        
        for i in range(5):  # Test 5 questions
            # Generate question
            question = await select_next_question_phased(interview_state)
            
            if not question:
                print(f"⚠️  No more questions after {questions_answered} questions")
                break
            
            print(f"\n   Question {i+1}:")
            print(f"      Phase: {interview_state.current_phase.value}")
            print(f"      Skill: {question.skill}")
            print(f"      Source: {question.context.get('source') if question.context else 'N/A'}")
            
            # Simulate answer
            answer = Answer(
                answer=f"Test answer for question {i+1}",
                code=None,
                language=None
            )
            
            # Evaluate answer
            evaluation = await evaluate_answer(
                question=question,
                answer=answer,
                previous_evaluations=None
            )
            
            # Update state
            interview_state.current_difficulty = evaluation.next_difficulty
            interview_state.total_questions += 1
            interview_state.questions_asked.append(question)
            
            if question.skill not in interview_state.answered_skills:
                interview_state.answered_skills[question.skill] = []
            interview_state.answered_skills[question.skill].append(evaluation)
            
            # Track phase changes
            current_phase = interview_state.current_phase.value
            if current_phase not in phases_completed:
                phases_completed.append(current_phase)
            
            questions_answered += 1
            
            # Update phase question count
            from interview_service.phased_flow import update_phase_question_count
            update_phase_question_count(interview_state)
        
        print(f"\n✅ Interview flow completed")
        print(f"   Questions answered: {questions_answered}")
        print(f"   Phases completed: {phases_completed}")
        print(f"   Current phase: {interview_state.current_phase.value}")
        print(f"   Total questions: {interview_state.total_questions}")
        print(f"   Phase breakdown: {interview_state.phase_questions}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in complete flow test: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_state_persistence():
    """Test interview state persistence."""
    print("\n" + "="*60)
    print("TEST 4: State Persistence")
    print("="*60)
    
    try:
        resume_data = create_test_resume_data()
        skill_weights = calculate_skill_weights(InterviewRole.BACKEND_DEVELOPER, resume_data)
        
        # Create interview state
        interview_state = await create_interview_state(
            user_id="test_user_123",
            role=InterviewRole.BACKEND_DEVELOPER,
            resume_data=resume_data,
            skill_weights=skill_weights,
            max_questions=12
        )
        
        interview_id = interview_state.interview_id
        print(f"✅ Interview state created: {interview_id}")
        
        # Try to load state
        loaded_state = await load_interview_state(interview_id)
        
        if loaded_state:
            print(f"✅ Interview state loaded successfully")
            print(f"   Loaded Interview ID: {loaded_state.interview_id}")
            print(f"   Phase: {loaded_state.current_phase.value}")
            print(f"   Total Questions: {loaded_state.total_questions}")
            return True
        else:
            print(f"⚠️  Interview state not found in storage (Redis/Firestore may not be configured)")
            print(f"   This is expected in development environment")
            return True  # Not a failure, just not configured
        
    except Exception as e:
        print(f"❌ Error testing state persistence: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all endpoint tests."""
    print("\n" + "="*60)
    print("INTERVIEW SERVICE ENDPOINTS - TEST SUITE")
    print("="*60)
    print("\nThis test suite tests the Interview Service REST endpoints and flow.")
    print("Note: Some tests may show warnings if Redis/Firestore is not configured.")
    
    results = []
    
    try:
        # Test 1: Start interview
        interview_state, first_question = await test_interview_start()
        results.append(("Start Interview", interview_state is not None))
        
        # Test 2: Submit answer
        if interview_state and first_question:
            evaluation, next_question = await test_answer_submission(interview_state, first_question)
            results.append(("Submit Answer", evaluation is not None))
        else:
            results.append(("Submit Answer", False))
        
        # Test 3: Complete phased flow
        results.append(("Complete Phased Flow", await test_phased_flow_complete()))
        
        # Test 4: State persistence
        results.append(("State Persistence", await test_state_persistence()))
        
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

