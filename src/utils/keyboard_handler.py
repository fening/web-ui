import logging
import threading
import time
import asyncio
from .agent_state import AgentState

logger = logging.getLogger(__name__)

# Try to import pynput, but gracefully handle if it's missing
pynput_available = False
try:
    from pynput import keyboard
    pynput_available = True
except ImportError:
    logger.warning("pynput module not found. Keyboard shortcuts will be disabled.")
    logger.warning("To enable keyboard shortcuts, install pynput with: pip install pynput")
    # Create a dummy keyboard module to prevent errors
    class DummyKeyboard:
        class Key:
            ctrl_l = "ctrl_l"
            alt_l = "alt_l"
        
        class KeyCode:
            @staticmethod
            def from_char(c):
                return f"key_{c}"
                
        class Listener:
            def __init__(self, *args, **kwargs):
                pass
                
            def __enter__(self):
                return self
                
            def __exit__(self, *args):
                pass
                
            def join(self):
                pass
                
            def stop(self):
                pass
    
    keyboard = DummyKeyboard()

class KeyboardShortcutHandler:
    """Handle global keyboard shortcuts for agent control"""
    
    def __init__(self, agent_state: AgentState = None):
        """Initialize keyboard handler"""
        self.agent_state = agent_state
        self.active_agent_id = None
        self.keyboard_listener = None
        self.running = False
        self.shortcuts = {
            # Define keyboard shortcuts with their friendly names
            "stop": {keyboard.Key.ctrl_l, keyboard.Key.alt_l, keyboard.KeyCode.from_char('s')},
            "pause_resume": {keyboard.Key.ctrl_l, keyboard.Key.alt_l, keyboard.KeyCode.from_char('p')},
            "help": {keyboard.Key.ctrl_l, keyboard.Key.alt_l, keyboard.KeyCode.from_char('h')},
            "status": {keyboard.Key.ctrl_l, keyboard.Key.alt_l, keyboard.KeyCode.from_char('i')},  # 'i' for info
            "screenshot": {keyboard.Key.ctrl_l, keyboard.Key.alt_l, keyboard.KeyCode.from_char('c')},
        }
        self.shortcut_descriptions = {
            "stop": "Stop the agent",
            "pause_resume": "Pause/Resume the agent",
            "help": "Show help information",
            "status": "Show current agent status",
            "screenshot": "Capture browser screenshot",
        }
        
    def start(self):
        """Start listening for keyboard shortcuts"""
        if not pynput_available:
            logger.warning("Keyboard shortcuts disabled due to missing pynput module")
            logger.warning("To enable, install with: pip install pynput")
            return
            
        if self.keyboard_listener is not None:
            return
            
        self.running = True
        
        # Start keyboard listener in a separate thread
        keyboard_thread = threading.Thread(target=self._start_keyboard_listener)
        keyboard_thread.daemon = True
        keyboard_thread.start()
        
        logger.info("⌨️ Keyboard shortcuts are active")
        logger.info("Available shortcuts:")
        logger.info("  Ctrl+Alt+S: Stop agent")
        logger.info("  Ctrl+Alt+P: Pause/Resume agent")
        logger.info("  Ctrl+Alt+H: Show help")
        logger.info("  Ctrl+Alt+I: Show status info")
        logger.info("  Ctrl+Alt+C: Capture screenshot")
        
        # Display to terminal also for better visibility
        print("\n" + "-" * 50)
        print("⌨️ KEYBOARD SHORTCUTS AVAILABLE:")
        print("  Ctrl+Alt+S: Stop agent")
        print("  Ctrl+Alt+P: Pause/Resume agent")
        print("  Ctrl+Alt+H: Show help")
        print("  Ctrl+Alt+I: Show status info")
        print("  Ctrl+Alt+C: Capture screenshot")
        print("-" * 50 + "\n")
    
    def stop(self):
        """Stop the keyboard listener"""
        self.running = False
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None
    
    def set_active_agent(self, agent_id: str = None):
        """Set the currently active agent ID"""
        self.active_agent_id = agent_id
    
    def _start_keyboard_listener(self):
        """Start the actual keyboard listener"""
        if not pynput_available:
            return
            
        try:
            # Track currently pressed keys
            current_keys = set()
            
            def on_press(key):
                if not self.running:
                    return False
                    
                # Add the key to current keys
                current_keys.add(key)
                
                # Check for stop shortcut
                if self.shortcuts["stop"].issubset(current_keys):
                    print("\n🛑 KEYBOARD SHORTCUT: Stopping agent")
                    logger.info("🛑 Stop shortcut detected")
                    self._handle_stop()
                    return True
                
                # Check for pause/resume shortcut
                if self.shortcuts["pause_resume"].issubset(current_keys):
                    print("\n⏯️ KEYBOARD SHORTCUT: Toggle pause/resume")
                    logger.info("⏯️ Pause/Resume shortcut detected")
                    self._handle_pause_resume()
                    return True
                
                # Check for help shortcut
                if self.shortcuts["help"].issubset(current_keys):
                    print("\n❓ KEYBOARD SHORTCUT: Showing help")
                    logger.info("❓ Help shortcut detected")
                    self._handle_help()
                    return True
                    
                # Check for status shortcut
                if self.shortcuts["status"].issubset(current_keys):
                    print("\nℹ️ KEYBOARD SHORTCUT: Showing status")
                    logger.info("ℹ️ Status shortcut detected")
                    self._handle_status()
                    return True
                    
                # Check for screenshot shortcut
                if self.shortcuts["screenshot"].issubset(current_keys):
                    print("\n📸 KEYBOARD SHORTCUT: Capturing screenshot")
                    logger.info("📸 Screenshot shortcut detected")
                    self._handle_screenshot()
                    return True
                
                return True
                
            def on_release(key):
                try:
                    current_keys.remove(key)
                except KeyError:
                    pass
                return True
                
            # Start the listener
            with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
                self.keyboard_listener = listener
                listener.join()
                
        except Exception as e:
            logger.error(f"Error in keyboard shortcut handler: {e}")
    
    def _handle_stop(self):
        """Stop the agent"""
        if self.agent_state:
            self.agent_state.request_stop()
            print("🛑 Agent will stop at the next safe point")
        else:
            print("⚠️ No agent state available to stop")
    
    def _handle_pause_resume(self):
        """Toggle pause/resume state"""
        if not self.active_agent_id:
            print("⚠️ No active agent to pause/resume")
            return
            
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            from .agent_control import agent_control_manager
            is_paused = agent_control_manager.is_paused(self.active_agent_id)
            
            if is_paused:
                # Resume if paused
                loop.run_until_complete(agent_control_manager.resume_agent(self.active_agent_id))
                print("▶️ Agent is resuming execution")
            else:
                # Pause if running
                loop.run_until_complete(agent_control_manager.pause_agent(self.active_agent_id))
                print("⏸️ Agent will pause at the next safe point")
        except Exception as e:
            print(f"⚠️ Error toggling pause/resume: {e}")
        finally:
            loop.close()
    
    def _handle_help(self):
        """Show help information"""
        print("\n" + "=" * 50)
        print("⌨️ KEYBOARD SHORTCUTS:")
        for shortcut_name, keys in self.shortcuts.items():
            key_combo = "+".join(str(k).replace("Key.", "").title() for k in keys)
            print(f"  {key_combo}: {self.shortcut_descriptions[shortcut_name]}")
        print("\nℹ️ These shortcuts work globally while the agent is running")
        print("=" * 50)
    
    def _handle_status(self):
        """Show current agent status"""
        if not self.active_agent_id:
            print("⚠️ No active agent")
            return
            
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            from .agent_control import agent_control_manager
            is_paused = agent_control_manager.is_paused(self.active_agent_id)
            
            print("\n" + "=" * 50)
            print(f"🔹 AGENT STATUS: {self.active_agent_id}")
            print(f"  State: {'⏸️ PAUSED' if is_paused else '▶️ RUNNING'}")
            
            # Check if stop requested
            if self.agent_state and self.agent_state.is_stop_requested():
                print("  🛑 Stop has been requested")
                
            print("=" * 50)
        except Exception as e:
            print(f"⚠️ Error getting agent status: {e}")
        finally:
            loop.close()
            
    def _handle_screenshot(self):
        """Capture a screenshot of the current browser state"""
        from .utils import capture_screenshot
        from ..browser.custom_browser import _global_browser_context
        
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Get timestamp for filename
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            
            # Capture screenshot
            screenshot_data = loop.run_until_complete(capture_screenshot(_global_browser_context))
            
            if screenshot_data:
                # Save screenshot to file
                import base64
                img_data = base64.b64decode(screenshot_data)
                with open(filename, "wb") as f:
                    f.write(img_data)
                print(f"📸 Screenshot saved to: {filename}")
            else:
                print("⚠️ Could not capture screenshot - browser may not be initialized")
        except Exception as e:
            print(f"⚠️ Error capturing screenshot: {e}")
        finally:
            loop.close()

# Global instance
keyboard_handler = KeyboardShortcutHandler()
