"""Question pool for common skills - meaningful questions only."""
from typing import Dict, List, Optional
from interview_service.models import QuestionType, DifficultyLevel
import random


# Question pool for common skills - NO basic "what is X" questions
# Only meaningful, practical questions that assess real understanding
QUESTION_POOL = {
    "Java": {
        DifficultyLevel.INTERMEDIATE: [
            "How would you handle memory leaks in a long-running Java application?",
            "Explain the difference between ConcurrentHashMap and Hashtable, and when would you use each?",
            "How does the JVM garbage collector work, and what are the trade-offs between different GC algorithms?",
            "Describe how you would implement a thread-safe singleton pattern in Java.",
            "What are the best practices for handling exceptions in a REST API service?",
        ],
        DifficultyLevel.ADVANCED: [
            "How would you design a distributed caching system using Java?",
            "Explain how Java's classloader mechanism works and its implications for memory management.",
            "How would you optimize a Java application that's experiencing high latency under load?",
            "Describe the internals of Java's concurrent collections and how they achieve thread safety.",
            "How would you implement a custom annotation processor in Java?",
        ],
    },
    "Python": {
        DifficultyLevel.INTERMEDIATE: [
            "How would you handle memory management in a Python application processing large datasets?",
            "Explain the Global Interpreter Lock (GIL) and its impact on multi-threading in Python.",
            "What are the differences between multiprocessing and multithreading in Python, and when would you use each?",
            "How would you implement a decorator that caches function results with TTL?",
            "Explain Python's method resolution order (MRO) and how it affects inheritance.",
        ],
        DifficultyLevel.ADVANCED: [
            "How would you design an async task queue system in Python?",
            "Explain how Python's memory management works and how to profile memory usage.",
            "How would you implement a custom context manager for resource management?",
            "Describe how you would optimize a Python application for performance at scale.",
            "How would you implement a custom metaclass in Python?",
        ],
    },
    "React": {
        DifficultyLevel.INTERMEDIATE: [
            "How would you optimize a React application that's experiencing performance issues?",
            "Explain the differences between React hooks and class components, and when to use each.",
            "How would you manage state in a large React application with multiple components?",
            "Describe how React's reconciliation algorithm works and its performance implications.",
            "How would you implement a custom hook for data fetching with error handling and caching?",
        ],
        DifficultyLevel.ADVANCED: [
            "How would you design a state management solution for a complex React application?",
            "Explain React's concurrent features and how they improve user experience.",
            "How would you implement server-side rendering (SSR) in a React application?",
            "Describe how you would optimize a React application's bundle size and loading performance.",
            "How would you implement a custom renderer for React?",
        ],
    },
    "JavaScript": {
        DifficultyLevel.INTERMEDIATE: [
            "How would you handle asynchronous operations in JavaScript, and what are the trade-offs?",
            "Explain JavaScript's event loop and how it handles promises and callbacks.",
            "How would you implement a debounce function and when would you use it?",
            "Describe JavaScript's prototype chain and how it differs from classical inheritance.",
            "How would you handle memory leaks in a JavaScript application?",
        ],
        DifficultyLevel.ADVANCED: [
            "How would you design a module system for a large JavaScript application?",
            "Explain JavaScript's memory model and how garbage collection works.",
            "How would you implement a custom promise library in JavaScript?",
            "Describe how you would optimize a JavaScript application's runtime performance.",
            "How would you implement a custom JavaScript engine feature?",
        ],
    },
    "Database": {
        DifficultyLevel.INTERMEDIATE: [
            "How would you optimize a slow database query in a production environment?",
            "Explain the differences between different database isolation levels and when to use each.",
            "How would you design a database schema for a high-traffic application?",
            "Describe how database indexes work and their impact on query performance.",
            "How would you handle database migrations in a zero-downtime deployment?",
        ],
        DifficultyLevel.ADVANCED: [
            "How would you design a distributed database system for global scale?",
            "Explain database replication strategies and their trade-offs.",
            "How would you implement database sharding for horizontal scaling?",
            "Describe how you would optimize a database for both read and write performance.",
            "How would you design a database system that handles both OLTP and OLAP workloads?",
        ],
    },
    "System Design": {
        DifficultyLevel.ADVANCED: [
            "How would you design a URL shortener service like bit.ly that handles millions of requests?",
            "Design a real-time chat system that supports millions of concurrent users.",
            "How would you design a distributed file storage system like Google Drive?",
            "Design a recommendation system for an e-commerce platform.",
            "How would you design a search engine that indexes billions of documents?",
        ],
        DifficultyLevel.EXPERT: [
            "Design a global content delivery network (CDN) with minimal latency.",
            "How would you design a distributed transaction system across multiple services?",
            "Design a system that handles real-time analytics for billions of events.",
            "How would you design a system that ensures data consistency across distributed systems?",
            "Design a system that handles both batch and stream processing at scale.",
        ],
    },
}


def get_question_from_pool(
    skill: str,
    difficulty: DifficultyLevel,
    used_questions: Optional[List[str]] = None
) -> Optional[str]:
    """
    Get a question from the pool for a common skill.
    
    Args:
        skill: Skill name
        difficulty: Difficulty level
        used_questions: List of already used questions (to avoid repetition)
        
    Returns:
        Question text or None if no questions available
    """
    if skill not in QUESTION_POOL:
        return None
    
    skill_pool = QUESTION_POOL[skill]
    
    # Try to get question for exact difficulty
    if difficulty in skill_pool:
        available_questions = skill_pool[difficulty]
        
        # Filter out used questions
        if used_questions:
            available_questions = [q for q in available_questions if q not in used_questions]
        
        if available_questions:
            return random.choice(available_questions)
    
    # If no questions for exact difficulty, try adjacent difficulties
    if difficulty == DifficultyLevel.BASIC:
        # Try intermediate
        if DifficultyLevel.INTERMEDIATE in skill_pool:
            available = skill_pool[DifficultyLevel.INTERMEDIATE]
            if used_questions:
                available = [q for q in available if q not in used_questions]
            if available:
                return random.choice(available)
    
    elif difficulty == DifficultyLevel.EXPERT:
        # Try advanced
        if DifficultyLevel.ADVANCED in skill_pool:
            available = skill_pool[DifficultyLevel.ADVANCED]
            if used_questions:
                available = [q for q in available if q not in used_questions]
            if available:
                return random.choice(available)
    
    return None


def is_common_skill(skill: str) -> bool:
    """
    Check if a skill is common (has questions in pool).
    
    Args:
        skill: Skill name
        
    Returns:
        True if skill is in question pool
    """
    return skill in QUESTION_POOL


# Common skills that should use question pool
COMMON_SKILLS = set(QUESTION_POOL.keys())

