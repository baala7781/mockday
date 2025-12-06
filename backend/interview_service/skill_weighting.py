"""Skill weighting algorithm for interview questions."""
from typing import List, Dict, Optional
from interview_service.models import SkillWeight, ResumeData, InterviewRole
from interview_service.llm_skill_extractor import extract_role_skills_with_llm
import logging

logger = logging.getLogger(__name__)

# Fallback role-skill mapping (used if LLM extraction fails or for backward compatibility)
ROLE_SKILL_MAPPING = {
    "backend-developer": {
        "primary": {
            "Java": 0.9, "Python": 0.9, "Node.js": 0.8, "Spring": 0.85,
            "Django": 0.8, "Database": 0.9, "SQL": 0.85, "REST API": 0.9,
            "Microservices": 0.8, "Docker": 0.7, "Kubernetes": 0.7
        },
        "secondary": {
            "React": 0.2, "JavaScript": 0.5, "TypeScript": 0.4,
            "GraphQL": 0.6, "Redis": 0.7, "MongoDB": 0.6
        },
        "weight_ratio": 0.8  # 80% primary, 20% secondary
    },
    "frontend-developer": {
        "primary": {
            "React": 0.9, "JavaScript": 0.95, "TypeScript": 0.9,
            "CSS": 0.8, "HTML": 0.8, "Vue.js": 0.7, "Angular": 0.7
        },
        "secondary": {
            "Node.js": 0.5, "Python": 0.3, "GraphQL": 0.6,
            "REST API": 0.5, "Webpack": 0.6, "Jest": 0.6
        },
        "weight_ratio": 0.8
    },
    "fullstack-developer": {
        "primary": {
            "JavaScript": 0.9, "React": 0.85, "Node.js": 0.9,
            "Python": 0.8, "Database": 0.8, "REST API": 0.9
        },
        "secondary": {
            "Docker": 0.6, "AWS": 0.5, "GraphQL": 0.7,
            "TypeScript": 0.7, "MongoDB": 0.6, "Redis": 0.6
        },
        "weight_ratio": 0.7  # 70% primary, 30% secondary
    },
    "data-scientist": {
        "primary": {
            "Python": 0.95, "Machine Learning": 0.9, "SQL": 0.85,
            "Data Analysis": 0.9, "Pandas": 0.8, "NumPy": 0.8,
            "Scikit-learn": 0.8, "TensorFlow": 0.7, "PyTorch": 0.7
        },
        "secondary": {
            "Java": 0.3, "Cloud": 0.5, "Statistics": 0.7,
            "R": 0.6, "Spark": 0.6, "Hadoop": 0.5
        },
        "weight_ratio": 0.85
    },
    "software-engineer": {
        "primary": {
            "Java": 0.8, "Python": 0.8, "JavaScript": 0.8,
            "Database": 0.7, "REST API": 0.8, "System Design": 0.8
        },
        "secondary": {
            "Docker": 0.6, "Cloud": 0.5, "Testing": 0.7,
            "CI/CD": 0.6, "Git": 0.7
        },
        "weight_ratio": 0.75
    },
    "product-manager": {
        "primary": {
            "Product Management": 0.9, "Agile": 0.8, "Scrum": 0.8,
            "User Research": 0.8, "Analytics": 0.7, "Strategy": 0.8
        },
        "secondary": {
            "SQL": 0.5, "Python": 0.3, "JavaScript": 0.3,
            "A/B Testing": 0.6, "Data Analysis": 0.6
        },
        "weight_ratio": 0.8
    }
}


