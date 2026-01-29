"""
Example test script demonstrating the Lead Scraper usage
Run this to test the scraper functionality
"""

import asyncio
import json
from scraper import LeadScraper


async def test_basic_scraping():
    """Test basic scraping functionality"""
    print("=" * 60)
    print("TEST 1: Basic Scraping")
    print("=" * 60)
    
    async with LeadScraper(max_results=10, timeout=15, headless=True) as scraper:
        leads = await scraper.scrape("coffee shops", "Munich")
        
        print(f"\n✓ Found {len(leads)} leads\n")
        
        for i, lead in enumerate(leads, 1):
            print(f"{i}. {lead['business_name']}")
            print(f"   Website: {lead['website']}")
            print(f"   Emails: {', '.join(lead['emails']) if lead['emails'] else 'None found'}")
            print(f"   Phones: {', '.join(lead['phones']) if lead['phones'] else 'None found'}")
            print(f"   Source: {lead['source_page']}")
            print()


async def test_multiple_niches():
    """Test scraping multiple niches"""
    print("=" * 60)
    print("TEST 2: Multiple Niches")
    print("=" * 60)
    
    test_queries = [
        ("bakeries", "Berlin", 5),
        ("dentists", "Hamburg", 5),
    ]
    
    all_results = []
    
    async with LeadScraper(max_results=5, timeout=15, headless=True) as scraper:
        for niche, location, max_results in test_queries:
            print(f"\n🔍 Searching: {niche} in {location}")
            leads = await scraper.scrape(niche, location)
            print(f"✓ Found {len(leads)} leads")
            all_results.extend(leads)
    
    print(f"\n📊 Total leads across all queries: {len(all_results)}")


async def test_data_quality():
    """Test data quality - check what percentage has contact info"""
    print("=" * 60)
    print("TEST 3: Data Quality Analysis")
    print("=" * 60)
    
    async with LeadScraper(max_results=15, timeout=15, headless=True) as scraper:
        leads = await scraper.scrape("restaurants", "Frankfurt")
        
        total = len(leads)
        with_emails = sum(1 for lead in leads if lead['emails'])
        with_phones = sum(1 for lead in leads if lead['phones'])
        with_both = sum(1 for lead in leads if lead['emails'] and lead['phones'])
        
        print(f"\n📊 Quality Metrics:")
        print(f"   Total leads: {total}")
        print(f"   With emails: {with_emails} ({with_emails/total*100:.1f}%)")
        print(f"   With phones: {with_phones} ({with_phones/total*100:.1f}%)")
        print(f"   With both: {with_both} ({with_both/total*100:.1f}%)")


async def test_export_to_json():
    """Test exporting leads to JSON"""
    print("=" * 60)
    print("TEST 4: Export to JSON")
    print("=" * 60)
    
    async with LeadScraper(max_results=10, timeout=15, headless=True) as scraper:
        leads = await scraper.scrape("yoga studios", "Munich")
        
        # Export to JSON file
        output_file = "test_leads_export.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(leads, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Exported {len(leads)} leads to {output_file}")
        print(f"   File size: {len(json.dumps(leads, indent=2))} bytes")


async def main():
    """Run all tests"""
    print("\n🧪 Lead Scraper Test Suite\n")
    
    # Run tests
    await test_basic_scraping()
    await asyncio.sleep(2)  # Be nice to servers
    
    # Uncomment other tests as needed
    # await test_multiple_niches()
    # await asyncio.sleep(2)
    
    # await test_data_quality()
    # await asyncio.sleep(2)
    
    # await test_export_to_json()
    
    print("\n✅ All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
