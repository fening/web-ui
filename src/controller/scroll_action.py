# -*- coding: utf-8 -*-

import logging
from typing import Optional, Literal
from pydantic import BaseModel, Field

# Try importing from registry
from browser_use.controller.registry import register_action
from browser_use.browser.context import BrowserContext
from browser_use.agent.views import ActionResult

logger = logging.getLogger(__name__)

class ScrollAction(BaseModel):
    """Scroll the page up or down by a specified amount."""
    direction: Literal["down", "up"] = Field(
        default="down",
        description="Direction to scroll. 'down' to scroll down, 'up' to scroll up."
    )
    amount: int = Field(
        default=500,
        description="Amount to scroll in pixels. Positive number."
    )

@register_action(
    name="scroll",
    description="Scroll the page up or down by a specified amount",
    required_browser=True,
    model=ScrollAction,
)
async def scroll(
    scroll_action: ScrollAction, browser_context: BrowserContext
) -> ActionResult:
    """
    Scroll the page up or down.

    Args:
        scroll_action: The scroll action parameters.
        browser_context: The browser context.

    Returns:
        ActionResult: The result of the action.
    """
    try:
        direction_multiplier = 1 if scroll_action.direction == "down" else -1
        scroll_amount = direction_multiplier * abs(scroll_action.amount)

        page = await browser_context.get_page()
        await page.evaluate(f"window.scrollBy(0, {scroll_amount})")

        return ActionResult(
            extracted_content=f"Scrolled {scroll_action.direction} by {abs(scroll_amount)} pixels",
            error=None,
            is_done=False,
        )
    except Exception as e:
        error_message = f"Failed to scroll: {str(e)}"
        logger.error(error_message)
        return ActionResult(
            extracted_content=None,
            error=error_message,
            is_done=False,
        )