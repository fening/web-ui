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
from .location_helper_action import FilterJobsByLocation, filter_jobs_by_location
from .smart_form_action import SmartFormFill, smart_form_fill
from .smart_element_action import SmartElementSelector, smart_element_select
from .dropdown_select_action import SelectDropdownOption, select_dropdown_option
from .model_registry import CustomModelRegistry
from .action_converter import ActionConverter

logger = logging.getLogger(__name__)

class CustomController(Controller):
    def __init__(self):
        super().__init__()
        self.model_registry = CustomModelRegistry()
        self._register_custom_actions()
        self._register_scroll_action()
        self._register_smart_form_actions()
        self._register_models()

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

    def _register_smart_form_actions(self):
        """Register smart form interaction actions"""
        
        @self.registry.action("smart_form_fill", requires_browser=True)
        async def smart_form_fill_action(params: SmartFormFill, browser: BrowserContext):
            """Fill a form field intelligently by handling labels and complex form structures"""
            return await smart_form_fill(params, browser)

    def _register_models(self):
        """Register custom models with the model registry."""
        # Register form-related models
        self.model_registry.register_model("smart_form_fill", SmartFormFill)
        self.model_registry.register_model("smart_element_select", SmartElementSelector)
        self.model_registry.register_model("select_dropdown_option", SelectDropdownOption)
        self.model_registry.register_model("filter_jobs_by_location", FilterJobsByLocation)
        self.model_registry.register_model("scroll_action", ScrollAction)
        
        # Register any converters between models if needed
        # For example, converting between framework actions and our custom actions
        self.model_registry.register_converter(
            "input_text", 
            "smart_form_fill", 
            lambda input_text_action: SmartFormFill(
                selector=input_text_action.selector,
                text=input_text_action.text
            )
        )
        
        # Register scroll action converter
        self.model_registry.register_converter(
            "scroll", 
            "scroll_action", 
            lambda scroll_action: ScrollAction(
                direction=scroll_action.direction,
                amount=scroll_action.amount
            )
        )
        
        logger.info(f"Registered models: {list(self.model_registry.models.keys())}")
