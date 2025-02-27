# -*- coding: utf-8 -*-
# @Time    : 2025/1/2
# @Author  : wenshao
# @ProjectName: browser-use-webui
# @FileName: custom_agent.py

import json
import logging
import pdb
import traceback
from typing import Optional, Type
from PIL import Image, ImageDraw, ImageFont
import os
import base64
import io
import uuid

from browser_use.agent.prompts import SystemPrompt
from browser_use.agent.service import Agent
from browser_use.agent.views import (
    ActionResult,
    AgentHistoryList,
    AgentOutput,
    AgentHistory,
)
from browser_use.browser.browser import Browser
from browser_use.browser.context import BrowserContext
from browser_use.browser.views import BrowserStateHistory
from browser_use.controller.service import Controller
from browser_use.telemetry.views import (
    AgentEndTelemetryEvent,
    AgentRunTelemetryEvent,
    AgentStepErrorTelemetryEvent,
)
from browser_use.utils import time_execution_async
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    BaseMessage,
)
from src.utils.agent_state import AgentState
from src.utils.agent_interaction import (
    interaction_manager, 
    InteractionRequest, 
    InteractionResponse,
    InteractionType
)
from src.utils.terminal_interaction import terminal_handler

from .custom_massage_manager import CustomMassageManager
from .custom_views import CustomAgentOutput, CustomAgentStepInfo

logger = logging.getLogger(__name__)


