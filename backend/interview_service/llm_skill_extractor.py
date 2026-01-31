"""LLM-based skill extraction for dynamic role-skill mapping."""
from typing import Dict, List, Optional
from interview_service.models import InterviewRole, ResumeData
from interview_service.llm_helpers import generate_with_task_and_byok
from shared.db.redis_client import redis_client
import json
import logging

logger = logging.getLogger(__name__)


async def extract_role_skills_with_llm(
    role: InterviewRole,
    resume_data: Optional[ResumeData] = None,
    use_cache: bool = True
) -> Dict[str, any]:
    """
    Use LLM to dynamically extract required skills for a role.
    
    Args:
        role: Interview role
        resume_data: Optional resume data for context
        use_cache: Whether to use cached results
        
    Returns:
        Dict with 'primary', 'secondary', and 'weight_ratio' keys
    """
    # Check cache first
    if use_cache:
        cache_key = f"role_skills:{role.value}"
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                logger.info(f"Using cached skill mapping for role: {role.value}")
                return cached
        except Exception as e:
            logger.debug(f"Cache read failed (non-critical): {e}")
    
    # Build resume context (very short)
    resume_context = ""
    if resume_data:
        top_skills = [s.name for s in (resume_data.skills or [])[:5]]
        top_projects = [p.name for p in (resume_data.projects or [])[:3]]
        if top_skills:
            resume_context += f"Candidate has experience with: {', '.join(top_skills)}. "
        if top_projects:
            resume_context += f"Projects: {', '.join(top_projects)}."
    
    # Generate prompt
    prompt = f"""You are an expert technical recruiter analyzing the role: {role.value.replace('-', ' ')}.

Analyze this role and determine the required technical skills.

{resume_context if resume_context else "No candidate resume provided."}

Provide a JSON response with:
{{
    "primary": {{
        "skill_name": relevance_score_0.0_to_1.0,
        ...
    }},
    "secondary": {{
        "skill_name": relevance_score_0.0_to_1.0,
        ...
    }},
    "weight_ratio": 0.7_to_0.85
}}

Guidelines:
- Primary skills: Core, essential skills for this role (relevance 0.7-0.95)
- Secondary skills: Supporting, nice-to-have skills (relevance 0.2-0.7)
- Include 8-12 primary skills, 5-8 secondary skills
- Focus on technical skills, frameworks, tools, languages
- weight_ratio: Proportion of primary vs secondary (typically 0.7-0.85)

Return ONLY valid JSON, no additional text:"""

    try:
        # Use OpenRouter with gpt-4o-mini for skill extraction
        response = await generate_with_task_and_byok(
            task="resume_parsing",  # Similar to resume parsing
            prompt=prompt,
            max_tokens=2000,
            temperature=0.1,
            interview_id=None  # Skill extraction doesn't have interview context
        )
        
        if response:
            # Extract JSON
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                data = json.loads(response[json_start:json_end])
                
                result = {
                    "primary": data.get("primary", {}),
                    "secondary": data.get("secondary", {}),
                    "weight_ratio": float(data.get("weight_ratio", 0.8))
                }
                
                # Cache result
                if use_cache:
                    try:
                        await redis_client.set(cache_key, result, expire=86400)  # 24 hours
                    except Exception as e:
                        logger.debug(f"Cache write failed (non-critical): {e}")
                
                logger.info(f"Extracted {len(result['primary'])} primary and {len(result['secondary'])} secondary skills for role: {role.value}")
                return result
    except Exception as e:
        logger.error(f"Error extracting role skills with LLM: {e}", exc_info=True)
    
    # Fallback to empty mapping (will use resume-only skills)
    logger.warning(f"LLM skill extraction failed, using empty mapping for role: {role.value}")
    return {
        "primary": {},
        "secondary": {},
        "weight_ratio": 0.8
    }

