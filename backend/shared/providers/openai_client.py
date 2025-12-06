"""OpenAI client for LLM interactions."""
from openai import AsyncOpenAI
from shared.providers.pool_manager import provider_pool_manager, ProviderType
from typing import Optional, AsyncGenerator
import json


class OpenAIClientWrapper:
    """OpenAI client wrapper with pool management."""
    
    async def generate_response(
        self,
        prompt: str,
        model: str = "gpt-4",
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Optional[str]:
        """
        Generate response using OpenAI.
        
        Args:
            prompt: Input prompt
            model: Model to use
            stream: Whether to stream response
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text or None on error
        """
        account = await provider_pool_manager.get_account(ProviderType.OPENAI)
        if not account:
            return None
        
        try:
            client = AsyncOpenAI(api_key=account.api_key)
            
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
            )
            
            if stream:
                # Handle streaming (return generator)
                async def stream_generator():
                    async for chunk in response:
                        if chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content
                    await provider_pool_manager.mark_success(account)
                
                return stream_generator()
            else:
                text = response.choices[0].message.content
                await provider_pool_manager.mark_success(account)
                return text
                
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "rate limit" in error_msg.lower():
                await provider_pool_manager.mark_error(account, error_msg, 60)
            else:
                await provider_pool_manager.mark_error(account, error_msg)
            return None
    
    async def generate_question(
        self,
        context: str,
        role: str,
        previous_questions: list,
        user_resume: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate interview question based on context.
        
        Args:
            context: Interview context
            role: Role being interviewed for
            previous_questions: List of previous questions
            user_resume: User's resume text
            
        Returns:
            Generated question or None on error
        """
        prompt = f"""You are an AI interviewer conducting a {role} interview.

Context: {context}

Previous questions asked:
{chr(10).join(f"- {q}" for q in previous_questions)}

User's background:
{user_resume[:500] if user_resume else "Not provided"}

Generate the next interview question. Keep it concise, relevant, and professional.
Question:"""
        
        return await self.generate_response(prompt, model="gpt-4", max_tokens=200)
    
    async def evaluate_answer(
        self,
        question: str,
        answer: str,
        role: str
    ) -> Optional[dict]:
        """
        Evaluate user's answer to a question.
        
        Args:
            question: Interview question
            answer: User's answer
            role: Role being interviewed for
            
        Returns:
            Evaluation dict with score, feedback, etc.
        """
        prompt = f"""Evaluate the following interview answer for a {role} position.

Question: {question}

Answer: {answer}

Provide a JSON response with:
- score: integer (0-100)
- feedback: string (constructive feedback)
- strengths: list of strings
- areas_for_improvement: list of strings

Response (JSON only):"""
        
        response = await self.generate_response(prompt, model="gpt-4", max_tokens=500)
        if response:
            try:
                # Extract JSON from response
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    return json.loads(response[json_start:json_end])
            except json.JSONDecodeError:
                pass
        
        return None


# Global OpenAI client instance
openai_client = OpenAIClientWrapper()

