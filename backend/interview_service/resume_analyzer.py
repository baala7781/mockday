"""Resume analysis and parsing with caching."""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
from typing import Any, Dict, Optional

import requests
from docx import Document
from PyPDF2 import PdfReader

from interview_service.models import Experience, Project, ResumeData, Skill
from shared.db.redis_client import redis_client
from shared.providers.gemini_client import gemini_client
from shared.storage.firebase_storage import download_blob_as_bytes

logger = logging.getLogger(__name__)


async def analyze_resume_with_llm(resume_text: str) -> ResumeData:
    """
    Analyze resume text using LLM to extract structured data.
    
    Args:
        resume_text: Raw resume text
        
    Returns:
        Structured resume data
    """
    prompt = f"""You are an expert resume parser. Analyze the following resume and extract ONLY the skills, technologies, and programming languages that are explicitly mentioned or clearly demonstrated.

IMPORTANT INSTRUCTIONS:
1. Extract ONLY technical skills, programming languages, frameworks, tools, and technologies
2. DO NOT include generic skills like "communication", "teamwork", "leadership" unless they are technical leadership skills
3. DO NOT include soft skills or personality traits
4. Focus on technical skills relevant to software engineering roles
5. Extract years of experience only if explicitly stated
6. For projects, extract ONLY the technologies actually used in the project
7. For experience, extract ONLY the technical skills used in that role

Resume Text:
{resume_text}

Extract the following information and provide a JSON response:
{{
    "skills": [
        {{"name": "skill_name", "years": years_of_experience_if_stated_otherwise_0, "projects": ["project_names_where_used"]}}
    ],
    "projects": [
        {{
            "name": "project_name",
            "description": "brief_project_description",
            "technologies": ["only_actual_technologies_used"],
            "duration": "duration_if_mentioned"
        }}
    ],
    "experience": [
        {{
            "role": "job_title",
            "company": "company_name",
            "duration": "duration",
            "skills_used": ["only_technical_skills_used_in_this_role"]
        }}
    ],
    "education": [
        {{
            "degree": "degree",
            "institution": "institution",
            "year": "year"
        }}
    ]
}}

CRITICAL: Only include skills that are:
- Programming languages (Python, Java, JavaScript, etc.)
- Frameworks (React, Django, Spring, etc.)
- Tools (Docker, Kubernetes, AWS, etc.)
- Databases (PostgreSQL, MongoDB, etc.)
- Technical concepts (REST API, Microservices, etc.)

DO NOT include:
- Soft skills (communication, teamwork, etc.)
- Generic terms (problem-solving, analytical thinking, etc.)
- Skills not mentioned in the resume

Return only valid JSON, no additional text:"""

    try:
        logger.info(f"📄 [Resume Parser] Analyzing resume with LLM (text length: {len(resume_text)} chars)")
        
        # Check Gemini API keys before attempting
        from shared.providers.pool_manager import provider_pool_manager, ProviderType
        pool_stats = await provider_pool_manager.get_pool_stats(ProviderType.GEMINI)
        logger.info(f"📄 [Resume Parser] Gemini pool stats: {pool_stats}")
        
        if pool_stats["total_accounts"] == 0:
            logger.error("❌ [Resume Parser] No Gemini API keys configured! Check GEMINI_API_KEYS environment variable.")
            return ResumeData()
        
        # Retry logic for resume parsing
        max_retries = 2
        response = None
        for attempt in range(max_retries):
            try:
                logger.info(f"📄 [Resume Parser] Attempt {attempt + 1}/{max_retries}: Calling Gemini API...")
                response = await gemini_client.generate_response(
                    prompt=prompt,
                    model="gemini-2.0-flash",
                    max_tokens=4000,  # Increase for longer resumes
                    temperature=0.3
                )
                
                if response:
                    logger.info(f"✅ [Resume Parser] Got response from LLM (length: {len(response)} chars)")
                    break
                else:
                    logger.warning(f"⚠️ [Resume Parser] Attempt {attempt + 1}: LLM returned empty response")
                    if attempt < max_retries - 1:
                        import asyncio
                        await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"❌ [Resume Parser] Attempt {attempt + 1} failed: {e}", exc_info=True)
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(1)
                else:
                    raise
        
        if not response:
            logger.error("❌ [Resume Parser] LLM returned empty response after all retries")
            return ResumeData()
        
        logger.debug(f"📄 [Resume Parser] LLM response (first 500 chars): {response[:500]}")
        
        # Extract JSON from response
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start < 0 or json_end <= json_start:
            logger.error(f"❌ [Resume Parser] Could not find JSON in LLM response. Response length: {len(response)}")
            logger.error(f"❌ [Resume Parser] Response preview: {response[:1000]}")
            return ResumeData()
        
        try:
            json_str = response[json_start:json_end]
            logger.debug(f"📄 [Resume Parser] Extracted JSON (length: {len(json_str)} chars)")
            data = json.loads(json_str)
            skills_count = len(data.get('skills', []))
            projects_count = len(data.get('projects', []))
            exp_count = len(data.get('experience', []))
            logger.info(f"✅ [Resume Parser] Parsed resume data: {skills_count} skills, {projects_count} projects, {exp_count} experiences")
            
            if skills_count == 0 and projects_count == 0:
                logger.warning("⚠️ [Resume Parser] No skills or projects extracted from resume. This might indicate a parsing issue.")
        except json.JSONDecodeError as e:
            logger.error(f"❌ [Resume Parser] Failed to parse JSON from LLM response: {e}")
            logger.error(f"❌ [Resume Parser] JSON string (first 1000 chars): {json_str[:1000] if 'json_str' in locals() else 'N/A'}")
            return ResumeData()
        
        # Convert to ResumeData model with error handling
        skills = []
        for skill in data.get("skills", []):
            try:
                skills.append(Skill(**skill))
            except Exception as e:
                logger.warning(f"Failed to parse skill {skill}: {e}")
        
        projects = []
        for project in data.get("projects", []):
            try:
                projects.append(Project(**project))
            except Exception as e:
                logger.warning(f"Failed to parse project {project}: {e}")
        
        experiences = []
        for exp in data.get("experience", []):
            try:
                experiences.append(Experience(**exp))
            except Exception as e:
                logger.warning(f"Failed to parse experience {exp}: {e}")
        
        result = ResumeData(
            skills=skills,
            projects=projects,
            experience=experiences,
            education=data.get("education", [])
        )
        
        logger.info(f"Successfully parsed resume: {len(skills)} skills, {len(projects)} projects, {len(experiences)} experiences")
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing resume with LLM: {e}", exc_info=True)
    
    # Fallback: Return empty resume data
    logger.warning("Returning empty ResumeData due to parsing failure")
    return ResumeData()


