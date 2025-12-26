"""Pydantic models for interview service."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class InterviewRole(str, Enum):
    """Interview roles."""
    BACKEND_DEVELOPER = "backend-developer"
    FRONTEND_DEVELOPER = "frontend-developer"
    FULLSTACK_DEVELOPER = "fullstack-developer"
    DATA_SCIENTIST = "data-scientist"
    DATA_SCIENCE = "data-science"
    DATA_ENGINEER = "data-engineer"
    GRADUATE = "graduate"
    GRADUATE_DATA_ENGINEER = "graduate-data-engineer"
    GRADUATE_DATA_SCIENTIST = "graduate-data-scientist"
    DEVOPS_ENGINEER = "devops-engineer"
    MACHINE_LEARNING_ENGINEER = "machine-learning-engineer"
    CLOUD_ENGINEER = "cloud-engineer"
    SECURITY_ENGINEER = "security-engineer"
    PRODUCT_MANAGER = "product-manager"
    SOFTWARE_ENGINEER = "software-engineer"


class QuestionType(str, Enum):
    """Question types."""
    CONCEPTUAL = "conceptual"
    PRACTICAL = "practical"
    CODING = "coding"
    SYSTEM_DESIGN = "system_design"


class DifficultyLevel(int, Enum):
    """Difficulty levels."""
    BASIC = 1
    INTERMEDIATE = 2
    ADVANCED = 3
    EXPERT = 4


class InterviewStatus(str, Enum):
    """Interview status."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class InterviewPhase(str, Enum):
    """Interview phases."""
    INTRODUCTION = "introduction"  # Phase 0: General introduction question
    PROJECTS = "projects"  # Phase 1: Questions on projects
    STANDOUT_SKILLS = "standout_skills"  # Phase 2: Skills that demonstrate capabilities
    ROLE_SKILLS = "role_skills"  # Phase 3: Skills required for the role


class InterviewFlowState(str, Enum):
    """Interview flow state machine for real-time STT/TTS orchestration."""
    AI_SPEAKING = "ai_speaking"  # TTS playing, STT off
    USER_SPEAKING = "user_speaking"  # STT on, TTS silent
    AI_THINKING = "ai_thinking"  # LLM evaluation running, STT off, TTS off
    USER_WAITING = "user_waiting"  # Waiting for TTS to finish
    INTERVIEW_COMPLETE = "interview_complete"  # Interview finished


# Resume Models
class Skill(BaseModel):
    """Skill model."""
    name: str
    years: Optional[float] = 0
    projects: List[str] = Field(default_factory=list)


class Project(BaseModel):
    """Project model."""
    name: str
    description: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)
    duration: Optional[str] = None


class Experience(BaseModel):
    """Experience model."""
    role: str
    company: str
    duration: Optional[str] = None
    skills_used: List[str] = Field(default_factory=list)


class ResumeData(BaseModel):
    """Resume data model."""
    skills: List[Skill] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    experience: List[Experience] = Field(default_factory=list)
    education: List[Dict[str, Any]] = Field(default_factory=list)


class SkillWeight(BaseModel):
    """Skill weight model."""
    skill: str
    weight: float
    role_relevance: float
    resume_experience: float
    project_count: float


# Interview Models
class StartInterviewRequest(BaseModel):
    """Start interview request."""
    user_id: str
    role: str  # Can be InterviewRole enum value or custom role string
    resume_id: Optional[str] = None
    resume_data: Optional[ResumeData] = None
    byok_openrouter_key: Optional[str] = None  # BYOK: OpenRouter API key (not stored in DB, used only for this interview)


class Question(BaseModel):
    """Question model."""
    question_id: str
    question: str
    skill: str
    difficulty: DifficultyLevel
    type: QuestionType
    context: Optional[Dict[str, Any]] = None


class Answer(BaseModel):
    """Answer model."""
    answer: str
    code: Optional[str] = None
    language: Optional[str] = None


class Evaluation(BaseModel):
    """Evaluation model."""
    score: float = Field(ge=0.0, le=1.0)
    feedback: str
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    next_difficulty: DifficultyLevel
    skill_assessment: Dict[str, float] = Field(default_factory=dict)


class InterviewState(BaseModel):
    """Interview state model."""
    interview_id: str
    user_id: str
    role: InterviewRole
    status: InterviewStatus
    current_phase: InterviewPhase = InterviewPhase.INTRODUCTION
    flow_state: InterviewFlowState = InterviewFlowState.USER_WAITING  # Real-time flow state
    resume_data: ResumeData
    skill_weights: List[SkillWeight] = Field(default_factory=list)
    use_llm_for_all_questions: bool = True  # Always use LLM (skip pool)
    answered_skills: Dict[str, List[Evaluation]] = Field(default_factory=dict)
    answered_projects: Dict[str, List[Evaluation]] = Field(default_factory=dict)  # project_name -> evaluations
    current_difficulty: DifficultyLevel = DifficultyLevel.BASIC
    current_skill: Optional[str] = None
    current_project: Optional[str] = None  # For project-phase questions
    current_question: Optional[Question] = None
    questions_asked: List[Question] = Field(default_factory=list)
    total_questions: int = 0
    max_questions: int = 15  # Increased for phased approach
    phase_questions: Dict[str, int] = Field(default_factory=dict)  # Track questions per phase
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    interview_duration_minutes: int = 30  # Time-based interview duration
    # Conversation context (sliding window for LLM)
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)  # Last N QA pairs
    max_context_pairs: int = 5  # Keep last 5 QA pairs for context
    report_id: Optional[str] = None  # Report ID after interview completion
    experience_level: Optional[str] = None  # User's experience level (entry, mid, senior, executive)


class SkillWeightResponse(BaseModel):
    """Skill weight response model (simplified for API)."""
    skill: str
    weight: float
    role_relevance: float


class StartInterviewResponse(BaseModel):
    """Start interview response."""
    interview_id: str
    first_question: Question
    estimated_duration: str
    skill_weights: List[SkillWeightResponse]


class AnswerResponse(BaseModel):
    """Answer response."""
    evaluation: Evaluation
    next_question: Optional[Question] = None
    progress: Dict[str, Any]
    completed: bool = False
    report_id: Optional[str] = None


# WebSocket Models
class WebSocketMessage(BaseModel):
    """WebSocket message model."""
    type: str
    data: Optional[Dict[str, Any]] = None


class AudioChunk(BaseModel):
    """Audio chunk model."""
    chunk: str  # Base64 encoded
    sample_rate: int = 16000
    channels: int = 1


class Transcript(BaseModel):
    """Transcript model."""
    text: str
    confidence: float
    is_final: bool

