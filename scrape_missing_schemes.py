import asyncio
import json
import os
from playwright.async_api import async_playwright

async def scrape_scheme_details(page, full_link, scheme_title="Unknown"):
    """
    Scrape detailed information from a scheme's individual page
    This function is copied from your complete_scraper.py with full logic
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

async def main():
    missing_schemes_file = r"E:\Capital\scraping\missing_schemes.json"
    details_file = r"E:\Capital\scraping\details_cleaned.json"
    failed_schemes_file = r"E:\Capital\scraping\failed_missing_schemes.json"

    # Load the list of missing schemes
    try:
        with open(missing_schemes_file, 'r', encoding='utf-8') as f:
            schemes_to_scrape = json.load(f)
        print(f"✅ Found {len(schemes_to_scrape)} missing schemes to scrape.")
    except FileNotFoundError:
        print(f"❌ Error: '{missing_schemes_file}' not found. Run the comparison script first.")
        return
    except json.JSONDecodeError:
        print(f"❌ Error: Could not decode JSON from '{missing_schemes_file}'.")
        return

    # Load existing schemes to avoid duplicates and to append to
    try:
        with open(details_file, 'r', encoding='utf-8') as f:
            existing_details = json.load(f)
        print(f"✅ Loaded {len(existing_details)} existing schemes from '{details_file}'.")
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"⚠️ Warning: Could not load '{details_file}'. A new file will be created with only the newly scraped schemes.")
        existing_details = []

    newly_scraped_schemes = []
    failed_schemes = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        for i, scheme in enumerate(schemes_to_scrape):
            print(f"\n{'='*60}")
            print(f"🔍 PROCESSING {i+1}/{len(schemes_to_scrape)}: {scheme.get('title', 'Unknown')}")
            print(f"{'='*60}")

            try:
                details = await scrape_scheme_details(page, scheme['link'], scheme['title'])
                
                if any("Error loading page:" in str(v) for v in details.values()):
                    print(f"  ❌ Failed to extract details for {scheme['title']}")
                    failed_schemes.append(scheme)
                else:
                    # Combine original info with scraped details
                    detailed_scheme = {
                        "title": scheme.get('title'),
                        "description": "No description found",
                        "link": scheme.get('link'),
                        **details
                    }
                    newly_scraped_schemes.append(detailed_scheme)
                    print(f"  ✅ Successfully extracted details for {scheme['title']}")

                await asyncio.sleep(1)  # Small delay between requests

            except Exception as e:
                print(f"  ❌ An unexpected error occurred while processing {scheme['title']}: {e}")
                failed_schemes.append(scheme)
                continue

        await browser.close()

    if newly_scraped_schemes:
        updated_details = existing_details + newly_scraped_schemes
        print(f"\n✅ Added {len(newly_scraped_schemes)} new schemes.")
        print(f"📈 Total schemes now: {len(updated_details)}")

        try:
            # Sort the final list alphabetically by title for consistency
            updated_details.sort(key=lambda x: x.get('title', ''))
            with open(details_file, 'w', encoding='utf-8') as f:
                json.dump(updated_details, f, indent=2, ensure_ascii=False)
            print(f"💾 Successfully updated '{details_file}'")
        except Exception as e:
            print(f"❌ Error saving updated data to '{details_file}': {e}")

    if failed_schemes:
        print(f"\n❌ {len(failed_schemes)} schemes failed to scrape.")
        try:
            with open(failed_schemes_file, 'w', encoding='utf-8') as f:
                json.dump(failed_schemes, f, indent=2, ensure_ascii=False)
            print(f"📋 Failed schemes list saved to '{failed_schemes_file}'")
        except Exception as e:
            print(f"❌ Error saving failed schemes list: {e}")

if __name__ == "__main__":
    asyncio.run(main())

