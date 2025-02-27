import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import json
import os

logger = logging.getLogger(__name__)

class AgentControlManager:
    """Manages the control flow of agents with pause/resume capabilities"""
    
    def __init__(self):
        self.paused_agents = {}
        self.pause_events = {}  # Using asyncio.Event for signaling
        self.state_snapshots = {}
        self.save_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tmp", "saved_sessions")
        os.makedirs(self.save_dir, exist_ok=True)
        
    async def pause_agent(self, agent_id: str) -> bool:
        """
        Signal an agent to pause at the next safe point
        
        Args:
            agent_id: Unique ID of the agent to pause
            
        Returns:
            True if pause was requested, False if already paused
        """
        if agent_id in self.paused_agents and self.paused_agents[agent_id]:
            return False
        
        logger.info(f"🔄 Requested pause for agent {agent_id}")
        self.paused_agents[agent_id] = True
        
        # Create an event for this agent if it doesn't exist
        if agent_id not in self.pause_events:
            self.pause_events[agent_id] = asyncio.Event()
            # Initially clear the event (not set)
            self.pause_events[agent_id].clear()
            
        return True
    
    async def resume_agent(self, agent_id: str) -> bool:
        """
        Signal an agent to resume execution
        
        Args:
            agent_id: Unique ID of the agent to resume
            
        Returns:
            True if resumed, False if not paused
        """
        if agent_id not in self.paused_agents or not self.paused_agents[agent_id]:
            return False
        
        logger.info(f"▶️ Resuming agent {agent_id}")
        self.paused_agents[agent_id] = False
        
        # Set the event to signal resumption
        if agent_id in self.pause_events:
            self.pause_events[agent_id].set()
            
        return True
    
    async def check_and_wait_if_paused(self, agent_id: str) -> None:
        """
        Check if agent is paused and wait if needed
        
        This should be called at safe points in the agent execution
        
        Args:
            agent_id: Unique ID of the agent to check
        """
        if agent_id in self.paused_agents and self.paused_agents[agent_id]:
            logger.info(f"⏸️ Agent {agent_id} paused - waiting for resume signal")
            
            # Create event if it doesn't exist
            if agent_id not in self.pause_events:
                self.pause_events[agent_id] = asyncio.Event()
                
            # Wait until the resume signal is received
            await self.pause_events[agent_id].wait()
            self.pause_events[agent_id].clear()  # Reset for future pauses
            logger.info(f"▶️ Agent {agent_id} continuing execution")
    
    def is_paused(self, agent_id: str) -> bool:
        """Check if an agent is currently paused"""
        return agent_id in self.paused_agents and self.paused_agents[agent_id]
    
    def save_session_state(self, agent_id: str, state_data: Dict[str, Any]) -> str:
        """
        Save agent session state for later restoration
        
        Args:
            agent_id: Unique ID of the agent
            state_data: Dictionary of state data to save
            
        Returns:
            Path to the saved state file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{agent_id}_{timestamp}.json"
        filepath = os.path.join(self.save_dir, filename)
        
        # Add metadata to state
        state_data['_metadata'] = {
            'agent_id': agent_id,
            'timestamp': timestamp,
            'saved_at': datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(state_data, f, indent=2)
        
        logger.info(f"💾 Saved agent {agent_id} state to {filepath}")
        return filepath
    
    def load_session_state(self, filepath: str) -> Optional[Dict[str, Any]]:
        """
        Load agent session state from file
        
        Args:
            filepath: Path to the state file
            
        Returns:
            Dictionary of state data or None if loading failed
        """
        try:
            with open(filepath, 'r') as f:
                state_data = json.load(f)
                
            logger.info(f"📂 Loaded agent state from {filepath}")
            return state_data
        except Exception as e:
            logger.error(f"Failed to load agent state: {e}")
            return None
    
    def list_saved_sessions(self) -> Dict[str, list]:
        """
        List all saved agent sessions
        
        Returns:
            Dictionary of agent IDs to lists of saved session files
        """
        sessions = {}
        
        try:
            for filename in os.listdir(self.save_dir):
                if filename.endswith(".json"):
                    parts = filename.split("_")
                    if len(parts) >= 2:
                        agent_id = parts[0]
                        if agent_id not in sessions:
                            sessions[agent_id] = []
                        sessions[agent_id].append(os.path.join(self.save_dir, filename))
        except Exception as e:
            logger.error(f"Error listing saved sessions: {e}")
            
        return sessions

# Global instance
agent_control_manager = AgentControlManager()
