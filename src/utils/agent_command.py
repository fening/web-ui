import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any
import uuid

logger = logging.getLogger(__name__)

class CommandRequest:
    """Represents a command to be processed by the agent"""
    
    def __init__(self, command: str, parameters: Dict[str, Any] = None):
        self.id = str(uuid.uuid4())
        self.command = command
        self.parameters = parameters or {}
        self.result = None
        self.completed = False
        self.event = asyncio.Event()

class AgentCommandManager:
    """Manages commands that can be sent to an agent during execution"""
    
    def __init__(self):
        self.command_queue = {}  # Map agent_id -> list of CommandRequest
        self.command_handlers = {}  # Map command_name -> handler function
        
    def register_handler(self, command_name: str, handler_func: Callable):
        """Register a handler function for a specific command"""
        self.command_handlers[command_name] = handler_func
        logger.debug(f"Registered handler for command '{command_name}'")
        
    def add_command(self, agent_id: str, command: str, parameters: Dict[str, Any] = None) -> CommandRequest:
        """Add a command to an agent's queue"""
        if agent_id not in self.command_queue:
            self.command_queue[agent_id] = []
            
        cmd_request = CommandRequest(command, parameters)
        self.command_queue[agent_id].append(cmd_request)
        
        logger.info(f"Added command '{command}' to agent {agent_id}'s queue")
        return cmd_request
        
    async def process_commands(self, agent_id: str, agent_obj: Any) -> None:
        """Process any pending commands for an agent"""
        if agent_id not in self.command_queue or not self.command_queue[agent_id]:
            return
            
        # Get commands and clear queue
        commands = self.command_queue[agent_id].copy()
        self.command_queue[agent_id].clear()
        
        for cmd in commands:
            if cmd.command in self.command_handlers:
                try:
                    logger.info(f"Processing command '{cmd.command}' for agent {agent_id}")
                    result = await self.command_handlers[cmd.command](agent_obj, **cmd.parameters)
                    cmd.result = result
                except Exception as e:
                    logger.error(f"Error executing command '{cmd.command}': {e}")
                    cmd.result = {"error": str(e)}
                    
                cmd.completed = True
                cmd.event.set()
            else:
                logger.warning(f"No handler for command '{cmd.command}'")
                cmd.result = {"error": f"Unknown command '{cmd.command}'"}
                cmd.completed = True
                cmd.event.set()
                
    async def wait_for_command(self, cmd_request: CommandRequest, timeout: float = None) -> Optional[Any]:
        """Wait for a command to complete and get its result"""
        try:
            await asyncio.wait_for(cmd_request.event.wait(), timeout)
            return cmd_request.result
        except asyncio.TimeoutError:
            return {"error": "Command timed out"}

# Global instance
agent_command_manager = AgentCommandManager()

# Register some built-in commands
async def cmd_get_page_info(agent):
    """Get information about the current page"""
    if hasattr(agent, 'browser_context'):
        state = await agent.browser_context.get_state(use_vision=False)
        return {
            "url": state.url,
            "title": state.title,
            "tabs_count": len(state.tabs)
        }
    return {"error": "No browser context available"}

async def cmd_add_memory(agent, memory_text):
    """Add a memory item to the agent"""
    if hasattr(agent, 'message_manager'):
        agent.message_manager.add_memory_item(memory_text)
        return {"status": "Memory added"}
    return {"error": "Agent does not support memory addition"}

# Register handlers
agent_command_manager.register_handler("get_page_info", cmd_get_page_info)
agent_command_manager.register_handler("add_memory", cmd_add_memory)
