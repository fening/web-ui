import logging
from pydantic import BaseModel, Field
from browser_use.agent.views import ActionResult
from browser_use.browser.context import BrowserContext
from typing import Optional, List

logger = logging.getLogger(__name__)

class SmartFormFill(BaseModel):
    """Fill a form input by finding the actual input element instead of labels."""
    action_type: str = "smart_form_fill"
    selector: str = Field(
        description="Selector or description of the form field you want to fill"
    )
    text: str = Field(
        description="Text to input into the form field"
    )
    form_id: Optional[str] = Field(
        default=None,
        description="Optional ID of the form containing the field"
    )

async def smart_form_fill(action: SmartFormFill, browser: BrowserContext) -> ActionResult:
    """
    Intelligently fills a form field by finding the actual input element
    even when a label or other non-input element was initially selected.
    """
    try:
        page = await browser.get_page()
        
        # First, try to find the specified element
        element = await browser.find_element(action.selector)
        
        if not element:
            return ActionResult(
                extracted_content=None,
                error=f"Could not find element matching '{action.selector}'",
                is_done=False
            )
        
        # Check if the element is a label
        tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
        
        if tag_name == "label":
            logger.info(f"Selected element is a label, looking for associated input")
            
            # Try to get the for attribute
            for_id = await element.evaluate("el => el.getAttribute('for')")
            
            if for_id:
                logger.info(f"Label points to element with id: {for_id}")
                # Find the actual input element
                input_element = await page.query_selector(f"#{for_id}")
                
                if input_element:
                    logger.info(f"Found associated input element")
                    element = input_element
                else:
                    logger.info(f"No element found with id '{for_id}', trying fallback methods")
            
            # If no for attribute or couldn't find input, try to find inputs nearby
            if tag_name == "label":
                # Try to find an input element that's a sibling or child
                input_element = await element.evaluate("""
                    label => {
                        // Check for an input following the label
                        let el = label.nextElementSibling;
                        if (el && (el.tagName === 'INPUT' || el.tagName === 'SELECT' || el.tagName === 'TEXTAREA')) {
                            return el;
                        }
                        
                        // Check for an input inside the label
                        el = label.querySelector('input, select, textarea');
                        if (el) return el;
                        
                        // Check for an input in the same form group/container
                        let container = label.parentElement;
                        if (container) {
                            el = container.querySelector('input, select, textarea');
                            if (el) return el;
                        }
                        
                        return null;
                    }
                """)
                
                if input_element:
                    logger.info(f"Found related input element via DOM traversal")
                    element = input_element
        
        # Check if we now have a valid input element
        if element:
            # Determine the best approach to set the value based on the element type
            await element.evaluate(f"""
                el => {{
                    const tag = el.tagName.toLowerCase();
                    const type = el.type && el.type.toLowerCase();
                    
                    if (tag === 'input' || tag === 'textarea') {{
                        el.value = "{action.text}";
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }} else if (tag === 'select') {{
                        const options = Array.from(el.options);
                        const valueToSelect = "{action.text}";
                        
                        // Try to match by text or value
                        const matchingOption = options.find(o => 
                            o.text.includes(valueToSelect) || 
                            o.value.includes(valueToSelect)
                        );
                        
                        if (matchingOption) {{
                            el.value = matchingOption.value;
                        }} else {{
                            // If no match, just set the value directly
                            el.value = valueToSelect;
                        }}
                        
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                }}
            """)
            
            # Now try to fill it properly using native methods
            try:
                await element.fill(action.text)
            except:
                # If native fill fails, we already used JS as a fallback
                pass
                
            return ActionResult(
                extracted_content=f"Successfully filled form field with text: {action.text}",
                error=None,
                is_done=False
            )
        else:
            return ActionResult(
                extracted_content=None,
                error=f"Could not find a fillable input element related to '{action.selector}'",
                is_done=False
            )
            
    except Exception as e:
        return ActionResult(
            extracted_content=None,
            error=f"Error filling form input: {str(e)}",
            is_done=False
        )
