import asyncio
import json
from playwright.async_api import async_playwright

async def scrape():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # Set to False to see browser
        page = await browser.new_page()
        
        # Go to the agriculture schemes page
        await page.goto('https://www.myscheme.gov.in/search/category/Agriculture,Rural%20&%20Environment')
        print("Page loaded")
        
        # Wait for page to fully load
        await page.wait_for_timeout(5000)
        
        # Try different selectors to find scheme cards/links
        possible_selectors = [
            'a[href*="scheme"]',
            'div[class*="card"]',
            'div[class*="scheme"]',
            'a[class*="card"]',
            'div[class*="item"]',
            '[data-testid*="scheme"]',
            '.card',
            '.scheme-card'
        ]

        current_page = 1
        max_pages = 60  # Increased to scrape all pages
        all_scheme_data = []

        while current_page <= max_pages:
            print(f"Scraping page {current_page}")
            schemes = []
            for selector in possible_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        print(f"Found {len(elements)} elements with selector: {selector} on page {current_page}")
                        schemes = elements
                        break
                except Exception as e:
                    continue
            
            if not schemes:
                print("No scheme elements found. Let's inspect the page structure...")
                # Get page content to inspect
                content = await page.content()
                print("Page HTML length:", len(content))
                
                # Look for common patterns
                scheme_links = await page.query_selector_all('a')
                print(f"Total links found: {len(scheme_links)}")
                
                # Print first few link hrefs to understand structure
                for i, link in enumerate(scheme_links[:10]):
                    href = await link.get_attribute('href')
                    text = await link.text_content()
                    if href and 'scheme' in href.lower():
                        print(f"Scheme link {i}: {href} - {text[:50]}")
                
                await browser.close()
                return
            
            print(f"Found {len(schemes)} scheme elements")
            
            # Extract scheme information
            scheme_data = []
            for i, scheme in enumerate(schemes):
                try:
                    # Get the tag name properly
                    tag_name = await scheme.evaluate('el => el.tagName.toLowerCase()')
                    
                    # Get scheme link (since we found links with a[href*="scheme"])
                    link = await scheme.get_attribute('href') if tag_name == 'a' else "No link found"
                    
                    # Get scheme title from the link text or nearby elements
                    title = await scheme.text_content()
                    if not title or title.strip() == "":
                        # Try to find title in parent or nearby elements
                        parent = await scheme.query_selector('xpath=..')
                        if parent:
                            title = await parent.text_content()
                    
                    # Try to get scheme description from parent container
                    parent_container = await scheme.query_selector('xpath=..//..')
                    description = "No description found"
                    if parent_container:
                        desc_element = await parent_container.query_selector('p, div[class*="desc"], div[class*="summary"]')
                        if desc_element:
                            description = await desc_element.text_content()
                    
                    scheme_info = {
                        'title': title.strip() if title else "No title found",
                        'description': description.strip()[:200] if description else "No description found",
                        'link': link if link and not link.startswith('#') else f"https://www.myscheme.gov.in{link}" if link else "No link found"
                    }
                    
                    scheme_data.append(scheme_info)
                    print(f"Scheme {i+1}:")
                    print(f"  Title: {scheme_info['title']}")
                    print(f"  Description: {scheme_info['description']}")
                    print(f"  Link: {scheme_info['link']}")
                    print("-" * 50)
                    
                except Exception as e:
                    print(f"Error processing scheme {i}: {e}")
                    # Let's try a simpler approach for this element
                    try:
                        simple_text = await scheme.text_content()
                        simple_link = await scheme.get_attribute('href')
                        print(f"  Simple extraction - Text: {simple_text[:100]} Link: {simple_link}")
                    except:
                        print(f"  Could not extract anything from scheme {i}")
            
            all_scheme_data.extend(scheme_data)

            # Debug: Let's see what pagination elements are available
            print("\nDebugging pagination elements...")
            pagination_area = await page.query_selector_all('[class*="pagination"], [class*="pager"], nav')
            print(f"Found {len(pagination_area)} potential pagination containers")
            
            # Look for all clickable elements that might be pagination
            all_buttons = await page.query_selector_all('button, a, div[class*="cursor-pointer"]')
            for i, btn in enumerate(all_buttons[-10:]):  # Check last 10 elements which are likely pagination
                try:
                    text = await btn.text_content()
                    classes = await btn.get_attribute('class')
                    if text and (text.strip().isdigit() or 'next' in text.lower() or '>' in text):
                        print(f"Pagination candidate {i}: '{text.strip()}' - classes: {classes}")
                except:
                    continue
            
            # Try to go to the next page using multiple strategies
            try:
                # Strategy 1: Manually click on the next page number
                next_page_number = current_page + 1
                next_page_button = await page.query_selector(f'li:has-text("{next_page_number}")')
                if next_page_button:
                    print("Found page number", next_page_number)
                    await next_page_button.click()
                    await page.wait_for_load_state('networkidle')
                    current_page += 1
                    continue
                
                # Strategy 2: Try finding clickable elements containing SVG
                svg_containers = await page.query_selector_all('*:has(svg.cursor-pointer)')
                if svg_containers:
                    for container in svg_containers:
                        try:
                            print("Trying to click SVG container...")
                            await container.click(timeout=5000)
                            await page.wait_for_load_state('networkidle')
                            current_page += 1
                            print(f"Successfully navigated to page {current_page}")
                            break
                        except Exception as e:
                            print(f"SVG container click failed: {e}")
                            continue
                    else:
                        # If we get here, none of the SVG containers worked
                        pass
                
                # Strategy 3: Try different pagination selectors
                pagination_selectors = [
                    'button:has-text("Next")',
                    'a:has-text("Next")',
                    '[aria-label="Next page"]',
                    '[data-testid="next-page"]',
                    'button[class*="next"]',
                    'a[class*="next"]'
                ]
                
                found_next = False
                for selector in pagination_selectors:
                    try:
                        next_elem = await page.query_selector(selector)
                        if next_elem:
                            print(f"Found next button with selector: {selector}")
                            await next_elem.click()
                            await page.wait_for_load_state('networkidle')
                            current_page += 1
                            found_next = True
                            break
                    except:
                        continue
                
                if not found_next:
                    # Strategy 4: Try URL-based pagination as last resort
                    current_url = page.url
                    if 'page=' in current_url:
                        # Replace page parameter
                        new_url = current_url.replace(f'page={current_page}', f'page={current_page + 1}')
                    else:
                        # Add page parameter
                        separator = '&' if '?' in current_url else '?'
                        new_url = f"{current_url}{separator}page={current_page + 1}"
                    
                    try:
                        print(f"Trying URL-based pagination: {new_url}")
                        await page.goto(new_url)
                        await page.wait_for_load_state('networkidle')
                        current_page += 1
                        continue
                    except:
                        print("URL-based pagination failed. No more pages found.")
                        break
                    
            except Exception as e:
                print(f"Error navigating to the next page: {e}")
                break
        # Save all data to JSON file
        with open('all_schemes_data.json', 'w', encoding='utf-8') as f:
            json.dump(all_scheme_data, f, indent=2, ensure_ascii=False)

        print(f"\nExtracted {len(all_scheme_data)} schemes from all pages and saved to all_schemes_data.json")
        
        await browser.close()

asyncio.run(scrape())