def parse_resume_from_profile(profile_data: Dict[str, Any]) -> ResumeData:
    """
    Parse resume data from user profile.
    
    Args:
        profile_data: User profile data from database
        
    Returns:
        Structured resume data
    """
    skills = []
    if "skills" in profile_data:
        for skill_name in profile_data["skills"]:
            skills.append(Skill(name=skill_name, years=0, projects=[]))
    
    projects = []
    # Extract projects from experiences or separate projects field
    if "experiences" in profile_data:
        for exp in profile_data["experiences"]:
            if "projects" in exp:
                for proj in exp["projects"]:
                    projects.append(Project(
                        name=proj.get("name", ""),
                        description=proj.get("description", ""),
                        technologies=proj.get("technologies", []),
                        duration=proj.get("duration", "")
                    ))
    
    experiences = []
    if "experiences" in profile_data:
        for exp in profile_data["experiences"]:
            experiences.append(Experience(
                role=exp.get("role", ""),
                company=exp.get("company", ""),
                duration=exp.get("period", ""),
                skills_used=exp.get("skills", [])
            ))
    
    return ResumeData(
        skills=skills,
        projects=projects,
        experience=experiences,
        education=profile_data.get("educations", [])
    )


async def get_resume_data(
    resume_id: Optional[str] = None,
    resume_text: Optional[str] = None,
    profile_data: Optional[Dict[str, Any]] = None
) -> ResumeData:
    """
    Get resume data from various sources with caching.
    
    Args:
        resume_id: Resume ID (to fetch from storage)
        resume_text: Raw resume text
        profile_data: User profile data
        
    Returns:
        Structured resume data
    """
    # Priority: resume_text > resume_id (storage) > profile_data
    extracted_text: Optional[str] = None
    
    if resume_text:
        extracted_text = resume_text
    elif resume_id:
        resume_meta = _find_resume_metadata(resume_id, profile_data)
        if resume_meta:
            extracted_text = await _extract_text_from_resume(resume_meta)
        else:
            logger.warning(f"Resume metadata not found for resume_id: {resume_id}")
    
    if extracted_text:
        return await _analyze_and_cache_resume_text(extracted_text)
    
    if profile_data:
        return parse_resume_from_profile(profile_data)
    
    return ResumeData()


