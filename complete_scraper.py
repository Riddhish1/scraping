import asyncio
import json
from playwright.async_api import async_playwright
import time

async def scrape_scheme_details(page, full_link, scheme_title="Unknown"):
    """
    Scrape detailed information from a scheme's individual page
    """
    details = {}
    
    try:
        print(f"  📄 Extracting details from: {scheme_title}")
        await page.goto(full_link, wait_until='networkidle', timeout=30000)
        
        # Define sections to scrape
        sections = {
            "details": "Details",
            "objective": "Objective", 
            "benefits": "Benefits",
            "eligibility": "Eligibility",
            "exclusions": "Exclusions",
            "application_process": "Application Process",
            "documents_required": "Documents Required",
            "frequently_asked_questions": "Frequently Asked Questions",
            "sources_and_references": "Sources And References"
        }
        
        # Try multiple selector strategies for each section
        for key, heading in sections.items():
            section_content = ""
            
            # Strategy 1: Look for exact heading match
            selectors_to_try = [
                f'h2:text-is("{heading}")',
                f'h3:text-is("{heading}")',
                f'h4:text-is("{heading}")',
                f'h2:has-text("{heading}")',
                f'h3:has-text("{heading}")',
                f'h4:has-text("{heading}")',
                f'*:text-is("{heading}")',
                f'*:has-text("{heading}")'
            ]
            
            content_found = False
            
            for selector in selectors_to_try:
                try:
                    heading_element = await page.query_selector(selector)
                    if heading_element:
                        
                        # Special handling for Sources And References
                        if key == "sources_and_references":
                            # Look for the container after the heading
                            next_container = await heading_element.evaluate_handle("""
                                el => {
                                    let next = el.nextElementSibling;
                                    // Find the next container that has content
                                    while (next && (!next.textContent || next.textContent.trim() === '')) {
                                        next = next.nextElementSibling;
                                    }
                                    return next;
                                }
                            """)
                            
                            if next_container:
                                # Look for links within this container
                                links = await next_container.query_selector_all('a')
                                if links:
                                    sources_list = []
                                    for link in links:
                                        link_text = await link.text_content()
                                        link_href = await link.get_attribute('href')
                                        if link_text and link_text.strip():
                                            if link_href:
                                                # Make sure href is absolute
                                                if link_href.startswith('/'):
                                                    link_href = f"https://www.myscheme.gov.in{link_href}"
                                                sources_list.append(f"{link_text.strip()}: {link_href}")
                                            else:
                                                sources_list.append(link_text.strip())
                                    section_content = "\n".join(sources_list) if sources_list else ""
                                
                                # If no links found, get all text
                                if not section_content:
                                    section_content = await next_container.text_content()
                        else:
                            # Regular content extraction for other sections
                            # Try to get content from next sibling or parent container
                            next_element = await heading_element.evaluate_handle("""
                                el => {
                                    let next = el.nextElementSibling;
                                    // Skip empty elements
                                    while (next && (!next.textContent || next.textContent.trim() === '')) {
                                        next = next.nextElementSibling;
                                    }
                                    return next;
                                }
                            """)
                            
                            if next_element:
                                section_content = await next_element.text_content()
                            else:
                                # Try to find content in parent container
                                parent = await heading_element.query_selector('xpath=..')
                                if parent:
                                    # Get all text after the heading within the parent
                                    section_content = await parent.evaluate(f"""
                                        el => {{
                                            const heading = el.querySelector('*[textContent*="{heading}"]') || el.querySelector('*:has-text("{heading}")');
                                            if (heading) {{
                                                let content = '';
                                                let next = heading.nextSibling;
                                                while (next) {{
                                                    if (next.nodeType === Node.TEXT_NODE) {{
                                                        content += next.textContent;
                                                    }} else if (next.nodeType === Node.ELEMENT_NODE) {{
                                                        content += next.textContent;
                                                    }}
                                                    next = next.nextSibling;
                                                }}
                                                return content;
                                            }}
                                            return '';
                                        }}
                                    """)
                        
                        if section_content and section_content.strip():
                            details[key] = section_content.strip()
                            content_found = True
                            break
                            
                except Exception as e:
                    continue
            
            if not content_found:
                details[key] = "Section not found"
        
    except Exception as e:
        print(f"    ❌ Error loading details for {scheme_title}: {e}")
        # Add error info to all sections
        error_sections = {
            "details": "Details",
            "objective": "Objective", 
            "benefits": "Benefits",
            "eligibility": "Eligibility",
            "exclusions": "Exclusions",
            "application_process": "Application Process",
            "documents_required": "Documents Required",
            "frequently_asked_questions": "Frequently Asked Questions",
            "sources_and_references": "Sources And References"
        }
        for key in error_sections.keys():
            details[key] = f"Error loading page: {e}"
    
    return details

