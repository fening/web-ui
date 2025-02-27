import logging
from pydantic import BaseModel, Field
from typing import Optional, List
from browser_use.agent.views import ActionResult
from browser_use.browser.context import BrowserContext

logger = logging.getLogger(__name__)

class SelectDropdownOption(BaseModel):
    """Select an option from a dropdown/select element."""
    action_type: str = "select_dropdown_option"
    selector: str = Field(
        description="Selector or description of the dropdown element"
    )
    option_text: str = Field(
        description="Text of the option to select (will try to match text content)"
    )
    option_value: Optional[str] = Field(
        default=None,
        description="Value of the option to select (if known, more precise than text)"
    )
    option_index: Optional[int] = Field(
        default=None,
        description="Index of the option to select (0-based, if known)"
    )

async def select_dropdown_option(action: SelectDropdownOption, browser: BrowserContext) -> ActionResult:
    """
    Intelligently select an option from a dropdown/select element.
    Works with both native <select> elements and custom dropdowns.
    """
    try:
        page = await browser.get_page()
        
        # First, find the dropdown element
        element = await browser.find_element(action.selector)
        
        if not element:
            return ActionResult(
                extracted_content=None,
                error=f"Could not find dropdown element with selector '{action.selector}'",
                is_done=False
            )
        
        # Check if it's a native <select> element
        tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
        
        if tag_name == "select":
            # Handle native <select> element
            logger.info("Found native <select> element")
            
            if action.option_index is not None:
                # Select by index if provided
                option_count = await element.evaluate("el => el.options.length")
                
                if action.option_index >= 0 and action.option_index < option_count:
                    option_text = await element.evaluate(f"el => el.options[{action.option_index}].text")
                    await element.select_option(index=action.option_index)
                    
                    return ActionResult(
                        extracted_content=f"Selected option '{option_text}' by index {action.option_index}",
                        error=None,
                        is_done=False
                    )
                else:
                    return ActionResult(
                        extracted_content=None,
                        error=f"Option index {action.option_index} is out of range (0-{option_count-1})",
                        is_done=False
                    )
            
            elif action.option_value is not None:
                # Select by value if provided
                await element.select_option(value=action.option_value)
                return ActionResult(
                    extracted_content=f"Selected option with value '{action.option_value}'",
                    error=None,
                    is_done=False
                )
                
            else:
                # Select by text (most common case)
                # First try exact match
                options = await element.evaluate("""el => {
                    return Array.from(el.options).map(opt => ({
                        text: opt.text.trim(),
                        value: opt.value
                    }));
                }""")
                
                # Try to find the best match for the option
                best_match = None
                for i, option in enumerate(options):
                    if action.option_text.lower() == option['text'].lower():
                        # Exact match (case insensitive)
                        best_match = i
                        break
                    elif option['text'].lower().includes(action.option_text.lower()):
                        # Partial match
                        best_match = i
                
                if best_match is not None:
                    # Select the option
                    await element.select_option(index=best_match)
                    return ActionResult(
                        extracted_content=f"Selected option '{options[best_match]['text']}' matching '{action.option_text}'",
                        error=None,
                        is_done=False
                    )
                else:
                    # Try a different approach with evaluate
                    success = await element.evaluate(f"""el => {{
                        const targetText = "{action.option_text.replace('"', '\\"')}".toLowerCase();
                        for (let i = 0; i < el.options.length; i++) {{
                            const option = el.options[i];
                            if (option.text.toLowerCase().includes(targetText)) {{
                                option.selected = true;
                                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                return true;
                            }}
                        }}
                        return false;
                    }}""")
                    
                    if success:
                        return ActionResult(
                            extracted_content=f"Selected option containing '{action.option_text}'",
                            error=None,
                            is_done=False
                        )
                    else:
                        return ActionResult(
                            extracted_content=None,
                            error=f"Could not find option matching '{action.option_text}'",
                            is_done=False
                        )
        
        else:
            # Handle custom dropdown (not a native <select>)
            logger.info(f"Found custom dropdown element ({tag_name})")
            
            # First, check if it's a common framework dropdown
            aria_expanded = await element.evaluate("el => el.getAttribute('aria-expanded')") 
            
            # Click to open the dropdown if it's not already expanded
            if aria_expanded == "false" or aria_expanded is None:
                await element.click()
                # Wait a moment for dropdown to appear
                await page.wait_for_timeout(500)
            
            # Try to find the dropdown list - common patterns
            dropdown_containers = [
                # Same container as the clicked element
                element,
                # Next sibling
                await page.evaluate_handle("el => el.nextElementSibling", element),
                # Parent's next sibling
                await page.evaluate_handle("el => el.parentElement.nextElementSibling", element),
                # Closest dropdown container
                await page.evaluate_handle("el => el.closest('.dropdown, [role=listbox], [role=combobox]')", element),
                # Check for recently appeared elements with common dropdown classes
                await page.query_selector(".dropdown-menu, .select-options, .listbox, .menu, [role=listbox]:visible")
            ]
            
            # Try to find the option
            option_found = False
            option_element = None
            
            # Common option selectors to try
            option_selectors = [
                f"li:has-text('{action.option_text}')",
                f"div:has-text('{action.option_text}')",
                f"[role='option']:has-text('{action.option_text}')",
                f"[data-value='{action.option_value or action.option_text}']",
                f"option:has-text('{action.option_text}')"
            ]
            
            # Try each container with each selector
            for container in dropdown_containers:
                if not container or container.is_empty():
                    continue
                    
                for selector in option_selectors:
                    try:
                        option_element = await container.query_selector(selector)
                        if option_element:
                            # Found our option
                            option_found = True
                            await option_element.click()
                            
                            return ActionResult(
                                extracted_content=f"Clicked option '{action.option_text}' in custom dropdown",
                                error=None,
                                is_done=False
                            )
                    except Exception as e:
                        logger.debug(f"Error trying selector {selector}: {e}")
                        continue
            
            if not option_found:
                # Last resort: Try to find any elements that appeared after clicking
                # and may contain our text
                try:
                    await page.wait_for_selector(f"text/{action.option_text}", timeout=1000)
                    matching_element = await page.query_selector(f"text/{action.option_text}")
                    if matching_element:
                        await matching_element.click()
                        return ActionResult(
                            extracted_content=f"Found and clicked text '{action.option_text}' after opening dropdown",
                            error=None,
                            is_done=False
                        )
                except:
                    pass
                    
                return ActionResult(
                    extracted_content=None,
                    error=f"Could not find option '{action.option_text}' in the dropdown",
                    is_done=False
                )
            
    except Exception as e:
        logger.error(f"Error in dropdown selection: {str(e)}")
        return ActionResult(
            extracted_content=None,
            error=f"Error selecting dropdown option: {str(e)}",
            is_done=False
        )
