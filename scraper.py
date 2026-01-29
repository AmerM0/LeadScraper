"""
Lead Scraper using Playwright for browser-level extraction
Implements a 4-stage pipeline: Discovery → Filtering → Extraction → Output
"""

import re
import asyncio
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
import logging

from playwright.async_api import async_playwright, Page, Browser
from bs4 import BeautifulSoup
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LeadScraper:
    """Production-grade lead scraper using Playwright"""
    
    # Known directory domains to exclude
    DIRECTORY_DOMAINS = {
        'yelp.com', 'yellowpages.com', 'tripadvisor.com', 'clutch.co',
        'trustpilot.com', 'bbb.org', 'manta.com', 'facebook.com',
        'linkedin.com', 'instagram.com', 'twitter.com', 'bing.com',
        'google.com', 'duckduckgo.com', 'wikipedia.org', 'youtube.com'
    }
    
    # Keywords that indicate list/directory pages
    DIRECTORY_KEYWORDS = [
        'best', 'top', 'list', 'directory', 'ranking', 'review',
        'find', 'search', 'compare', 'guide', 'rating'
    ]
    
    def __init__(self, max_results: int = 20, timeout: int = 15, headless: bool = True):
        self.max_results = max_results
        self.timeout = timeout * 1000  # Convert to milliseconds
        self.headless = headless
        self.browser: Optional[Browser] = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.browser:
            await self.browser.close()
        await self.playwright.stop()
    
    # ========================================
    # STAGE 1: DISCOVERY
    # ========================================
    
    async def discover_businesses(self, niche: str, location: str) -> List[str]:
        """
        Stage 1: Discover business websites using DuckDuckGo
        Returns list of candidate URLs
        """
        query = f"{niche} in {location}"
        logger.info(f"🔍 Discovery Stage: Searching for '{query}'")
        
        urls = await self._search_duckduckgo(query)
        logger.info(f"✓ Found {len(urls)} candidate URLs")
        return urls
    
    async def _search_duckduckgo(self, query: str) -> List[str]:
        """Use DuckDuckGo HTML search to find business websites"""
        search_url = f"https://html.duckduckgo.com/html/?q={query}"
        urls = []
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                response = await client.get(search_url, headers=headers, follow_redirects=True)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'lxml')
                    
                    # Extract result links
                    for link in soup.select('a.result__a'):
                        href = link.get('href')
                        if href:
                            # DuckDuckGo uses redirect URLs
                            if 'uddg=' in href:
                                # Extract actual URL from redirect
                                try:
                                    actual_url = href.split('uddg=')[1].split('&')[0]
                                    from urllib.parse import unquote
                                    actual_url = unquote(actual_url)
                                    urls.append(actual_url)
                                except:
                                    pass
                            elif href.startswith('http'):
                                urls.append(href)
                    
                    # Limit results
                    urls = urls[:self.max_results]
                    
        except Exception as e:
            logger.error(f"Search error: {e}")
            
        return urls
    
    # ========================================
    # STAGE 2: LIGHT FILTERING
    # ========================================
    
    def filter_urls(self, urls: List[str]) -> List[str]:
        """
        Stage 2: Light filtering to remove obvious directories
        Does NOT over-validate - keeps most candidates
        """
        logger.info(f"🔎 Filtering Stage: Processing {len(urls)} URLs")
        filtered = []
        
        for url in urls:
            if self._is_valid_business_url(url):
                filtered.append(url)
            else:
                logger.debug(f"Filtered out: {url}")
        
        logger.info(f"✓ Kept {len(filtered)} URLs after filtering")
        return filtered
    
    def _is_valid_business_url(self, url: str) -> bool:
        """Check if URL is likely a real business (not a directory)"""
        try:
            parsed = urlparse(url.lower())
            domain = parsed.netloc.replace('www.', '')
            path = parsed.path.lower()
            
            # Check directory domains
            if any(dir_domain in domain for dir_domain in self.DIRECTORY_DOMAINS):
                return False
            
            # Check directory keywords in URL
            full_url = url.lower()
            if any(keyword in full_url for keyword in self.DIRECTORY_KEYWORDS):
                return False
            
            # Must have valid domain
            if not domain or '.' not in domain:
                return False
                
            return True
            
        except Exception as e:
            logger.debug(f"URL validation error for {url}: {e}")
            return False
    
    # ========================================
    # STAGE 3: PLAYWRIGHT EXTRACTION
    # ========================================
    
    async def extract_leads(self, urls: List[str]) -> List[Dict]:
        """
        Stage 3: Extract lead data from each URL using Playwright
        Returns list of lead dictionaries
        """
        logger.info(f"📊 Extraction Stage: Processing {len(urls)} websites")
        leads = []
        
        for i, url in enumerate(urls, 1):
            logger.info(f"Processing {i}/{len(urls)}: {url}")
            
            try:
                lead = await self._extract_from_website(url)
                if lead:
                    leads.append(lead)
                    logger.info(f"✓ Extracted: {lead['business_name']}")
                else:
                    logger.warning(f"✗ No data extracted from {url}")
                    
            except Exception as e:
                logger.error(f"Error processing {url}: {e}")
                continue
        
        logger.info(f"✓ Extracted {len(leads)} valid leads")
        return leads
    
    async def _extract_from_website(self, url: str) -> Optional[Dict]:
        """Extract business data from a single website using Playwright"""
        if not self.browser:
            raise RuntimeError("Browser not initialized. Use async with context.")
        
        context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        
        try:
            page = await context.new_page()
            
            # Visit homepage
            await page.goto(url, wait_until='domcontentloaded', timeout=self.timeout)
            await page.wait_for_timeout(2000)  # Let page settle
            
            # Extract from homepage
            html = await page.content()
            homepage_data = self._parse_html(html, url)
            
            # Try to find and visit contact page
            contact_data = await self._try_contact_page(page, url)
            
            # Merge data (contact page takes precedence for emails/phones)
            lead = self._merge_data(homepage_data, contact_data, url)
            
            await page.close()
            return lead if lead['business_name'] else None
            
        except Exception as e:
            logger.debug(f"Extraction error for {url}: {e}")
            return None
            
        finally:
            await context.close()
    
    async def _try_contact_page(self, page: Page, base_url: str) -> Dict:
        """Try to find and extract from contact page"""
        contact_data = {'emails': [], 'phones': []}
        
        try:
            # Look for contact links
            contact_selectors = [
                'a[href*="contact"]',
                'a[href*="kontakt"]',
                'a:has-text("Contact")',
                'a:has-text("Kontakt")',
                'a:has-text("Get in touch")'
            ]
            
            contact_link = None
            for selector in contact_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        href = await element.get_attribute('href')
                        if href:
                            contact_link = urljoin(base_url, href)
                            break
                except:
                    continue
            
            if contact_link and contact_link != page.url:
                logger.debug(f"Visiting contact page: {contact_link}")
                await page.goto(contact_link, wait_until='domcontentloaded', timeout=self.timeout)
                await page.wait_for_timeout(1500)
                
                html = await page.content()
                contact_data = self._parse_html(html, contact_link)
                contact_data['source_page'] = 'contact'
                
        except Exception as e:
            logger.debug(f"Contact page error: {e}")
        
        return contact_data
    
    def _parse_html(self, html: str, url: str) -> Dict:
        """Parse HTML to extract business information"""
        soup = BeautifulSoup(html, 'lxml')
        
        # Extract business name
        business_name = self._extract_business_name(soup, url)
        
        # Extract emails
        emails = self._extract_emails(soup)
        
        # Extract phones
        phones = self._extract_phones(soup)
        
        return {
            'business_name': business_name,
            'emails': emails,
            'phones': phones,
            'source_page': 'homepage'
        }
    
    def _extract_business_name(self, soup: BeautifulSoup, url: str) -> str:
        """Extract business name from title, h1, or domain"""
        # Try title tag
        title = soup.find('title')
        if title and title.string:
            name = title.string.strip()
            # Clean common suffixes
            name = re.split(r'\s*[\-\|]\s*', name)[0]
            if len(name) > 3 and len(name) < 100:
                return name
        
        # Try h1
        h1 = soup.find('h1')
        if h1:
            name = h1.get_text(strip=True)
            if len(name) > 3 and len(name) < 100:
                return name
        
        # Fallback to domain
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        return domain.split('.')[0].title()
    
    def _extract_emails(self, soup: BeautifulSoup) -> List[str]:
        """Extract email addresses from HTML"""
        emails = set()
        
        # Find mailto links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('mailto:'):
                email = href.replace('mailto:', '').split('?')[0].strip()
                if self._is_valid_email(email):
                    emails.add(email.lower())
        
        # Find emails in text using regex
        text = soup.get_text()
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        found_emails = re.findall(email_pattern, text)
        
        for email in found_emails:
            if self._is_valid_email(email):
                emails.add(email.lower())
        
        # Remove common false positives
        filtered = [e for e in emails if not self._is_placeholder_email(e)]
        return sorted(filtered)[:5]  # Max 5 emails
    
    def _extract_phones(self, soup: BeautifulSoup) -> List[str]:
        """Extract phone numbers from HTML"""
        phones = set()
        
        # Find tel links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('tel:'):
                phone = href.replace('tel:', '').strip()
                phone = self._clean_phone(phone)
                if phone:
                    phones.add(phone)
        
        # Find phones in text using regex
        text = soup.get_text()
        
        # Various phone patterns (international, US, European)
        phone_patterns = [
            r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}',
            r'\(\d{3}\)\s*\d{3}[-.\s]?\d{4}',
            r'\d{3}[-.\s]\d{3}[-.\s]\d{4}',
        ]
        
        for pattern in phone_patterns:
            found_phones = re.findall(pattern, text)
            for phone in found_phones:
                cleaned = self._clean_phone(phone)
                if cleaned and len(cleaned) >= 10:
                    phones.add(cleaned)
        
        return sorted(phones)[:3]  # Max 3 phone numbers
    
    def _is_valid_email(self, email: str) -> bool:
        """Validate email format"""
        pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'
        return bool(re.match(pattern, email)) and len(email) < 100
    
    def _is_placeholder_email(self, email: str) -> bool:
        """Check if email is a placeholder"""
        placeholders = ['example.com', 'test.com', 'domain.com', 'email.com', 
                       'yoursite.com', 'yourdomain.com', 'sentry.io']
        return any(ph in email for ph in placeholders)
    
    def _clean_phone(self, phone: str) -> str:
        """Clean and normalize phone number"""
        # Remove common non-digit characters
        cleaned = re.sub(r'[^\d+]', '', phone)
        return cleaned if len(cleaned) >= 10 else ''
    
    # ========================================
    # STAGE 4: OUTPUT
    # ========================================
    
    def _merge_data(self, homepage_data: Dict, contact_data: Dict, url: str) -> Dict:
        """Merge homepage and contact page data, prioritizing contact page for emails/phones"""
        
        # Use business name from homepage (usually more reliable)
        business_name = homepage_data['business_name']
        
        # Combine emails (contact page first)
        all_emails = list(dict.fromkeys(contact_data['emails'] + homepage_data['emails']))
        
        # Combine phones (contact page first)
        all_phones = list(dict.fromkeys(contact_data['phones'] + homepage_data['phones']))
        
        # Determine source
        source = 'contact' if contact_data.get('source_page') == 'contact' and (contact_data['emails'] or contact_data['phones']) else 'homepage'
        
        return {
            'business_name': business_name,
            'website': url,
            'emails': all_emails[:5],  # Max 5
            'phones': all_phones[:3],  # Max 3
            'source_page': source
        }
    
    # ========================================
    # PUBLIC API
    # ========================================
    
    async def scrape(self, niche: str, location: str) -> List[Dict]:
        """
        Main scraping pipeline
        Returns list of lead dictionaries
        """
        # Stage 1: Discovery
        urls = await self.discover_businesses(niche, location)
        
        if not urls:
            logger.warning("No URLs discovered")
            return []
        
        # Stage 2: Filtering
        filtered_urls = self.filter_urls(urls)
        
        if not filtered_urls:
            logger.warning("All URLs filtered out")
            return []
        
        # Stage 3: Extraction
        leads = await self.extract_leads(filtered_urls)
        
        return leads


# ========================================
# STANDALONE TEST
# ========================================

async def test_scraper():
    """Test the scraper with a sample query"""
    async with LeadScraper(max_results=10, timeout=15, headless=True) as scraper:
        leads = await scraper.scrape("coffee shops", "Berlin")
        
        print(f"\n✓ Found {len(leads)} leads:\n")
        for i, lead in enumerate(leads, 1):
            print(f"{i}. {lead['business_name']}")
            print(f"   Website: {lead['website']}")
            print(f"   Emails: {', '.join(lead['emails']) if lead['emails'] else 'None'}")
            print(f"   Phones: {', '.join(lead['phones']) if lead['phones'] else 'None'}")
            print(f"   Source: {lead['source_page']}\n")


if __name__ == "__main__":
    asyncio.run(test_scraper())