async def scrape_page_schemes(page, page_number):
    """
    Extract all scheme links and basic info from current page
    """
    schemes = []
    
    try:
        # Wait for content to load with longer timeout
        await page.wait_for_timeout(5000)
        
        # Debug: Check current URL
        current_url = page.url
        print(f"  🌐 Current URL: {current_url}")
        
        # Check if we're on an unexpected page (like DigiLocker)
        if 'digilocker' in current_url.lower() or 'signinv2' in current_url.lower() or 'signin' in current_url.lower():
            print(f"  ⚠️ Detected authentication/login page, skipping...")
            return schemes
        
        # Debug: Check if page has loaded properly
        page_title = await page.title()
        print(f"  📄 Page title: {page_title}")
        
        # Find scheme links with multiple strategies
        selectors_to_try = [
            'a[href*="/schemes/"]',  # More specific selector
            'a[href*="scheme"]',
            '[data-testid*="scheme"]'
        ]
        
        scheme_elements = []
        for selector in selectors_to_try:
            try:
                elements = await page.query_selector_all(selector)
                if elements:
                    print(f"  Found {len(elements)} scheme elements with selector: {selector}")
                    scheme_elements = elements
                    break
                else:
                    print(f"  No elements found with selector: {selector}")
            except Exception as e:
                print(f"  Error with selector {selector}: {e}")
                continue
        
        if not scheme_elements:
            print(f"  ❌ No scheme elements found on page {page_number}")
            
            # Debug: Check what links are available
            all_links = await page.query_selector_all('a')
            print(f"  🔍 Total links on page: {len(all_links)}")
            
            # Check for any links that might be schemes
            scheme_like_links = 0
            for link in all_links[:20]:  # Check first 20 links
                href = await link.get_attribute('href')
                if href and ('scheme' in href.lower() or '/schemes/' in href):
                    scheme_like_links += 1
                    print(f"    Found scheme-like link: {href}")
            
            print(f"  🔍 Found {scheme_like_links} scheme-like links")
            return schemes
        
        # Extract scheme information
        for i, scheme_element in enumerate(scheme_elements):
            try:
                # Get link
                link = await scheme_element.get_attribute('href')
                if not link:
                    continue
                
                # Get title
                title = await scheme_element.text_content()
                if not title or title.strip() == "":
                    # Try parent element
                    parent = await scheme_element.query_selector('xpath=..')
                    if parent:
                        title = await parent.text_content()
                
                # Get description from nearby elements
                description = "No description found"
                try:
                    # Look for description in parent containers
                    container = await scheme_element.query_selector('xpath=..//..')
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
                    'page_found': page_number
                }
                
                schemes.append(scheme_info)
                print(f"    📋 {i+1}. {scheme_info['title'][:50]}...")
                
            except Exception as e:
                print(f"    ❌ Error extracting scheme {i}: {e}")
                continue
    
    except Exception as e:
        print(f"  ❌ Error extracting schemes from page {page_number}: {e}")
    
    return schemes

async def navigate_to_next_page(page, current_page, max_pages):
    """
    Navigate to the next page using pagination - matches improved_scraper.py logic
    """
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
                        print(f"  🔄 Clicking page {next_page_number} with selector: {selector}")
                        
                        # Scroll into view
                        await next_button.scroll_into_view_if_needed()
                        await page.wait_for_timeout(1000)
                        
                        # Click the button
                        await next_button.click()
                        await page.wait_for_load_state('networkidle', timeout=30000)
                        
                        # Verify we're on the new page
                        await page.wait_for_timeout(2000)
                        
                        # Check for unexpected navigation
                        new_url = page.url
                        if 'digilocker' in new_url or 'signinv2' in new_url:
                            print("  ⚠️ Unexpected navigation to an authentication page, stopping navigation")
                            return False
                        
                        navigation_success = True
                        print(f"  ✅ Successfully navigated to page {next_page_number}")
                        return True
                except Exception as e:
                    print(f"  ❌ Failed to click with selector {selector}: {e}")
                    continue
            
            if navigation_success:
                return True
        except Exception as e:
            print(f"  ❌ Page number navigation failed: {e}")
    
    # Strategy 2: Try finding and clicking next button or arrow (but avoid SVG buttons that might cause redirects)
    if not navigation_success:
        try:
            next_selectors = [
                '[aria-label*="next"]',
                '[class*="next"]',
                'button:not(:has(svg))'  # Avoid SVG buttons that might cause redirects
            ]
            
            for selector in next_selectors:
                try:
                    next_elem = await page.query_selector(selector)
                    if next_elem:
                        print(f"  🔄 Trying next button with selector: {selector}")
                        await next_elem.scroll_into_view_if_needed()
                        
                        # Get current URL before clicking
                        old_url = page.url
                        
                        await next_elem.click()
                        await page.wait_for_load_state('networkidle', timeout=30000)
                        
                        # Check if we got redirected to an auth page
                        new_url = page.url
                        if 'digilocker' in new_url or 'signinv2' in new_url:
                            print("  ⚠️ Navigation led to authentication page, stopping")
                            return False
                        
                        navigation_success = True
                        print(f"  ✅ Successfully navigated to page {next_page_number}")
                        return True
                except Exception as e:
                    print(f"  ❌ Next button click failed: {e}")
                    continue
        except Exception as e:
            print(f"  ❌ Next button navigation failed: {e}")
    
    return False

