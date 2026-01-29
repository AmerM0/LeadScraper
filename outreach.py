"""
AI-powered outreach message generator
Uses OpenAI API to create personalized cold emails
"""

import os
from typing import Dict, Optional
import logging
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class OutreachGenerator:
    """Generate personalized outreach messages using AI"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None
    
    def is_available(self) -> bool:
        """Check if AI generation is available"""
        return self.client is not None
    
    async def generate_email(self, lead: Dict, user_context: str = "") -> Optional[str]:
        """
        Generate a personalized cold email for a lead
        
        Args:
            lead: Lead dictionary with business info
            user_context: User's business/service description
        
        Returns:
            Generated email text or None if generation fails
        """
        if not self.is_available():
            logger.warning("OpenAI API key not configured")
            return None
        
        try:
            prompt = self._build_prompt(lead, user_context)
            
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at writing concise, personalized cold emails for B2B outreach. Keep emails under 150 words, focus on value, and include a clear call-to-action."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=300
            )
            
            email = response.choices[0].message.content.strip()
            return email
            
        except Exception as e:
            logger.error(f"Email generation error: {e}")
            return None
    
    def _build_prompt(self, lead: Dict, user_context: str) -> str:
        """Build the prompt for email generation"""
        business_name = lead.get('business_name', 'there')
        website = lead.get('website', '')
        
        prompt = f"""Write a personalized cold email to {business_name} ({website}).

My business context: {user_context if user_context else "I provide marketing services to help businesses grow."}

Requirements:
- Professional but friendly tone
- Mention their business specifically
- Highlight 1-2 key benefits
- Include clear call-to-action
- Keep under 150 words
- Do not include subject line
- Start with a personalized greeting

Write only the email body, nothing else."""
        
        return prompt
    
    async def generate_batch(self, leads: list[Dict], user_context: str = "", 
                           max_count: int = 10) -> Dict[str, str]:
        """
        Generate emails for multiple leads
        
        Returns:
            Dictionary mapping website URL to generated email
        """
        if not self.is_available():
            return {}
        
        results = {}
        
        for lead in leads[:max_count]:
            email = await self.generate_email(lead, user_context)
            if email:
                results[lead['website']] = email
        
        return results
    
    def generate_template(self, lead: Dict) -> str:
        """Generate a simple template email (no AI required)"""
        business_name = lead.get('business_name', 'there')
        
        template = f"""Hi {business_name} team,

I came across your website and was impressed by your business.

I specialize in [YOUR SERVICE] and help businesses like yours [KEY BENEFIT].

Would you be open to a quick 15-minute call this week to discuss how we could help you [SPECIFIC OUTCOME]?

Best regards,
[YOUR NAME]
[YOUR CONTACT]"""
        
        return template
