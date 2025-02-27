import asyncio
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)

class AgentState:
    """
    Maintains state for an agent that can be accessed across processing boundaries
    """
    _instance = None

    def __init__(self):
        self._stop_requested = False
        self._agent_id = None
        self._last_valid_state = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentState, cls).__new__(cls)
        return cls._instance

    def request_stop(self):
        """Request the agent to stop at the next safe point"""
        self._stop_requested = True
        logger.info("Stop requested for agent")

    def clear_stop(self):
        """Clear any pending stop request"""
        self._stop_requested = False

    def is_stop_requested(self) -> bool:
        """Check if a stop has been requested"""
        return self._stop_requested

    def set_agent_id(self, agent_id: str):
        """Set the agent ID"""
        self._agent_id = agent_id
        logger.debug(f"Agent state now tracking agent ID: {agent_id}")

    def get_agent_id(self) -> Optional[str]:
        """Get the current agent ID"""
        return self._agent_id

    def set_last_valid_state(self, state: Any):
        """Set the last valid browser state"""
        self._last_valid_state = state

    def get_last_valid_state(self) -> Any:
        """Get the last valid browser state"""
        return self._last_valid_state