async def collect_all_scheme_links(page, max_pages):
    """
    Phase 1: Loop through all pages and collect scheme links without visiting them.
    """
    all_schemes = []
    seen_links = set()
    current_page = 1

    while current_page <= max_pages:
        print(f"\n{'='*60}")
        print(f"🔍 COLLECTING LINKS FROM PAGE {current_page}")
        print(f"{'='*60}")

        try:
            page_schemes = await scrape_page_schemes(page, current_page)
            if not page_schemes:
                print(f"❌ No more schemes found on page {current_page}, stopping collection.")
                break

            new_schemes_found = 0
            for scheme in page_schemes:
                if scheme['link'] not in seen_links:
                    seen_links.add(scheme['link'])
                    all_schemes.append(scheme)
                    new_schemes_found += 1
            
            print(f"📊 Found {new_schemes_found} new schemes on page {current_page}")
            print(f"📈 Total unique schemes collected so far: {len(all_schemes)}")

            # Navigate to the next page
            if current_page < max_pages:
                navigation_success = await navigate_to_next_page(page, current_page, max_pages)
                if navigation_success:
                    current_page += 1
                else:
                    print(f"❌ Could not navigate from page {current_page}. Stopping link collection.")
                    break
            else:
                print(f"🎯 Reached maximum pages ({max_pages})")
                break

        except Exception as e:
            print(f"❌ Error collecting links on page {current_page}: {e}")
            current_page += 1
            continue
            
    return all_schemes

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # Go to the initial search page
        await page.goto('https://www.myscheme.gov.in/search/category/Agriculture,Rural%20&%20Environment', wait_until='networkidle')
        print("🌐 Page loaded")
        await page.wait_for_timeout(5000)
        
        # --- PHASE 1: Collect all scheme links --- #
        all_schemes_to_process = await collect_all_scheme_links(page, max_pages=60)
        
        if not all_schemes_to_process:
            print("\n❌ No schemes were collected. Exiting.")
            await browser.close()
            return

        print(f"\n{'='*60}")
        print(f"✅ Link collection finished. Found {len(all_schemes_to_process)} unique schemes.")
        print(f"{'='*60}")
        
        # --- PHASE 2: Scrape details for each collected link --- #
        all_detailed_schemes = []
        failed_schemes = []
        
        for i, scheme in enumerate(all_schemes_to_process):
            print(f"\n{'~'*60}")
            print(f"🔍 PROCESSING {i+1}/{len(all_schemes_to_process)}: {scheme['title'][:50]}...")
            print(f"{'~'*60}")
            
            try:
                # Directly navigate to the scheme's page to get details
                details = await scrape_scheme_details(page, scheme['link'], scheme['title'])
                
                if any("Error loading page:" in str(details.get(key, "")) for key in details):
                    print(f"      ❌ Failed to extract details for {scheme['title']}")
                    failed_schemes.append(scheme)
                else:
                    # Combine the initial data with the scraped details
                    detailed_scheme = {
                        **scheme,
                        **details
                    }
                    all_detailed_schemes.append(detailed_scheme)
                    print(f"      ✅ Successfully extracted details for {scheme['title']}")

                # Small delay between requests
                await asyncio.sleep(1)

            except Exception as e:
                print(f"      ❌ An unexpected error occurred while processing {scheme['title']}: {e}")
                failed_schemes.append(scheme)
                continue

        await browser.close()
        
        # --- FINAL: Save all collected data --- #
        try:
            with open('E:\\Capital\\scraping\\complete_details.json', 'w', encoding='utf-8') as f:
                json.dump(all_detailed_schemes, f, indent=2, ensure_ascii=False)
            print(f"\n{'='*60}")
            print(f"🎉 SCRAPING COMPLETED 🎉")
            print(f"{'='*60}")
            print(f"📊 Total schemes with details: {len(all_detailed_schemes)}")
            print(f"❌ Failed schemes: {len(failed_schemes)}")
            print(f"💾 Data saved to 'complete_details.json'")
            
            if failed_schemes:
                with open('E:\\Capital\\scraping\\failed_schemes_list.json', 'w', encoding='utf-8') as f:
                    json.dump(failed_schemes, f, indent=2, ensure_ascii=False)
                print(f"📋 Failed schemes saved to 'failed_schemes_list.json'")

        except Exception as e:
            print(f"❌ Error saving data: {e}")

if __name__ == "__main__":
    asyncio.run(main())