async def _analyze_and_cache_resume_text(resume_text: str) -> ResumeData:
    """Analyze resume text with caching."""
    resume_hash = hashlib.md5(resume_text.encode()).hexdigest()
    cache_key = f"resume_analysis:{resume_hash}"
    
    cached_analysis = await redis_client.get(cache_key)
    if cached_analysis:
        try:
            return ResumeData(**cached_analysis)
        except Exception as e:
            logger.debug(f"Error parsing cached resume analysis: {e}")
    
    resume_data = await analyze_resume_with_llm(resume_text)
    
    try:
        await redis_client.set(
            cache_key,
            resume_data.model_dump(mode='json'),
            expire=86400 * 30
        )
    except Exception as e:
        logger.debug(f"Error caching resume analysis: {e}")
    
    return resume_data


def _find_resume_metadata(
    resume_id: str,
    profile_data: Optional[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Find resume metadata by ID from profile data."""
    if not profile_data:
        return None
    
    resumes = profile_data.get("resumes", [])
    for resume in resumes:
        if str(resume.get("id")) == str(resume_id):
            return resume
    return None


async def _extract_text_from_resume(resume_meta: Dict[str, Any]) -> Optional[str]:
    """
    Extract text from resume metadata.
    First tries to use stored extractedText, then falls back to downloading file if available.
    """
    # If we have stored extracted text, use it (no file download needed)
    if resume_meta.get("extractedText"):
        logger.debug(f"Using stored extracted text for resume {resume_meta.get('id')}")
        return resume_meta["extractedText"]
    
    # Fallback: try to download from storage if storagePath exists (for backward compatibility)
    file_bytes = await _download_resume_bytes(resume_meta)
    if not file_bytes:
        return None
    
    extension = _infer_extension(resume_meta)
    
    try:
        if extension == "pdf":
            return await asyncio.to_thread(_extract_pdf_text, file_bytes)
        if extension in {"docx", "doc"}:
            return await asyncio.to_thread(_extract_docx_text, file_bytes)
        # Default to UTF-8 text
        return file_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        logger.error(f"Error extracting text from resume: {e}", exc_info=True)
        return None


async def _download_resume_bytes(resume_meta: Dict[str, Any]) -> Optional[bytes]:
    """Download resume bytes from Firebase Storage or direct URL."""
    storage_path = resume_meta.get("storagePath") or resume_meta.get("path")
    if storage_path:
        try:
            return await asyncio.to_thread(download_blob_as_bytes, storage_path)
        except Exception as e:
            logger.error(f"Failed to download resume from storage path '{storage_path}': {e}")
    
    download_url = resume_meta.get("url")
    if download_url:
        try:
            return await asyncio.to_thread(_download_bytes_via_http, download_url)
        except Exception as e:
            logger.error(f"Failed to download resume via URL '{download_url}': {e}")
    
    logger.warning("Resume metadata missing storagePath or url.")
    return None


def _download_bytes_via_http(url: str) -> bytes:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.content


def _infer_extension(resume_meta: Dict[str, Any]) -> str:
    """Infer file extension from metadata."""
    name = (resume_meta.get("name") or "").lower()
    if "." in name:
        return name.rsplit(".", 1)[1]
    
    storage_path = (resume_meta.get("storagePath") or "").lower()
    if "." in storage_path:
        return storage_path.rsplit(".", 1)[1]
    
    url = (resume_meta.get("url") or "").lower()
    if "." in url.split("?")[0]:
        return url.split("?")[0].rsplit(".", 1)[1]
    
    return "pdf"  # Default assumption


def _extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    text_chunks = []
    for page in reader.pages:
        text_chunks.append(page.extract_text() or "")
    return "\n".join(text_chunks).strip()


def _extract_docx_text(file_bytes: bytes) -> str:
    document = Document(io.BytesIO(file_bytes))
    paragraphs = [p.text for p in document.paragraphs if p.text]
    return "\n".join(paragraphs).strip()


async def _extract_text_from_uploaded_file(file_bytes: bytes, file_ext: str) -> str:
    """
    Extract text from uploaded file bytes.
    
    Args:
        file_bytes: File contents as bytes
        file_ext: File extension (e.g., ".pdf", ".docx")
        
    Returns:
        Extracted text
    """
    try:
        if file_ext == ".pdf":
            return await asyncio.to_thread(_extract_pdf_text, file_bytes)
        if file_ext in {".docx", ".doc"}:
            return await asyncio.to_thread(_extract_docx_text, file_bytes)
        # Default to UTF-8 text
        return file_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        logger.error(f"Error extracting text from uploaded file: {e}", exc_info=True)
        raise
