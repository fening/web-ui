# -*- coding: utf-8 -*-
# @Time    : 2025/1/2
# @Author  : wenshao
# @ProjectName: browser-use-webui
# @FileName: custom_action.py

import logging
import pyperclip
from pydantic import BaseModel, Field
from browser_use.agent.views import ActionResult
from browser_use.browser.context import BrowserContext
from browser_use.controller.service import Controller
from typing import Literal
from .custom_scroll_action import ScrollAction, scroll

logger = logging.getLogger(__name__)

class CustomController(Controller):
    def __init__(self):
        super().__init__()
        self._register_custom_actions()
        self._register_scroll_action()

    def _register_custom_actions(self):
        """Register all custom browser actions"""

        @self.registry.action("Copy text to clipboard")
        def copy_to_clipboard(text: str):
            pyperclip.copy(text)
            return ActionResult(extracted_content=text)

        @self.registry.action("Paste text from clipboard", requires_browser=True)
        async def paste_from_clipboard(browser: BrowserContext):
            text = pyperclip.paste()
            # send text to browser
            page = await browser.get_current_page()
            await page.keyboard.type(text)

            return ActionResult(extracted_content=text)

    def _register_scroll_action(self):
        """Register the scroll action with the registry"""
        
        # First define a model class for the action parameters
        class ScrollParams(BaseModel):
            direction: Literal["down", "up"] = Field(
                default="down",
                description="Direction to scroll. 'down' to scroll down, 'up' to scroll up."
            )
            amount: int = Field(
                default=500,
                description="Amount to scroll in pixels. Positive number."
            )
        
        # Then register the action with the correct format
        # Fix: Change parameter name from browser_context to browser to match framework expectation
        @self.registry.action("scroll_action", requires_browser=True, param_model=ScrollParams)
        async def scroll_action(params: ScrollParams, browser: BrowserContext):  # Changed from browser_context to browser
            """Scroll the page up or down by a specified amount."""
            try:
                direction_multiplier = 1 if params.direction == "down" else -1
                scroll_amount = direction_multiplier * abs(params.amount)
                
                page = await browser.get_page()  # Use browser instead of browser_context
                await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
                
                return ActionResult(
                    extracted_content=f"Scrolled {params.direction} by {abs(scroll_amount)} pixels",
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