class CustomAgent(Agent):
    def __init__(
            self,
            task: str,
            llm: BaseChatModel,
            add_infos: str = "",
            browser: Browser | None = None,
            browser_context: BrowserContext | None = None,
            controller: Controller = Controller(),
            use_vision: bool = True,
            save_conversation_path: Optional[str] = None,
            max_failures: int = 5,
            retry_delay: int = 10,
            system_prompt_class: Type[SystemPrompt] = SystemPrompt,
            max_input_tokens: int = 128000,
            validate_output: bool = False,
            include_attributes: list[str] = [
                "title",
                "type",
                "name",
                "role",
                "tabindex",
                "aria-label",
                "placeholder",
                "value",
                "alt",
                "aria-expanded",
            ],
            max_error_length: int = 400,
            max_actions_per_step: int = 10,
            tool_call_in_content: bool = True,
            agent_state: AgentState = None,
            ensure_full_page_exploration: bool = True,  # Add this parameter
            enable_user_interaction: bool = True,  # Add this parameter
    ):
        super().__init__(
            task=task,
            llm=llm,
            browser=browser,
            browser_context=browser_context,
            controller=controller,
            use_vision=use_vision,
            save_conversation_path=save_conversation_path,
            max_failures=max_failures,
            retry_delay=retry_delay,
            system_prompt_class=system_prompt_class,
            max_input_tokens=max_input_tokens,
            validate_output=validate_output,
            include_attributes=include_attributes,
            max_error_length=max_error_length,
            max_actions_per_step=max_actions_per_step,
            tool_call_in_content=tool_call_in_content,
        )
        self.add_infos = add_infos
        self.agent_state = agent_state
        self.message_manager = CustomMassageManager(
            llm=self.llm,
            task=self.task,
            action_descriptions=self.controller.registry.get_prompt_description(),
            system_prompt_class=self.system_prompt_class,
            max_input_tokens=self.max_input_tokens,
            include_attributes=self.include_attributes,
            max_error_length=self.max_error_length,
            max_actions_per_step=self.max_actions_per_step,
            tool_call_in_content=tool_call_in_content,
        )
        self.ensure_full_page_exploration = ensure_full_page_exploration
        self.page_fully_scrolled = False
        self.last_page_url = None
        self.scroll_attempts = 0
        self.max_scroll_attempts = 5  # Maximum number of scroll attempts per page
        self.enable_user_interaction = enable_user_interaction
        self.waiting_for_user_input = False

    def _setup_action_models(self) -> None:
        """Setup dynamic action models from controller's registry"""
        # Get the dynamic action model from controller's registry
        self.ActionModel = self.controller.registry.create_action_model()
        # Create output model with the dynamic actions
        self.AgentOutput = CustomAgentOutput.type_with_custom_actions(self.ActionModel)

    def _log_response(self, response: CustomAgentOutput) -> None:
        """Log the model's response"""
        if "Success" in response.current_state.prev_action_evaluation:
            emoji = "✅"
        elif "Failed" in response.current_state.prev_action_evaluation:
            emoji = "❌"
        else:
            emoji = "🤷"

        logger.info(f"{emoji} Eval: {response.current_state.prev_action_evaluation}")
        logger.info(f"🧠 New Memory: {response.current_state.important_contents}")
        logger.info(f"⏳ Task Progress: {response.current_state.completed_contents}")
        logger.info(f"🤔 Thought: {response.current_state.thought}")
        logger.info(f"🎯 Summary: {response.current_state.summary}")
        for i, action in enumerate(response.action):
            logger.info(
                f"🛠️  Action {i + 1}/{len(response.action)}: {action.model_dump_json(exclude_unset=True)}"
            )

    def update_step_info(
            self, model_output: CustomAgentOutput, step_info: CustomAgentStepInfo = None
    ):
        """
        update step info
        """
        if step_info is None:
            return

        step_info.step_number += 1
        important_contents = model_output.current_state.important_contents
        if (
                important_contents
                and "None" not in important_contents
                and important_contents not in step_info.memory
        ):
            step_info.memory += important_contents + "\n"

        completed_contents = model_output.current_state.completed_contents
        if completed_contents and "None" not in completed_contents:
            step_info.task_progress = completed_contents

    @time_execution_async("--get_next_action")
    async def get_next_action(self, input_messages: list[BaseMessage]) -> AgentOutput:
        """Get next action from LLM based on current state"""
        try:
            structured_llm = self.llm.with_structured_output(self.AgentOutput, include_raw=True)
            response: dict[str, Any] = await structured_llm.ainvoke(input_messages)  # type: ignore

            parsed: AgentOutput = response['parsed']
            # cut the number of actions to max_actions_per_step
            parsed.action = parsed.action[: self.max_actions_per_step]
            self._log_response(parsed)
            self.n_steps += 1

            return parsed
        except Exception as e:
            # If something goes wrong, try to invoke the LLM again without structured output,
            # and Manually parse the response. Temporarily solution for DeepSeek
            ret = self.llm.invoke(input_messages)
            if isinstance(ret.content, list):
                parsed_json = json.loads(ret.content[0].replace("```json", "").replace("```", ""))
            else:
                parsed_json = json.loads(ret.content.replace("```json", "").replace("```", ""))
            parsed: AgentOutput = self.AgentOutput(**parsed_json)
            if parsed is None:
                raise ValueError(f'Could not parse response.')

            # cut the number of actions to max_actions_per_step
            parsed.action = parsed.action[: self.max_actions_per_step]
            self._log_response(parsed)
            self.n_steps += 1

            return parsed

    @time_execution_async("--step")
    async def step(self, step_info: Optional[CustomAgentStepInfo] = None) -> None:
        """Execute one step of the task"""
        logger.info(f"\n📍 Step {self.n_steps}")
        state = None
        model_output = None
        result: list[ActionResult] = []

        try:
            state = await self.browser_context.get_state(use_vision=self.use_vision)
            
            # Check if we've changed pages - reset scroll state if so
            if state and self.last_page_url != state.url:
                logger.info(f"🌐 New page detected: {state.url}")
                self.last_page_url = state.url
                self.page_fully_scrolled = False
                self.scroll_attempts = 0
            
            # If we're enforcing full page exploration and haven't fully scrolled yet
            if (self.ensure_full_page_exploration and 
                not self.page_fully_scrolled and 
                self.scroll_attempts < self.max_scroll_attempts):
                
                # Add a stronger hint about scrolling
                if step_info and hasattr(step_info, "memory"):
                    step_info.memory += "IMPORTANT: You should scroll down to explore the ENTIRE page before making decisions or navigating away. This ensures you don't miss crucial information.\n"
                    logger.info("📜 Encouraging full page exploration before navigation")
            
            # Add a hint about scrolling if this is the first time seeing search results
            if state and "search" in state.url.lower() and self.n_steps <= 3:
                logger.info("🔍 On a search results page - consider scrolling to see more results")
                if step_info and hasattr(step_info, "memory"):
                    step_info.memory += "Remember: Search results often continue below the visible area. Consider scrolling down to see all results.\n"
            
            self.message_manager.add_state_message(state, self._last_result, step_info)
            input_messages = self.message_manager.get_messages()
            model_output = await self.get_next_action(input_messages)
            self.update_step_info(model_output, step_info)
            logger.info(f"🧠 All Memory: {step_info.memory}")
            self._save_conversation(input_messages, model_output)
            self.message_manager._remove_last_state_message()
            self.message_manager.add_model_output(model_output)

            # Add special logging for scroll actions
            for action in model_output.action:
                if hasattr(action, "action_type") and action.action_type == "scroll":
                    logger.info(f"📜 Scrolling {action.direction} by {action.amount} pixels")

            # Check for navigation actions
            navigation_action_found = False
            for action in model_output.action:
                action_type = getattr(action, "action_type", "")
                if action_type in ["go_to_url", "open_tab", "click_element"]:
                    navigation_action_found = True
                    
                    # If trying to navigate but haven't fully explored the page
                    if self.ensure_full_page_exploration and not self.page_fully_scrolled:
                        if self.scroll_attempts < self.max_scroll_attempts:
                            logger.info(f"⚠️ Navigation attempted before full page exploration (attempt {self.scroll_attempts + 1}/{self.max_scroll_attempts})")
                            
                            # Force a scroll action instead of navigation
                            result: list[ActionResult] = await self._force_page_scroll(state)
                            self.scroll_attempts += 1
                            
                            # After reaching max scroll attempts, consider the page fully scrolled
                            if self.scroll_attempts >= self.max_scroll_attempts:
                                logger.info("📋 Page considered fully explored after max scroll attempts")
                                self.page_fully_scrolled = True
                                
                            # Skip the regular action execution
                            self._last_result = result
                            return
            
            # If no navigation actions and we're scrolling, count this as a scroll attempt
            if not navigation_action_found:
                for action in model_output.action:
                    action_type = getattr(action, "action_type", "")
                    if action_type == "scroll" or action_type == "scroll_action":
                        self.scroll_attempts += 1
                        if self.scroll_attempts >= self.max_scroll_attempts:
                            logger.info("📋 Page considered fully explored after multiple scrolls")
                            self.page_fully_scrolled = True
            
            # Add processing for login detection
            if state and model_output:
                # Check if this looks like a login page and we might need user help
                if await self._should_request_login_help(state, model_output):
                    service_name = self._identify_service(state)
                    login_successful = await self.request_login(state.url, service_name)
                    
                    if login_successful:
                        # Get updated state after user login
                        state = await self.browser_context.get_state(use_vision=self.use_vision)
                        # Skip the originally planned actions and proceed with new state
                        self._last_result = [ActionResult(
                            extracted_content=f"User completed login to {service_name}",
                            error=None,
                            is_done=False
                        )]
                        return

            # Execute the planned actions
            result: list[ActionResult] = await self.controller.multi_act(
                model_output.action, self.browser_context
            )
            self._last_result = result

            if len(result) > 0 and result[-1].is_done:
                logger.info(f"📄 Result: {result[-1].extracted_content}")

            self.consecutive_failures = 0

        except Exception as e:
            result = self._handle_step_error(e)
            self._last_result = result

        finally:
            if not result:
                return
            for r in result:
                if r.error:
                    self.telemetry.capture(
                        AgentStepErrorTelemetryEvent(
                            agent_id=self.agent_id,
                            error=r.error,
                        )
                    )
            if state:
                self._make_history_item(model_output, state, result)

    async def _force_page_scroll(self, state) -> list[ActionResult]:
        """Force a page scroll when full page exploration is needed"""
        logger.info("🔄 Forcing page scroll to ensure full exploration")
        
        try:
            page = await self.browser_context.get_page()
            
            # Get current scroll position and page height
            scroll_info = await page.evaluate("""
                () => {
                    return {
                        scrollHeight: document.documentElement.scrollHeight,
                        scrollTop: document.documentElement.scrollTop,
                        clientHeight: document.documentElement.clientHeight
                    }
                }
            """)
            
            # Calculate how much to scroll (about one viewport)
            scroll_amount = scroll_info['clientHeight'] - 100
            
            # Check if we're near the bottom of the page
            near_bottom = (scroll_info['scrollTop'] + scroll_info['clientHeight'] + 200) >= scroll_info['scrollHeight']
            
            if near_bottom:
                # We're at the bottom, mark as fully scrolled
                self.page_fully_scrolled = True
                logger.info("📋 Reached bottom of page, marking as fully explored")
                return [ActionResult(
                    extracted_content="Finished exploring the page - reached the bottom",
                    error=None,
                    is_done=False
                )]
            else:
                # Scroll down
                await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
                return [ActionResult(
                    extracted_content=f"Scrolled down by {scroll_amount} pixels to explore more of the page",
                    error=None,
                    is_done=False
                )]
                
        except Exception as e:
            logger.error(f"Error during forced scroll: {e}")
            return [ActionResult(
                extracted_content=None,
                error=f"Failed to scroll: {str(e)}",
                is_done=False
            )]

    async def request_user_help(
        self, 
        prompt: str, 
        description: str = "", 
        interaction_type: InteractionType = InteractionType.TEXT_INPUT,
        options: list = None,
        metadata: dict = None,
        required: bool = True
    ) -> InteractionResponse:
        """
        Request help from the user
        
        Args:
            prompt: The question or prompt for the user
            description: Additional details about what's needed
            interaction_type: Type of interaction needed
            options: List of options for selection interactions
            metadata: Additional data to include
            required: Whether a response is required to proceed
            
        Returns:
            User's response or None if unavailable/cancelled
        """
        if not self.enable_user_interaction:
            logger.warning("User interaction requested but feature is disabled")
            return InteractionResponse(
                request_id="disabled", 
                response=None, 
                cancelled=True
            )
        
        # Create a unique ID for this request
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        
        # Create the request object
        request = InteractionRequest(
            request_id=request_id,
            type=interaction_type,
            prompt=prompt,
            description=description,
            options=options or [],
            metadata=metadata or {},
            required=required
        )
        
        # Set state to waiting
        self.waiting_for_user_input = True
        
        # Log that we're waiting for user with clear instructions
        logger.info(f"🙋 Agent is requesting user assistance: {prompt}")
        logger.info("👉 IMPORTANT: Open http://localhost:7788/interaction_modal.html to see and respond to the request")
        
        try:
            # Wait for user response
            response = await interaction_manager.request_interaction(
                request=request,
                timeout=300  # 5 minutes timeout
            )
            
            return response
        finally:
            # Reset waiting state
            self.waiting_for_user_input = False
    
    async def request_login(self, url: str, service_name: str = "this service") -> bool:
        """Request user to perform login on a page via terminal interaction only"""
        logger.info(f"🙋 Agent needs your help: Please login to {service_name}")
        logger.info(f"👀 Check your terminal window for instructions")
        
        # Use terminal interaction only - don't try web UI since we can't integrate it properly
        try:
            successful = await terminal_handler.request_login(service_name, url)
            
            if successful:
                logger.info(f"✅ User completed login for {service_name} via terminal")
                return True
            else:
                logger.warning(f"❌ Login to {service_name} was not completed via terminal")
                return False
        except Exception as e:
            logger.error(f"Terminal interaction failed: {e}")
            return False

    async def _should_request_login_help(self, state, model_output) -> bool:
        """Determine if we should request login help based on page content"""
        # Check URL for login indicators
        lower_url = state.url.lower()
        if any(x in lower_url for x in ["login", "signin", "auth", "account"]):
            # Check thought content for login intent
            if hasattr(model_output, "current_state") and model_output.current_state:
                thought = model_output.current_state.thought.lower()
                if any(x in thought for x in ["login", "sign in", "credentials", "password"]):
                    return True
                    
        return False
        
    def _identify_service(self, state) -> str:
        """Try to identify the service name from state"""
        if not state or not state.url:
            return "this service"
            
        # Extract domain from URL
        from urllib.parse import urlparse
        domain = urlparse(state.url).netloc
        
        # Remove www. and .com/.org/etc
        if domain.startswith('www.'):
            domain = domain[4:]
            
        parts = domain.split('.')
        if parts:
            return parts[0].capitalize()
            
        return "this service"

    def create_history_gif(
            self,
            output_path: str = 'agent_history.gif',
            duration: int = 3000,
            show_goals: bool = True,
            show_task: bool = True,
            show_logo: bool = False,
            font_size: int = 40,
            title_font_size: int = 56,
            goal_font_size: int = 44,
            margin: int = 40,
            line_spacing: float = 1.5,
    ) -> None:
        """Create a GIF from the agent's history with overlaid task and goal text."""
        if not self.history.history:
            logger.warning('No history to create GIF from')
            return

        images = []
        # if history is empty or first screenshot is None, we can't create a gif
        if not self.history.history or not self.history.history[0].state.screenshot:
            logger.warning('No history or first screenshot to create GIF from')
            return

        # Try to load nicer fonts
        try:
            # Try different font options in order of preference
            font_options = ['Helvetica', 'Arial', 'DejaVuSans', 'Verdana']
            font_loaded = False
            for font_name in font_options:
                try:
                    import platform
                    if platform.system() == "Windows":
                        # Need to specify the abs font path on Windows
                        font_name = os.path.join(os.getenv("WIN_FONT_DIR", "C:\\Windows\\Fonts"), font_name + ".ttf")
                    regular_font = ImageFont.truetype(font_name, font_size)
                    title_font = ImageFont.truetype(font_name, title_font_size)
                    goal_font = ImageFont.truetype(font_name, goal_font_size)
                    font_loaded = True
                    break
                except OSError:
                    continue
            if not font_loaded:
                raise OSError('No preferred fonts found')
        except OSError:
            regular_font = ImageFont.load_default()
            title_font = ImageFont.load_default()
            goal_font = regular_font

        # Try to load logo if requested
        if show_logo:
            try:
                logo = Image.open('./static/browser-use.png')
                # Resize logo to be small (e.g., 40px height)
                logo_height = 150
                aspect_ratio = logo.width / logo.height
                logo_width = int(logo_height * aspect_ratio)
                logo = logo.resize((logo_width, logo_height), Image.Resampling.LANCZOS)
            except Exception as e:
                logger.warning(f'Could not load logo: {e}')
                logo = None
        else:
            logo = None

        # Create task frame if requested
        if show_task and self.task:
            task_frame = self._create_task_frame(
                self.task,
                self.history.history[0].state.screenshot,
                title_font,
                regular_font,
                logo,
                line_spacing,
            )
            images.append(task_frame)

        # Process each history item
        for i, item in enumerate(self.history.history, 1):
            if not item.state.screenshot:
                continue
            # Convert base64 screenshot to PIL Image
            img_data = base64.b64decode(item.state.screenshot)
            image = Image.open(io.BytesIO(img_data))

            if show_goals and item.model_output:
                image = self._add_overlay_to_image(
                    image=image,
                    step_number=i,
                    goal_text=item.model_output.current_state.thought,
                    regular_font=regular_font,
                    title_font=title_font,
                    margin=margin,
                    logo=logo,
                )
            images.append(image)

        if images:
            # Save the GIF
            images[0].save(
                output_path,
                save_all=True,
                append_images=images[1:],
                duration=duration,
                loop=0,
                optimize=False,
            )
            logger.info(f'Created GIF at {output_path}')
        else:
            logger.warning('No images found in history to create GIF')

    async def run(self, max_steps: int = 100) -> AgentHistoryList:
        """Execute the task with maximum number of steps"""
        try:
            logger.info(f"🚀 Starting task: {self.task}")
            
            # Fix the telemetry event to only include supported parameters
            self.telemetry.capture(
                AgentRunTelemetryEvent(
                    agent_id=self.agent_id,
                    task=self.task,
                    # Remove the unsupported parameters
                )
            )

            # Create the step_info with all required parameters
            step_info = CustomAgentStepInfo(
                task=self.task,
                add_infos=self.add_infos,
                step_number=1,
                max_steps=max_steps,
                memory="",
                task_progress="",
            )

            for step in range(max_steps):
                # 1) Check if stop requested
                if self.agent_state and self.agent_state.is_stop_requested():
                    logger.info("🛑 Stop requested by user")
                    self._create_stop_history_item()
                    break

                # 2) Store last valid state before step
                if self.browser_context and self.agent_state:
                    state = await self.browser_context.get_state(use_vision=self.use_vision)
                    self.agent_state.set_last_valid_state(state)

                if self._too_many_failures():
                    break

                # 3) Do the step
                await self.step(step_info)

                if (
                        self.validate_output and step < max_steps - 1
                ):  # if last step, we dont need to validate
                    if not await self._validate_output():
                        continue

                if self.history.is_done():
                    logger.info("✅ Task completed successfully")
                    break
            else:
                logger.info("❌ Failed to complete task in maximum steps")

            return self.history
        finally:
            self.telemetry.capture(
                AgentEndTelemetryEvent(
                    agent_id=self.agent_id,
                    task=self.task,
                    success=self.history.is_done(),
                    steps=len(self.history.history),
                )
            )
            if not self.injected_browser_context:
                await self.browser_context.close()
            if not self.injected_browser and self.browser:
                await self.browser.close()
            if self.generate_gif:
                self.create_history_gif()

    def _create_stop_history_item(self):
        """Create a history item for when the agent is stopped."""
        try:
            # Attempt to retrieve the last valid state from agent_state
            state = None
            if self.agent_state:
                last_state = self.agent_state.get_last_valid_state()
                if last_state:
                    # Convert to BrowserStateHistory
                    state = BrowserStateHistory(
                        url=getattr(last_state, 'url', ""),
                        title=getattr(last_state, 'title', ""),
                        tabs=getattr(last_state, 'tabs', []),
                        interacted_element=[None],
                        screenshot=getattr(last_state, 'screenshot', None)
                    )
                else:
                    state = self._create_empty_state()
            else:
                state = self._create_empty_state()
            # Create a final item in the agent history indicating done
            stop_history = AgentHistory(
                model_output=None,
                state=state,
                result=[ActionResult(extracted_content=None, error=None, is_done=True)]
            )
            self.history.history.append(stop_history)

        except Exception as e:
            logger.error(f"Error creating stop history item: {e}")
            # Create empty state as fallback
            state = self._create_empty_state()
            stop_history = AgentHistory(
                model_output=None,
                state=state,
                result=[ActionResult(extracted_content=None, error=None, is_done=True)]
            )
            self.history.history.append(stop_history)

    def _convert_to_browser_state_history(self, browser_state):
        return BrowserStateHistory(
            url=getattr(browser_state, 'url', ""),
            title=getattr(browser_state, 'title', ""),
            tabs=getattr(browser_state, 'tabs', []),
            interacted_element=[None],
            screenshot=getattr(browser_state, 'screenshot', None)
        )

    def _create_empty_state(self):
        return BrowserStateHistory(
            url="",
            title="",
            tabs=[],
            interacted_element=[None],
            screenshot=None
        )

    def _should_recommend_scrolling(self, state, task: str) -> bool:
        """Determine if we should recommend scrolling based on the current context"""
        lower_task = task.lower()
        
        # Keywords that suggest we need to see all content
        scroll_keywords = ["last", "all", "every", "bottom", "end", "complete", "entire"]
        
        # Check if any of these keywords are in the task
        needs_full_page = any(keyword in lower_task for keyword in scroll_keywords)
        
        # Check if we're on a page that typically needs scrolling
        on_results_page = state and any(x in state.url.lower() for x in ["search", "results", "list"])
        
        return needs_full_page or on_results_page
