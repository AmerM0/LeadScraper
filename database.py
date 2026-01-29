"""
Database layer for storing and retrieving leads
Uses SQLite with async support
"""

import aiosqlite
import json
from datetime import datetime
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class LeadDatabase:
    """Async SQLite database for leads"""
    
    def __init__(self, db_path: str = "./leads.db"):
        self.db_path = db_path
    
    async def initialize(self):
        """Create tables if they don't exist"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_name TEXT NOT NULL,
                    website TEXT NOT NULL UNIQUE,
                    emails TEXT,
                    phones TEXT,
                    source_page TEXT,
                    niche TEXT,
                    location TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS scrape_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    niche TEXT NOT NULL,
                    location TEXT NOT NULL,
                    leads_found INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.commit()
            logger.info("Database initialized")
    
    async def save_lead(self, lead: Dict, niche: str, location: str) -> int:
        """Save a single lead to database"""
        async with aiosqlite.connect(self.db_path) as db:
            # Convert lists to JSON strings
            emails_json = json.dumps(lead['emails'])
            phones_json = json.dumps(lead['phones'])
            
            try:
                cursor = await db.execute("""
                    INSERT INTO leads (business_name, website, emails, phones, source_page, niche, location)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    lead['business_name'],
                    lead['website'],
                    emails_json,
                    phones_json,
                    lead['source_page'],
                    niche,
                    location
                ))
                
                await db.commit()
                return cursor.lastrowid
                
            except aiosqlite.IntegrityError:
                # Lead already exists
                logger.debug(f"Lead already exists: {lead['website']}")
                return -1
    
    async def save_leads(self, leads: List[Dict], niche: str, location: str) -> int:
        """Save multiple leads and create session record"""
        saved_count = 0
        
        for lead in leads:
            result = await self.save_lead(lead, niche, location)
            if result > 0:
                saved_count += 1
        
        # Create session record
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO scrape_sessions (niche, location, leads_found)
                VALUES (?, ?, ?)
            """, (niche, location, saved_count))
            await db.commit()
        
        return saved_count
    
    async def get_leads(self, niche: Optional[str] = None, location: Optional[str] = None, 
                       limit: int = 100) -> List[Dict]:
        """Retrieve leads with optional filtering"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            query = "SELECT * FROM leads WHERE 1=1"
            params = []
            
            if niche:
                query += " AND niche = ?"
                params.append(niche)
            
            if location:
                query += " AND location = ?"
                params.append(location)
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                
                leads = []
                for row in rows:
                    lead = dict(row)
                    # Parse JSON fields
                    lead['emails'] = json.loads(lead['emails'])
                    lead['phones'] = json.loads(lead['phones'])
                    leads.append(lead)
                
                return leads
    
    async def get_sessions(self, limit: int = 10) -> List[Dict]:
        """Get recent scrape sessions"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            async with db.execute("""
                SELECT * FROM scrape_sessions 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def get_stats(self) -> Dict:
        """Get database statistics"""
        async with aiosqlite.connect(self.db_path) as db:
            # Total leads
            async with db.execute("SELECT COUNT(*) FROM leads") as cursor:
                total_leads = (await cursor.fetchone())[0]
            
            # Total sessions
            async with db.execute("SELECT COUNT(*) FROM scrape_sessions") as cursor:
                total_sessions = (await cursor.fetchone())[0]
            
            # Leads with emails
            async with db.execute("""
                SELECT COUNT(*) FROM leads 
                WHERE emails != '[]'
            """) as cursor:
                leads_with_emails = (await cursor.fetchone())[0]
            
            # Leads with phones
            async with db.execute("""
                SELECT COUNT(*) FROM leads 
                WHERE phones != '[]'
            """) as cursor:
                leads_with_phones = (await cursor.fetchone())[0]
            
            return {
                'total_leads': total_leads,
                'total_sessions': total_sessions,
                'leads_with_emails': leads_with_emails,
                'leads_with_phones': leads_with_phones
            }
