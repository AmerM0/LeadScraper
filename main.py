"""
FastAPI Backend for Lead Generation Tool
Production-ready with proper error handling and async support
"""

import os
from contextlib import asynccontextmanager
from typing import List, Optional
import logging

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from scraper import LeadScraper
from database import LeadDatabase
from outreach import OutreachGenerator

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize database
db = LeadDatabase(db_path=os.getenv('DATABASE_PATH', './leads.db'))

# Initialize AI outreach generator
outreach_gen = OutreachGenerator()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("🚀 Starting Lead Generation API")
    await db.initialize()
    logger.info("✓ Database initialized")
    
    if outreach_gen.is_available():
        logger.info("✓ AI outreach generator available")
    else:
        logger.info("⚠ AI outreach generator not configured (missing OPENAI_API_KEY)")
    
    yield
    
    # Shutdown
    logger.info("👋 Shutting down")


# Create FastAPI app
app = FastAPI(
    title="Lead Generation API",
    description="Production-ready lead scraping tool with Playwright",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========================================
# REQUEST/RESPONSE MODELS
# ========================================

class ScrapeRequest(BaseModel):
    niche: str = Field(..., min_length=2, max_length=100, 
                      description="Business niche (e.g., 'plumbers', 'coffee shops')")
    location: str = Field(..., min_length=2, max_length=100,
                         description="Location (e.g., 'Munich', 'Berlin')")
    max_results: int = Field(20, ge=5, le=50,
                            description="Maximum number of results to scrape")


class Lead(BaseModel):
    business_name: str
    website: str
    emails: List[str]
    phones: List[str]
    source_page: str


class ScrapeResponse(BaseModel):
    success: bool
    message: str
    leads_found: int
    leads: List[Lead]


class OutreachRequest(BaseModel):
    website: str = Field(..., description="Website URL of the lead")
    user_context: str = Field("", max_length=500,
                             description="Your business/service description for personalization")


class OutreachResponse(BaseModel):
    success: bool
    website: str
    email_message: Optional[str] = None
    template_message: Optional[str] = None


class StatsResponse(BaseModel):
    total_leads: int
    total_sessions: int
    leads_with_emails: int
    leads_with_phones: int


# ========================================
# API ENDPOINTS
# ========================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the frontend HTML page"""
    try:
        return FileResponse("static/index.html")
    except FileNotFoundError:
        return HTMLResponse(content="""
        <html>
            <body>
                <h1>Lead Generation API</h1>
                <p>API is running. Frontend not found.</p>
                <p>Visit <a href="/docs">/docs</a> for API documentation.</p>
            </body>
        </html>
        """)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    stats = await db.get_stats()
    return {
        "status": "healthy",
        "database": "connected",
        "ai_available": outreach_gen.is_available(),
        "stats": stats
    }


@app.post("/api/scrape", response_model=ScrapeResponse)
async def scrape_leads(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """
    Scrape leads for a given niche and location
    
    This endpoint initiates the scraping process:
    1. Discovers business websites
    2. Filters out directories
    3. Extracts lead data using Playwright
    4. Stores results in database
    """
    try:
        logger.info(f"Scrape request: {request.niche} in {request.location}")
        
        # Create scraper with config
        max_results = min(request.max_results, int(os.getenv('MAX_RESULTS', 20)))
        timeout = int(os.getenv('TIMEOUT_SECONDS', 15))
        headless = os.getenv('HEADLESS', 'true').lower() == 'true'
        
        async with LeadScraper(max_results=max_results, timeout=timeout, headless=headless) as scraper:
            # Run scraping pipeline
            leads = await scraper.scrape(request.niche, request.location)
            
            if not leads:
                return ScrapeResponse(
                    success=True,
                    message="No leads found. Try different search terms.",
                    leads_found=0,
                    leads=[]
                )
            
            # Save to database in background
            background_tasks.add_task(db.save_leads, leads, request.niche, request.location)
            
            return ScrapeResponse(
                success=True,
                message=f"Successfully scraped {len(leads)} leads",
                leads_found=len(leads),
                leads=[Lead(**lead) for lead in leads]
            )
            
    except Exception as e:
        logger.error(f"Scrape error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")


@app.get("/api/leads")
async def get_leads(
    niche: Optional[str] = None,
    location: Optional[str] = None,
    limit: int = 100
):
    """
    Retrieve stored leads from database
    
    Query parameters:
    - niche: Filter by business niche
    - location: Filter by location
    - limit: Maximum number of results (default 100)
    """
    try:
        leads = await db.get_leads(niche=niche, location=location, limit=limit)
        
        return {
            "success": True,
            "count": len(leads),
            "leads": leads
        }
        
    except Exception as e:
        logger.error(f"Get leads error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions")
async def get_sessions(limit: int = 10):
    """Get recent scraping sessions"""
    try:
        sessions = await db.get_sessions(limit=limit)
        
        return {
            "success": True,
            "count": len(sessions),
            "sessions": sessions
        }
        
    except Exception as e:
        logger.error(f"Get sessions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats():
    """Get database statistics"""
    try:
        stats = await db.get_stats()
        return StatsResponse(**stats)
        
    except Exception as e:
        logger.error(f"Get stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/outreach", response_model=OutreachResponse)
async def generate_outreach(request: OutreachRequest):
    """
    Generate personalized outreach message for a lead
    
    Requires OPENAI_API_KEY to be set for AI generation.
    Falls back to template if AI is not available.
    """
    try:
        # Find lead in database
        leads = await db.get_leads(limit=1000)
        lead = next((l for l in leads if l['website'] == request.website), None)
        
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # Try AI generation
        ai_message = None
        if outreach_gen.is_available():
            ai_message = await outreach_gen.generate_email(lead, request.user_context)
        
        # Always provide template fallback
        template_message = outreach_gen.generate_template(lead)
        
        return OutreachResponse(
            success=True,
            website=request.website,
            email_message=ai_message,
            template_message=template_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Outreach generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/leads/{lead_id}")
async def delete_lead(lead_id: int):
    """Delete a specific lead"""
    # Note: This would require adding delete method to database.py
    raise HTTPException(status_code=501, detail="Not implemented yet")


# Serve static files (frontend)
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception as e:
    logger.warning(f"Static files directory not found: {e}")


# ========================================
# MAIN
# ========================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv('PORT', 8000))
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
