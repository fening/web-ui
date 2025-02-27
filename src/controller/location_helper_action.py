import logging
from pydantic import BaseModel, Field
from browser_use.agent.views import ActionResult
from browser_use.browser.context import BrowserContext

logger = logging.getLogger(__name__)

class FilterJobsByLocation(BaseModel):
    """Filter job listings to focus on a specific location."""
    action_type: str = "filter_jobs_by_location"
    location: str = Field(
        description="Target location to filter jobs by (e.g., 'Houston, TX')"
    )
    platform: str = Field(
        default="linkedin",
        description="The job platform being used (e.g., 'linkedin', 'indeed')"
    )

async def filter_jobs_by_location(action: FilterJobsByLocation, browser: BrowserContext) -> ActionResult:
    """
    Helps filter job listings to focus on jobs in a specific location.
    """
    try:
        page = await browser.get_page()
        location = action.location
        platform = action.platform.lower()
        
        if platform == "linkedin":
            # Check if we're on a search results page
            if "jobs" in await page.url():
                # Look for location filter input
                location_input = await page.query_selector("input[aria-label*='location' i], input[placeholder*='location' i], input[id*='location' i]")
                
                if location_input:
                    # Clear existing location
                    await location_input.click()
                    await location_input.fill("")
                    
                    # Enter new location
                    await location_input.fill(location)
                    await page.keyboard.press("Enter")
                    
                    # Wait for results to update
                    await page.wait_for_load_state("networkidle")
                    
                    return ActionResult(
                        extracted_content=f"Successfully filtered jobs by location: {location}",
                        error=None,
                        is_done=False
                    )
                else:
                    # Try to find filters button and open location filter
                    filters_button = await page.query_selector("button:has-text('Filters'), button:has-text('All filters')")
                    if filters_button:
                        await filters_button.click()
                        await page.wait_for_timeout(1000)
                        
                        # Look for location filter in the modal
                        location_input = await page.query_selector("input[aria-label*='location' i], input[placeholder*='location' i], input[id*='location' i]")
                        if location_input:
                            await location_input.fill(location)
                            await page.keyboard.press("Enter")
                            
                            # Find and click apply button
                            apply_button = await page.query_selector("button:has-text('Apply'), button:has-text('Show results')")
                            if apply_button:
                                await apply_button.click()
                                await page.wait_for_load_state("networkidle")
                                
                                return ActionResult(
                                    extracted_content=f"Applied location filter '{location}' from filters modal",
                                    error=None,
                                    is_done=False
                                )
            
            # If we're on the job search page
            search_url = "https://www.linkedin.com/jobs/search/"
            if await page.url() == search_url or "linkedin.com/jobs" in await page.url():
                # Clear search and set it explicitly
                keyword_input = await page.query_selector("input[aria-label*='search' i], input[placeholder*='search' i], input[id*='jobs-search-box-keyword' i]")
                location_input = await page.query_selector("input[aria-label*='location' i], input[placeholder*='location' i], input[id*='jobs-search-box-location' i]")
                
                if keyword_input and location_input:
                    await keyword_input.fill("software engineer")  # Use a default search term
                    await location_input.fill(location)
                    await page.keyboard.press("Enter")
                    
                    return ActionResult(
                        extracted_content=f"Started new job search in location: {location}",
                        error=None,
                        is_done=False
                    )
        
        return ActionResult(
            extracted_content=f"Unable to apply location filter for {location} on {platform}. Try manual filtering.",
            error=None,
            is_done=False
        )
    except Exception as e:
        return ActionResult(
            extracted_content=None,
            error=f"Error filtering jobs by location: {str(e)}",
            is_done=False
        )
