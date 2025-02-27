import sys
import os
import asyncio

# Ensure the parent directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Try importing colorama directly
try:
    from colorama import Fore, Style, init
    init()
    print(f"{Fore.GREEN}Colorama loaded successfully!{Style.RESET_ALL}")
except ImportError:
    print("Colorama not installed. Please run 'pip install colorama'")
    sys.exit(1)

# Now try the full terminal interaction
try:
    from src.utils.terminal_interaction import terminal_handler
    
    async def simple_test():
        print("Asking for confirmation...")
        result = await terminal_handler.request_confirmation(
            "Does this terminal interaction work?",
            "This is a simple test to check if terminal interaction is working properly."
        )
        if result:
            print("You confirmed it works!")
        else:
            print("You indicated it doesn't work.")
    
    # Run the test
    asyncio.run(simple_test())
    
except Exception as e:
    import traceback
    print(f"Error running terminal interaction test: {e}")
    traceback.print_exc()