async def calculate_skill_weights(
    role: InterviewRole,
    resume_data: ResumeData,
    max_years: float = 5.0,
    max_projects: int = 5,
    use_llm_extraction: bool = True
) -> List[SkillWeight]:
    """
    Calculate skill weights based on role and resume.
    
    Formula:
    skill_weight = (role_relevance × 0.5) + (resume_experience × 0.3) + (project_count × 0.2)
    
    Args:
        role: Interview role
        resume_data: Parsed resume data
        max_years: Maximum years for normalization
        max_projects: Maximum projects for normalization
        use_llm_extraction: Whether to use LLM for dynamic skill extraction
        
    Returns:
        List of skill weights sorted by weight (descending)
    """
    # Try LLM extraction first (if enabled)
    role_mapping = None
    if use_llm_extraction:
        try:
            role_mapping = await extract_role_skills_with_llm(role, resume_data, use_cache=True)
            logger.info(f"Using LLM-extracted skills for role: {role.value}")
        except Exception as e:
            logger.warning(f"LLM skill extraction failed, using fallback: {e}")
    
    # Fallback to hardcoded mapping if LLM fails or disabled
    if not role_mapping:
        role_mapping = ROLE_SKILL_MAPPING.get(role.value, {})
        logger.debug(f"Using hardcoded skill mapping for role: {role.value}")
    
    primary_skills = role_mapping.get("primary", {})
    secondary_skills = role_mapping.get("secondary", {})
    weight_ratio = role_mapping.get("weight_ratio", 0.8)
    
    # Create skill dictionary from resume
    resume_skills = {}
    for skill in (resume_data.skills or []):
        resume_skills[skill.name] = {
            "years": skill.years or 0,
            "projects": len(skill.projects) if skill.projects else 0
        }
    
    # Also extract skills from projects and experience
    for project in (resume_data.projects or []):
        for tech in (project.technologies or []):
            if tech not in resume_skills:
                resume_skills[tech] = {"years": 0, "projects": 0}
            resume_skills[tech]["projects"] += 1
    
    for exp in (resume_data.experience or []):
        for skill in (exp.skills_used or []):
            if skill not in resume_skills:
                resume_skills[skill] = {"years": 0, "projects": 0}
            # Add experience years (approximate)
            resume_skills[skill]["years"] += 1
    
    skill_weights = []
    
    # If no resume skills, use role-based skills only
    if not resume_skills:
        # Use primary and secondary skills from role mapping
        for skill_name, relevance in primary_skills.items():
            skill_weights.append(SkillWeight(
                skill=skill_name,
                weight=relevance,
                role_relevance=relevance,
                resume_experience=0.0,
                project_count=0.0
            ))
        for skill_name, relevance in secondary_skills.items():
            skill_weights.append(SkillWeight(
                skill=skill_name,
                weight=relevance * 0.5,  # Lower weight for secondary skills
                role_relevance=relevance,
                resume_experience=0.0,
                project_count=0.0
            ))
    else:
        # Calculate weights for all skills in resume
        for skill_name, skill_data in resume_skills.items():
            # Get role relevance
            role_relevance = 0.0
            if skill_name in primary_skills:
                role_relevance = primary_skills[skill_name]
            elif skill_name in secondary_skills:
                role_relevance = secondary_skills[skill_name]
            else:
                # Skill not in role mapping, give low relevance
                role_relevance = 0.1
            
            # Normalize resume experience
            resume_experience = min(skill_data["years"] / max_years, 1.0)
            
            # Normalize project count
            project_count = min(skill_data["projects"] / max_projects, 1.0)
            
            # Calculate weight
            weight = (
                role_relevance * 0.5 +
                resume_experience * 0.3 +
                project_count * 0.2
            )
            
            skill_weights.append(SkillWeight(
                skill=skill_name,
                weight=weight,
                role_relevance=role_relevance,
                resume_experience=resume_experience,
                project_count=project_count
            ))
    
    # Sort by weight (descending)
    skill_weights.sort(key=lambda x: x.weight, reverse=True)
    
    return skill_weights


def distribute_questions(
    skill_weights: List[SkillWeight],
    total_questions: int = 10
) -> Dict[str, int]:
    """
    Distribute questions across skills based on weights.
    
    Args:
        skill_weights: List of skill weights
        total_questions: Total number of questions
        
    Returns:
        Dictionary mapping skill to number of questions
    """
    if not skill_weights:
        return {}
    
    # Calculate total weight
    total_weight = sum(sw.weight for sw in skill_weights)
    
    if total_weight == 0:
        # Equal distribution
        questions_per_skill = total_questions // len(skill_weights)
        return {sw.skill: questions_per_skill for sw in skill_weights}
    
    # Distribute questions proportionally
    question_distribution = {}
    remaining_questions = total_questions
    
    # Allocate questions based on weights
    for i, skill_weight in enumerate(skill_weights):
        if i == len(skill_weights) - 1:
            # Last skill gets remaining questions
            question_distribution[skill_weight.skill] = remaining_questions
        else:
            # Calculate questions for this skill
            questions = int((skill_weight.weight / total_weight) * total_questions)
            questions = max(1, questions)  # At least 1 question per skill
            question_distribution[skill_weight.skill] = questions
            remaining_questions -= questions
    
    return question_distribution

