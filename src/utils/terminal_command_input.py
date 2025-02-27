import sys
import threading
import asyncio
import logging
import time

logger = logging.getLogger(__name__)

class TerminalCommandInput:
    """
    Monitors terminal input for commands while agent is running.
    Allows pausing/resuming/stopping the agent from the same terminal where logs appear.
    """
    
    def __init__(self):
        self.running = False
        self.input_thread = None
        self.commands = {
            'pause': self._handle_pause,
            'resume': self._handle_resume,
            'stop': self._handle_stop,
            'help': self._handle_help,
            'status': self._handle_status
        }
        self.current_agent_id = None
        self.agent_state = None
    
    def start(self, agent_id=None, agent_state=None):
        """Start the terminal command listener"""
        self.running = True
        self.current_agent_id = agent_id
        self.agent_state = agent_state
        
        # Create and start the listener thread
        self.input_thread = threading.Thread(target=self._input_listener)
        self.input_thread.daemon = True
        self.input_thread.start()
        
        # Display available commands
        print("\n" + "-" * 50)
        print("🔹 Terminal commands available while agent is running:")
        print("   Type 'pause' to pause the agent")
        print("   Type 'resume' to resume if paused")
        print("   Type 'stop' to stop the agent")
        print("   Type 'status' for current agent status")
        print("   Type 'help' for command list")
        print("-" * 50 + "\n")
    
    def stop(self):
        """Stop the terminal command listener"""
        self.running = False
        # No need to join thread as it's a daemon
    
    def set_agent_id(self, agent_id):
        """Update the current agent ID"""
        self.current_agent_id = agent_id
        logger.debug(f"Terminal command input: Agent ID set to {agent_id}")
        print(f"\n✅ Terminal commands now linked to agent: {agent_id}")
        print("Type 'pause', 'resume', 'stop', 'status', or 'help' to interact.\n")
    
    def set_agent_state(self, agent_state):
        """Update the agent state reference"""
        self.agent_state = agent_state
    
    def _input_listener(self):
        """Listen for terminal input in a separate thread"""
        try:
            while self.running:
                # Check for input without blocking main thread
                if self._has_input():
                    cmd = input().strip().lower()
                    if cmd in self.commands:
                        self.commands[cmd]()
                    elif cmd:
                        print(f"Unknown command: '{cmd}'. Type 'help' for command list.")
                
                # Sleep briefly to avoid high CPU usage
                time.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Error in terminal input listener: {e}")
        
        logger.debug("Terminal input listener stopped")
    
    def _has_input(self):
        """Check if there is pending input without blocking"""
        # This is a simplified way to check if input is available on some systems
        # On Windows, we'll just have minimal responsiveness with the sleep above
        return True
    
    def _handle_pause(self):
        """Handle pause command"""
        if not self.current_agent_id:
            print("⚠️ No active agent to pause")
            return
            
        print("⏸️ Requesting agent to pause...")
        
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            from .agent_control import agent_control_manager
            loop.run_until_complete(agent_control_manager.pause_agent(self.current_agent_id))
            print("⏸️ Agent will pause at the next safe point")
        except Exception as e:
            print(f"⚠️ Error pausing agent: {e}")
        finally:
            loop.close()
    
    def _handle_resume(self):
        """Handle resume command"""
        if not self.current_agent_id:
            print("⚠️ No active agent to resume")
            return
            
        print("▶️ Requesting agent to resume...")
        
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            from .agent_control import agent_control_manager
            loop.run_until_complete(agent_control_manager.resume_agent(self.current_agent_id))
            print("▶️ Agent execution resuming")
        except Exception as e:
            print(f"⚠️ Error resuming agent: {e}")
        finally:
            loop.close()
    
    def _handle_stop(self):
        """Handle stop command"""
        if not self.agent_state:
            print("⚠️ No active agent to stop")
            return
            
        print("🛑 Requesting agent to stop...")
        self.agent_state.request_stop()
        print("🛑 Agent will stop at the next safe point")
    
    def _handle_help(self):
        """Show available commands"""
        print("\n" + "-" * 50)
        print("🔹 Available Commands:")
        print("   pause  - Pause the agent at the next safe point")
        print("   resume - Resume a paused agent")
        print("   stop   - Stop the agent completely")
        print("   status - Check the agent's current status")
        print("   help   - Show this help message")
        print("-" * 50)
    
    def _handle_status(self):
        """Show agent status"""
        if not self.current_agent_id:
            print("⚠️ No active agent")
            return
            
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            from .agent_control import agent_control_manager
            is_paused = agent_control_manager.is_paused(self.current_agent_id)
            
            print("\n" + "-" * 50)
            print(f"🔹 Agent Status: {self.current_agent_id}")
            print(f"   State: {'PAUSED' if is_paused else 'RUNNING'}")
            
            # Check if stop requested
            if self.agent_state and self.agent_state.is_stop_requested():
                print("   Stop has been requested")
                
            print("-" * 50)
        except Exception as e:
            print(f"⚠️ Error getting agent status: {e}")
        finally:
            loop.close()

# Global instance
terminal_command_input = TerminalCommandInput()
