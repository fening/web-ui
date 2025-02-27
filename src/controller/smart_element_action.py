import logging
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from browser_use.agent.views import ActionResult
from browser_use.browser.context import BrowserContext

logger = logging.getLogger(__name__)

class SmartElementSelector(BaseModel):
    """Intelligently select an element on the page using flexible matching strategies."""
    action_type: str = "smart_element_select"
    description: str = Field(
        description="Describe what element you're looking for (e.g., 'submit button', 'phone number field')"
    )
    purpose: str = Field(
        description="What you intend to do with this element (e.g., 'click', 'input text', 'check if present')"
    )
    text_content: Optional[str] = Field(
        default=None,
        description="Text content that should be in or near the element"
    )
    element_type: Optional[str] = Field(
        default=None,
        description="Type of element if known (e.g., 'button', 'input', 'select', 'a')"
    )
    location: Optional[str] = Field(
        default=None,
        description="General location on the page (e.g., 'header', 'footer', 'sidebar', 'main content')"
    )
    fallback_selector: Optional[str] = Field(
        default=None,
        description="CSS selector to try if smart selection fails"
    )

async def smart_element_select(action: SmartElementSelector, browser: BrowserContext) -> ActionResult:
    """
    Intelligently finds the most likely element based on natural language description
    and returns information about it for future interaction.
    """
    try:
        page = await browser.get_page()
        
        # Build selectors based on provided information
        selectors = []
        
        # Use element type if provided
        if action.element_type:
            elem_type = action.element_type.lower()
            
            # Handle special cases for common element types
            if elem_type == 'button':
                selectors.append("button")
                selectors.append("input[type='button']")
                selectors.append("input[type='submit']")
                selectors.append("[role='button']")
                selectors.append(".btn")
                selectors.append(".button")
            elif elem_type == 'input' or elem_type == 'text field' or elem_type == 'textbox':
                selectors.append("input:not([type='button']):not([type='submit']):not([type='checkbox']):not([type='radio'])")
                selectors.append("textarea")
                selectors.append("[contenteditable='true']")
            elif elem_type == 'dropdown' or elem_type == 'select':
                selectors.append("select")
                selectors.append("[role='combobox']")
                selectors.append("[role='listbox']")
            else:
                # Generic element type
                selectors.append(elem_type)
        
        # Add text-based selectors if text content was provided
        if action.text_content:
            text = action.text_content.replace("'", "\\'").replace('"', '\\"')
            
            # Text exactly matches
            selectors.append(f"text='{text}'")
            selectors.append(f"[placeholder='{text}']")
            selectors.append(f"[aria-label='{text}']")
            selectors.append(f"[alt='{text}']")
            
            # Text contains
            selectors.append(f"text='{text}'")
            selectors.append(f"[placeholder*='{text}']")
            selectors.append(f"[aria-label*='{text}']")
            
            # Use description text to find labels that might be associated with form fields
            if "field" in action.description or "input" in action.description:
                selectors.append(f"label:has-text('{text}')") 
                selectors.append(f"input[id=id-of-label:has-text('{text}')]")
        
        # If looking for something based on natural language description
        description_keywords = action.description.lower().split()
        purpose = action.purpose.lower()
        
        # Try to match based on purpose
        if 'click' in purpose and not action.element_type:
            selectors.append("button")
            selectors.append("a")
            selectors.append("[role='button']")
            selectors.append("input[type='button']")
            selectors.append("input[type='submit']")
        
        # Add fallback selector if provided
        if action.fallback_selector:
            selectors.append(action.fallback_selector)
            
        # Try each selector until we find a match
        found_element = None
        selector_used = None
        
        logger.info(f"Trying smart selectors for '{action.description}'")
        for selector in selectors:
            try:
                # Check if element exists
                elements = await page.query_selector_all(selector)
                if elements and len(elements) > 0:
                    # If multiple elements match, try to find the most relevant one
                    if len(elements) > 1:
                        # For multiple matches, try to narrow down by:
                        # 1. Visibility
                        # 2. Enabled state (for form controls)
                        # 3. Position on page (higher = more important)
                        
                        # Evaluate each element
                        element_scores = []
                        
                        for i, elem in enumerate(elements):
                            # Default score starts at 0
                            score = 0
                            
                            # Check if visible
                            is_visible = await elem.is_visible()
                            if is_visible:
                                score += 10
                            else:
                                score -= 5
                                
                            # Check if enabled (for inputs)
                            tag_name = await elem.evaluate("e => e.tagName.toLowerCase()")
                            if tag_name in ['input', 'button', 'select', 'textarea']:
                                is_disabled = await elem.evaluate("e => e.disabled === true")
                                if not is_disabled:
                                    score += 5
                                else:
                                    score -= 3
                            
                            # Check position (elements higher on the page score better)
                            box = await elem.bounding_box()
                            if box:
                                # Higher elements are more important, but not too high (might be headers)
                                if box['y'] < 100:
                                    score += 2
                                elif box['y'] < 300:
                                    score += 3
                                else:
                                    score += 1
                                    
                            # Check size - very small elements are less likely to be important
                            if box and (box['width'] < 5 or box['height'] < 5):
                                score -= 2
                                
                            # Add to scores
                            element_scores.append((score, i, elem))
                        
                        # Sort by score (descending)
                        element_scores.sort(reverse=True)
                        
                        # Take the highest scoring element
                        if element_scores:
                            found_element = element_scores[0][2]
                            selector_used = selector
                            break
                    else:
                        # Just one element found
                        found_element = elements[0]
                        selector_used = selector
                        break
            except Exception as e:
                logger.debug(f"Selector '{selector}' failed: {str(e)}")
                continue
                
        if found_element:
            # Get information about the element
            tag_name = await found_element.evaluate("e => e.tagName.toLowerCase()")
            element_id = await found_element.evaluate("e => e.id || ''")
            element_class = await found_element.evaluate("e => e.className || ''")
            element_type = await found_element.evaluate("e => e.type || ''")
            
            # Get text content if applicable
            try:
                text_content = await found_element.text_content() or ""
                text_content = text_content.strip()
            except:
                text_content = ""
                
            # Create a selector that can reliably find this element again
            unique_selector = await found_element.evaluate("""e => {
                // Try to create a selector based on ID
                if (e.id) {
                    return `#${e.id}`;
                }
                
                // Try to create a selector based on unique classes
                if (e.className) {
                    const classes = e.className.split(' ').filter(c => c && c.trim());
                    if (classes.length > 0) {
                        const selector = `.${classes.join('.')}`;
                        // Check if this uniquely selects our element
                        if (document.querySelectorAll(selector).length === 1) {
                            return selector;
                        }
                    }
                }
                
                // Try to create a selector based on element attributes
                for (const attr of ['name', 'placeholder', 'value', 'aria-label']) {
                    if (e.hasAttribute(attr)) {
                        const val = e.getAttribute(attr);
                        if (val) {
                            const selector = `${e.tagName.toLowerCase()}[${attr}="${val.replace(/"/g, '\\"')}"]`;
                            if (document.querySelectorAll(selector).length === 1) {
                                return selector;
                            }
                        }
                    }
                }
                
                // Fallback to a full path selector
                let path = '';
                let element = e;
                while (element && element.nodeType === 1) {
                    let selector = element.tagName.toLowerCase();
                    if (element.id) {
                        selector += `#${element.id}`;
                        path = selector + (path ? ' > ' + path : '');
                        break;
                    } else {
                        let siblings = Array.from(element.parentNode?.children || []);
                        if (siblings.length > 1) {
                            let index = siblings.indexOf(element) + 1;
                            if (index > 0) {
                                selector += `:nth-child(${index})`;
                            }
                        }
                    }
                    path = selector + (path ? ' > ' + path : '');
                    element = element.parentElement;
                }
                
                return path;
            }""")
            
            # Prepare result
            result = {
                "element_found": True,
                "selector": unique_selector,
                "original_selector": selector_used,
                "tag_name": tag_name,
                "id": element_id,
                "class": element_class,
                "type": element_type,
                "text": text_content[:100] if len(text_content) > 100 else text_content
            }
            
            return ActionResult(
                extracted_content=f"Element found: {result}",
                error=None,
                is_done=False,
                metadata=result
            )
        else:
            # No element found with any selector
            return ActionResult(
                extracted_content=None,
                error=f"Could not find an element matching '{action.description}'",
                is_done=False,
                metadata={"element_found": False}
            )
            
    except Exception as e:
        logger.error(f"Error in smart element select: {str(e)}")
        return ActionResult(
            extracted_content=None,
            error=f"Error selecting element: {str(e)}",
            is_done=False,
            metadata={"element_found": False, "error": str(e)}
        )
