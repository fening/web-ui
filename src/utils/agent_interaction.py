# -*- coding: utf-8 -*-
import asyncio
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, Callable, List

logger = logging.getLogger(__name__)

class InteractionType(Enum):
    """Types of interaction between agent and user"""
    TEXT_INPUT = "text_input"
    CONFIRMATION = "confirmation"
    LOGIN = "login"
    SELECTION = "selection"
    CUSTOM = "custom"

@dataclass
class InteractionRequest:
    """Request from agent to user for interaction"""
    request_id: str
    type: InteractionType
    prompt: str
    description: str = ""
    options: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    required: bool = True
    
@dataclass
class InteractionResponse:
    """Response from user to agent"""
    request_id: str
    response: Any
    cancelled: bool = False

class UserInteractionManager:
    """Manages interactions between agent and user"""
    
    def __init__(self):
        self._requests = {}  # Store pending requests
        self._responses = {}  # Store received responses
        self._events = {}  # Event objects for waiting
        self._callbacks = {}  # Optional callbacks
        
    async def request_interaction(self, request: InteractionRequest, 
                                  callback: Optional[Callable] = None, 
                                  timeout: int = 300) -> InteractionResponse:
        """
        Request interaction from the user and wait for response
        
        Args:
            request: The interaction request
            callback: Optional callback for when response received
            timeout: Timeout in seconds for waiting (default 5 minutes)
            
        Returns:
            User's response or None if timeout/cancelled
        """
        self._requests[request.request_id] = request
        self._events[request.request_id] = asyncio.Event()
        
        if callback:
            self._callbacks[request.request_id] = callback
            
        # Log the request
        logger.info(f"👤 Requesting user interaction: {request.prompt}")
        
        # Wait for response with timeout
        try:
            await asyncio.wait_for(self._events[request.request_id].wait(), timeout)
            response = self._responses.get(request.request_id)
            
            # Clean up
            self._cleanup_request(request.request_id)
            
            return response
        except asyncio.TimeoutError:
            logger.warning(f"User interaction timed out after {timeout}s: {request.prompt}")
            self._cleanup_request(request.request_id)
            return InteractionResponse(
                request_id=request.request_id,
                response=None,
                cancelled=True
            )
    
    def provide_response(self, request_id: str, response: Any, cancelled: bool = False) -> None:
        """
        Provide user response to a pending request
        
        Args:
            request_id: ID of the request being responded to
            response: User's response data
            cancelled: Whether the interaction was cancelled
        """
        if request_id not in self._requests:
            logger.warning(f"Response provided for unknown request ID: {request_id}")
            return
            
        self._responses[request_id] = InteractionResponse(
            request_id=request_id,
            response=response,
            cancelled=cancelled
        )
        
        # Execute callback if registered
        if request_id in self._callbacks and not cancelled:
            try:
                self._callbacks[request_id](response)
            except Exception as e:
                logger.error(f"Error in interaction callback: {e}")
        
        # Set event to resume agent execution
        if request_id in self._events:
            self._events[request_id].set()
    
    def get_pending_requests(self) -> Dict[str, InteractionRequest]:
        """Get all pending interaction requests"""
        return self._requests.copy()
    
    def cancel_request(self, request_id: str) -> None:
        """Cancel a pending request"""
        if request_id in self._requests:
            self.provide_response(request_id, None, cancelled=True)
            self._cleanup_request(request_id)
    
    def _cleanup_request(self, request_id: str) -> None:
        """Clean up request data"""
        if request_id in self._requests:
            del self._requests[request_id]
        if request_id in self._callbacks:
            del self._callbacks[request_id]
        if request_id in self._events:
            del self._events[request_id]
        if request_id in self._responses:
            del self._responses[request_id]

# Singleton instance
interaction_manager = UserInteractionManager()
