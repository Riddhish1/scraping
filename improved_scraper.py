import asyncio
import json
from playwright.async_api import async_playwright
import time

async def scrape():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # Go to the agriculture schemes page
        await page.goto('https://www.myscheme.gov.in/search/category/Agriculture,Rural%20&%20Environment')
        print("Page loaded")
        
        # Wait for page to fully load
        await page.wait_for_timeout(5000)
        
        current_page = 1
        max_pages = 60
        all_scheme_data = []
        seen_links = set()  # Track unique links to prevent duplicates
        failed_pages = []
        
        while current_page <= max_pages:
            print(f"\n{'='*50}")
            print(f"SCRAPING PAGE {current_page}")
            print(f"{'='*50}")
            
            try:
                # Wait for content to load
                await page.wait_for_timeout(3000)
                
                # Find scheme links with multiple strategies
                schemes = []
                selectors_to_try = [
                    'a[href*="/schemes/"]',  # More specific selector
                    'a[href*="scheme"]',
                    '[data-testid*="scheme"]'
                ]
                
                for selector in selectors_to_try:
                    try:
                        elements = await page.query_selector_all(selector)
                        if elements:
                            print(f"Found {len(elements)} elements with selector: {selector}")
                            schemes = elements
                            break
                    except Exception as e:
                        print(f"Selector {selector} failed: {e}")
                        continue
                
                if not schemes:
                    print(f"❌ No schemes found on page {current_page}")
                    failed_pages.append(current_page)
                else:
                    print(f"✅ Found {len(schemes)} schemes on page {current_page}")
                    
                    # Extract scheme information
                    page_schemes = []
                    for i, scheme in enumerate(schemes):
                        try:
                            # Get link
                            link = await scheme.get_attribute('href')
                            if not link:
                                continue
                                
                            # Skip if we've already seen this link
                            if link in seen_links:
                                print(f"  Skipping duplicate: {link}")
                                continue
                                
                            seen_links.add(link)
                            
                            # Get title
                            title = await scheme.text_content()
                            if not title or title.strip() == "":
                                # Try parent element
                                parent = await scheme.query_selector('xpath=..')
                                if parent:
                                    title = await parent.text_content()
                            
                            # Get description from nearby elements
                            description = "No description found"
                            try:
                                # Look for description in parent containers
                                container = await scheme.query_selector('xpath=..//..')
                                if container:
                                    desc_elem = await container.query_selector('p, div[class*="desc"], div[class*="summary"], .text-gray-600')
                                    if desc_elem:
                                        description = await desc_elem.text_content()
                            except:
                                pass
                            
                            # Clean and format the data
                            scheme_info = {
                                'title': title.strip() if title else "No title found",
                                'description': description.strip()[:200] if description else "No description found",
                                'link': link if link.startswith('http') else f"https://www.myscheme.gov.in{link}",
                                'page_found': current_page
                            }
                            
                            page_schemes.append(scheme_info)
                            print(f"  ✓ Extracted: {scheme_info['title'][:50]}...")
                            
                        except Exception as e:
                            print(f"  ❌ Error extracting scheme {i}: {e}")
                            continue
                    
                    all_scheme_data.extend(page_schemes)
                    print(f"📊 Page {current_page}: Added {len(page_schemes)} new schemes (Total: {len(all_scheme_data)})")
                
                # Try to navigate to next page
                navigation_success = False
                
                # Strategy 1: Try clicking on the next page number
                next_page_number = current_page + 1
                if next_page_number <= max_pages:
                    try:
                        # Try different selectors for pagination
                        pagination_selectors = [
                            f'li:has-text("{next_page_number}"):not(.bg-green-700)',
                            f'li.hover\\:cursor-pointer :has-text("{next_page_number}")',
                            f'li[class*="cursor-pointer"]:has-text("{next_page_number}")',
                            f'*:has-text("{next_page_number}")[class*="cursor-pointer"]'
                        ]
                        
                        for selector in pagination_selectors:
                            try:
                                next_button = await page.query_selector(selector)
                                if next_button:
                                    print(f"🔄 Clicking page {next_page_number} with selector: {selector}")
                                    
                                    # Scroll into view
                                    await next_button.scroll_into_view_if_needed()
                                    await page.wait_for_timeout(1000)
                                    
                                    # Click the button
                                    await next_button.click()
                                    await page.wait_for_load_state('networkidle', timeout=30000)
                                    
                                    # Verify we're on the new page
                                    await page.wait_for_timeout(2000)
                                    current_page = next_page_number
                                    navigation_success = True
                                    print(f"✅ Successfully navigated to page {current_page}")
                                    break
                            except Exception as e:
                                print(f"❌ Failed to click with selector {selector}: {e}")
                                continue
                        
                        if navigation_success:
                            continue
                    except Exception as e:
                        print(f"❌ Page number navigation failed: {e}")
                
                # Strategy 2: Try finding and clicking next button or arrow
                if not navigation_success:
                    try:
                        next_selectors = [
                            'button:has(svg)',
                            '[aria-label*="next"]',
                            '[class*="next"]',
                            'svg[class*="cursor-pointer"]'
                        ]
                        
                        for selector in next_selectors:
                            try:
                                next_elem = await page.query_selector(selector)
                                if next_elem:
                                    print(f"🔄 Trying next button with selector: {selector}")
                                    await next_elem.scroll_into_view_if_needed()
                                    await next_elem.click()
                                    await page.wait_for_load_state('networkidle', timeout=30000)
                                    current_page += 1
                                    navigation_success = True
                                    print(f"✅ Successfully navigated to page {current_page}")
                                    break
                            except Exception as e:
                                print(f"❌ Next button click failed: {e}")
                                continue
                    except Exception as e:
                        print(f"❌ Next button navigation failed: {e}")
                
                # If navigation failed, break the loop
                if not navigation_success:
                    print(f"❌ Could not navigate from page {current_page}. Stopping.")
                    break
                    
            except Exception as e:
                print(f"❌ Error on page {current_page}: {e}")
                failed_pages.append(current_page)
                current_page += 1
                continue
        
        # Save all data to JSON file
        with open('all_schemes_data.json', 'w', encoding='utf-8') as f:
            json.dump(all_scheme_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n{'='*60}")
        print(f"SCRAPING COMPLETED")
        print(f"{'='*60}")
        print(f"📊 Total schemes extracted: {len(all_scheme_data)}")
        print(f"📄 Pages scraped: {current_page - 1}")
        print(f"❌ Failed pages: {failed_pages}")
        print(f"💾 Data saved to 'all_schemes_data.json'")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape())
