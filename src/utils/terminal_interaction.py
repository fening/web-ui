import asyncio
import sys
import logging
from colorama import Fore, Style, init
import traceback

# Initialize colorama for cross-platform colored terminal output
init()

logger = logging.getLogger(__name__)

class TerminalInteractionHandler:
    """Handles user interactions via terminal input"""
    
    @staticmethod
    async def request_confirmation(prompt, description=""):
        """
        Request a yes/no confirmation from the user via terminal
        
        Args:
            prompt: The main question text
            description: Additional details
            
        Returns:
            bool: True if user confirmed (yes), False otherwise
        """
        # Print the request with nice formatting
        print(f"\n{Fore.CYAN}╔{'═' * 78}╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║ {Fore.YELLOW}AGENT NEEDS YOUR HELP {Fore.CYAN}{' ' * 58}║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╠{'═' * 78}╣{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║ {Fore.WHITE}{prompt}{' ' * (77 - len(prompt))}║{Style.RESET_ALL}")
        
        if description:
            # Word wrap description if needed
            words = description.split()
            lines = []
            current_line = ""
            
            for word in words:
                if len(current_line) + len(word) + 1 > 74:  # +1 for space
                    lines.append(current_line)
                    current_line = word
                else:
                    current_line += " " + word if current_line else word
            
            if current_line:
                lines.append(current_line)
                
            for line in lines:
                print(f"{Fore.CYAN}║ {Fore.LIGHTBLUE_EX}{line}{' ' * (77 - len(line))}║{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}╠{'═' * 78}╣{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║ {Fore.GREEN}Have you completed this action? (yes/no): {' ' * 42}║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚{'═' * 78}╝{Style.RESET_ALL}")
        
        # Get user input in a non-blocking way
        response = await get_terminal_input()
        
        # Check response
        if response.lower().strip() in ['yes', 'y', 'true', 't', '1']:
            print(f"{Fore.GREEN}✓ Confirmed! Continuing with the task...{Style.RESET_ALL}")
            return True
        else:
            print(f"{Fore.YELLOW}✗ Action not completed. Please try again when ready.{Style.RESET_ALL}")
            return False
    
    @staticmethod 
    async def request_login(service_name, url):
        """
        Ask the user to perform a login and confirm when done
        
        Args:
            service_name: Name of the service to log into
            url: The login page URL
            
        Returns:
            bool: True if user completed login, False otherwise
        """
        description = (
            f"The agent needs you to sign in to {service_name} to continue.\n\n"
            f"Steps:\n"
            f"1. Enter your credentials in the browser window\n"
            f"2. Complete the login process\n"
            f"3. Type 'yes' below when you've finished logging in"
        )
        
        return await TerminalInteractionHandler.request_confirmation(
            f"Please login to {service_name}",
            description
        )

async def get_terminal_input():
    """Get user input from terminal without blocking the event loop"""
    # Create a future that will be set when input is available
    loop = asyncio.get_event_loop()
    future = loop.create_future()
    
    def _get_input():
        try:
            result = input()
            if not future.cancelled():
                loop.call_soon_threadsafe(future.set_result, result)
        except (EOFError, KeyboardInterrupt) as e:
            if not future.cancelled():
                loop.call_soon_threadsafe(future.set_exception, e)
        except Exception as e:
            print(f"Error getting input: {e}")
            traceback.print_exc()
            if not future.cancelled():
                loop.call_soon_threadsafe(future.set_exception, e)
    
    # Run input operation in a separate thread to not block the event loop
    try:
        await loop.run_in_executor(None, _get_input)
        return await future
    except Exception as e:
        print(f"Input error: {e}")
        return "no"  # Default to "no" on error

# Singleton instance
terminal_handler = TerminalInteractionHandler()
