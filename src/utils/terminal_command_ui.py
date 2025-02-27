import os
import asyncio
import logging
import threading
import curses
import time
from typing import Dict, List
from .agent_command import agent_command_manager

logger = logging.getLogger(__name__)

class TerminalCommandUI:
    """Terminal-based UI for interacting with agents"""
    
    def __init__(self):
        self.active = False
        self.current_agent_id = None
        self.command_history = []
        self.input_buffer = ""
        self.stdscr = None
        self.ui_thread = None
        
    def start(self, agent_id: str = None):
        """Start the terminal UI in its own thread"""
        if self.active:
            return False
            
        self.active = True
        self.current_agent_id = agent_id
        
        self.ui_thread = threading.Thread(target=self._run_ui)
        self.ui_thread.daemon = True
        self.ui_thread.start()
        
        return True
        
    def stop(self):
        """Stop the terminal UI"""
        self.active = False
        
    def _run_ui(self):
        """Run the curses-based UI"""
        try:
            curses.wrapper(self._main_loop)
        except Exception as e:
            logger.error(f"Error in terminal UI: {e}")
            self.active = False
    
    def _main_loop(self, stdscr):
        """Main curses UI loop"""
        self.stdscr = stdscr
        curses.curs_set(1)  # Show cursor
        curses.start_color()
        curses.use_default_colors()
        
        # Initialize color pairs
        curses.init_pair(1, curses.COLOR_GREEN, -1)  # Prompt
        curses.init_pair(2, curses.COLOR_CYAN, -1)   # Input
        curses.init_pair(3, curses.COLOR_YELLOW, -1) # System messages
        curses.init_pair(4, curses.COLOR_RED, -1)    # Errors
        
        height, width = stdscr.getmaxyx()
        
        # Create windows
        header_win = curses.newwin(3, width, 0, 0)
        cmd_output_win = curses.newwin(height-6, width, 3, 0)
        input_win = curses.newwin(3, width, height-3, 0)
        
        # Enable scrolling for output window
        cmd_output_win.scrollok(True)
        
        self._draw_header(header_win)
        self._draw_input_line(input_win)
        
        cmd_output_win.addstr(0, 0, "Enter commands to interact with the agent. Type 'help' for available commands.\n")
        cmd_output_win.addstr("Commands: help, status, pause, resume, stop, screenshot, add-memory\n\n")
        cmd_output_win.refresh()
        
        # Input processing loop
        while self.active:
            self._draw_header(header_win)
            self._draw_input_line(input_win)
            
            try:
                key = input_win.getch()
                
                if key == ord('\n'):  # Enter key
                    if self.input_buffer:
                        self._process_command(cmd_output_win)
                        self.input_buffer = ""
                elif key == 27:  # Escape key
                    self.active = False
                    break
                elif key == curses.KEY_BACKSPACE or key == 127:  # Backspace
                    self.input_buffer = self.input_buffer[:-1]
                elif 32 <= key <= 126:  # Printable ASCII
                    self.input_buffer += chr(key)
                    
                self._draw_input_line(input_win)
                    
            except Exception as e:
                cmd_output_win.addstr(f"Error: {str(e)}\n", curses.color_pair(4))
                cmd_output_win.refresh()
        
        # Cleanup
        curses.endwin()
    
    def _draw_header(self, win):
        """Draw the UI header"""
        win.clear()
        win.border()
        height, width = win.getmaxyx()
        
        title = "Agent Terminal Control"
        win.addstr(1, (width - len(title)) // 2, title, curses.A_BOLD)
        
        agent_text = f"Agent: {self.current_agent_id or 'None'}"
        win.addstr(1, 2, agent_text)
        
        exit_text = "ESC to exit"
        win.addstr(1, width - len(exit_text) - 2, exit_text)
        
        win.refresh()
    
    def _draw_input_line(self, win):
        """Draw the command input line"""
        win.clear()
        win.border()
        height, width = win.getmaxyx()
        
        prompt = "> "
        win.addstr(1, 2, prompt, curses.color_pair(1))
        
        # Calculate how much of the input buffer to show
        max_input_len = width - len(prompt) - 4
        if len(self.input_buffer) > max_input_len:
            display_buf = "..." + self.input_buffer[-(max_input_len-3):]
        else:
            display_buf = self.input_buffer
            
        win.addstr(1, 2 + len(prompt), display_buf, curses.color_pair(2))
        win.refresh()
    
    def _process_command(self, output_win):
        """Process a command and display results"""
        cmd = self.input_buffer.strip()
        self.command_history.append(cmd)
        
        output_win.addstr(f"\n> {cmd}\n", curses.color_pair(2))
        
        if cmd.lower() == "help":
            self._cmd_help(output_win)
        elif cmd.lower() == "status":
            self._cmd_status(output_win)
        elif cmd.lower().startswith("pause"):
            self._cmd_pause(output_win)
        elif cmd.lower().startswith("resume"):
            self._cmd_resume(output_win)
        elif cmd.lower() == "stop":
            self._cmd_stop(output_win)
        elif cmd.lower() == "screenshot":
            self._cmd_screenshot(output_win)
        elif cmd.lower().startswith("add-memory"):
            self._cmd_add_memory(output_win, cmd[11:])
        else:
            output_win.addstr(f"Unknown command: {cmd}\n", curses.color_pair(4))
        
        output_win.refresh()
    
    def _cmd_help(self, win):
        """Display help information"""
        win.addstr("Available commands:\n", curses.color_pair(3))
        win.addstr("  help         - Show this help message\n")
        win.addstr("  status       - Show current agent status\n")
        win.addstr("  pause        - Pause the agent at the next safe point\n")
        win.addstr("  resume       - Resume a paused agent\n")
        win.addstr("  stop         - Stop the agent completely\n")
        win.addstr("  screenshot   - Take a screenshot of the current browser\n")
        win.addstr("  add-memory   - Add a memory item to the agent\n")
    
    def _cmd_status(self, win):
        """Display current agent status"""
        if not self.current_agent_id:
            win.addstr("No active agent.\n", curses.color_pair(3))
            return
            
        from .agent_control import agent_control_manager
        
        paused = agent_control_manager.is_paused(self.current_agent_id)
        status = "PAUSED" if paused else "RUNNING"
        
        win.addstr("Current agent status:\n", curses.color_pair(3))
        win.addstr(f"  Agent ID: {self.current_agent_id}\n")
        win.addstr(f"  Status: {status}\n")
        
        # Get command result asynchronously - this is a bit hacky but works for demo
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        cmd = agent_command_manager.add_command(self.current_agent_id, "get_page_info")
        try:
            result = loop.run_until_complete(
                agent_command_manager.wait_for_command(cmd, timeout=2.0)
            )
            
            if result and "error" not in result:
                win.addstr(f"  Current URL: {result.get('url', 'N/A')}\n")
                win.addstr(f"  Page Title: {result.get('title', 'N/A')}\n")
                win.addstr(f"  Open Tabs: {result.get('tabs_count', 0)}\n")
            else:
                win.addstr(f"  Could not get page info: {result.get('error', 'Unknown error')}\n")
        except Exception as e:
            win.addstr(f"  Error getting page info: {str(e)}\n", curses.color_pair(4))
        finally:
            loop.close()
    
    def _cmd_pause(self, win):
        """Pause the agent"""
        if not self.current_agent_id:
            win.addstr("No active agent to pause.\n", curses.color_pair(4))
            return
            
        from .agent_control import agent_control_manager
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            paused = loop.run_until_complete(
                agent_control_manager.pause_agent(self.current_agent_id)