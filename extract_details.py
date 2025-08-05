import asyncio
import json
from playwright.async_api import async_playwright
import re

async def scrape_scheme_details(page, full_link):
    """
    Scrape detailed information from a scheme's individual page
    """
    details = {}
    
    try:
        print(f"Navigating to: {full_link}")
        await page.goto(full_link, wait_until='networkidle')
        
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
            print(f"Looking for section: {heading}")
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
                        print(f"Found heading with selector: {selector}")
                        
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
                            print(f"Found content for {heading}: {section_content[:100]}...")
                            break
                            
                except Exception as e:
                    print(f"Error with selector {selector}: {e}")
                    continue
            
            if not content_found:
                details[key] = "Section not found"
                print(f"Section {heading} not found on page")
        
    except Exception as e:
        print(f"Error loading page {full_link}: {e}")
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

async def main():
    # Read the existing schemes data
    try:
        with open('E:\\Capital\\scraping\\all_schemes_data.json', 'r', encoding='utf-8') as f:
            schemes_data = json.load(f)
        print(f"Loaded {len(schemes_data)} schemes from all_schemes_data.json")
    except Exception as e:
        print(f"Error loading schemes data: {e}")
        return
    
    # Launch browser
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        detailed_schemes = []
        
        for i, scheme in enumerate(schemes_data):
            print(f"\nProcessing scheme {i+1}/{len(schemes_data)}: {scheme.get('title', 'Unknown')}")
            
            # Get the link
            link = scheme.get('link', '')
            if not link or link == "No link found":
                print("No valid link found, skipping...")
                continue
            
            # Ensure the link is complete
            if not link.startswith('http'):
                if link.startswith('/'):
                    link = f"https://www.myscheme.gov.in{link}"
                else:
                    link = f"https://www.myscheme.gov.in/{link}"
            
            # Extract detailed information
            details = await scrape_scheme_details(page, link)
            
            # Combine original scheme data with detailed information
            detailed_scheme = {
                "title": scheme.get('title', 'Unknown'),
                "description": scheme.get('description', 'No description'),
                "link": link,
                **details  # Add all the detailed sections
            }
            
            detailed_schemes.append(detailed_scheme)
            
            # Add a small delay between requests to be respectful
            await asyncio.sleep(2)
        
        await browser.close()
    
    # Save detailed data to JSON file
    try:
        with open('E:\\Capital\\scraping\\details.json', 'w', encoding='utf-8') as f:
            json.dump(detailed_schemes, f, indent=2, ensure_ascii=False)
        print(f"\nSuccessfully saved {len(detailed_schemes)} detailed schemes to details.json")
    except Exception as e:
        print(f"Error saving detailed data: {e}")

if __name__ == "__main__":
    asyncio.run(main())
