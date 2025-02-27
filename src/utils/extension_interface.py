import logging
import asyncio
import json
import websockets
from typing import Dict, Any, Optional, Callable, List
from .notification_manager import notification_manager, NotificationLevel

logger = logging.getLogger(__name__)

class ExtensionInterface:
    """Interface for the browser extension to communicate with the agent"""
    
    def __init__(self, port: int = 7789):
        self.port = port
        self.server = None
        self.clients = set()
        self.message_handlers: Dict[str, Callable] = {}
        self.running = False
        
    async def start_server(self):
        """Start the WebSocket server"""
        if self.server:
            return
            
        self.running = True
        
        try:
            self.server = await websockets.serve(
                self._handle_client,
                "127.0.0.1",
                self.port
            )
            
            logger.info(f"Extension interface running on ws://127.0.0.1:{self.port}")
            notification_manager.info(
                f"Extension interface available on port {self.port}",
                title="Extension Ready"
            )
            
        except Exception as e:
            logger.error(f"Failed to start extension interface: {e}")
            self.running = False
    
    async def stop_server(self):
        """Stop the WebSocket server"""
        self.running = False
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
            logger.info("Extension interface stopped")
    
    def register_handler(self, message_type: str, handler: Callable):
        """Register a handler for specific message types"""
        self.message_handlers[message_type] = handler
        logger.debug(f"Registered handler for '{message_type}' messages")
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all connected clients"""
        if not self.clients:
            return
            
        message_json = json.dumps(message)
        
        for client in self.clients.copy():
            try:
                await client.send(message_json)
            except Exception as e:
                logger.debug(f"Error broadcasting to client: {e}")
                self.clients.discard(client)
    
    async def _handle_client(self, websocket, path):
        """Handle a client connection"""
        self.clients.add(websocket)
        logger.debug(f"New extension client connected (total: {len(self.clients)})")
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    
                    if not isinstance(data, dict) or "type" not in data:
                        logger.warning(f"Invalid message format: {message[:100]}")
                        continue
                        
                    message_type = data["type"]
                    
                    # Handle based on message type
                    if message_type in self.message_handlers:
                        handler = self.message_handlers[message_type]
                        await handler(data, websocket)
                    else:
                        logger.debug(f"No handler for message type: {message_type}")
                        
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received: {message[:100]}")
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)
            logger.debug(f"Extension client disconnected (remaining: {len(self.clients)})")

# Global extension interface instance
extension_interface = ExtensionInterface()

# Register built-in handlers
async def handle_ping(data, websocket):
    """Handle ping messages"""
    try:
        await websocket.send(json.dumps({"type": "pong", "timestamp": data.get("timestamp")}))
    except Exception as e:
        logger.error(f"Error responding to ping: {e}")

async def handle_agent_control(data, websocket):
    """Handle agent control messages"""
    from .agent_control import agent_control_manager
    
    command = data.get("command")
    agent_id = data.get("agent_id")
    
    if not agent_id:
        logger.warning("Agent control message missing agent_id")
        return
    
    try:
        if command == "pause":
            success = await agent_control_manager.pause_agent(agent_id)
            await websocket.send(json.dumps({
                "type": "control_response", 
                "command": command,
                "success": success,
                "agent_id": agent_id
            }))
        elif command == "resume":
            success = await agent_control_manager.resume_agent(agent_id)
            await websocket.send(json.dumps({
                "type": "control_response", 
                "command": command,
                "success": success,
                "agent_id": agent_id
            }))
        elif command == "status":
            is_paused = agent_control_manager.is_paused(agent_id)
            await websocket.send(json.dumps({
                "type": "control_response", 
                "command": command,
                "agent_id": agent_id,
                "status": "paused" if is_paused else "running"
            }))
        else:
            logger.warning(f"Unknown agent control command: {command}")
            await websocket.send(json.dumps({
                "type": "control_response", 
                "command": command,
                "success": False,
                "error": "Unknown command"
            }))
    except Exception as e:
        logger.error(f"Error handling agent control: {e}")
        await websocket.send(json.dumps({
            "type": "control_response", 
            "command": command,
            "success": False,
            "error": str(e)
        }))

# Register handlers
extension_interface.register_handler("ping", handle_ping)
extension_interface.register_handler("agent_control", handle_agent_control)
