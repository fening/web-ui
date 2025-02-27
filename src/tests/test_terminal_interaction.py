import sys
import asyncio
import os

# Add parent directory to path to ensure imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.utils.terminal_interaction import terminal_handler

async def test_login_interaction():
    """Test function to demonstrate terminal login interaction"""
    print("\n==== TERMINAL INTERACTION TEST ====")
    print("This test will show how the terminal interaction appears when requesting login.")
    print("You'll see a colored prompt in your terminal asking for confirmation.\n")
    
    # Simulate a login request to "Example Service"
    service_name = "Example Service"
    url = "https://example.com/login"
    
    print(f"Requesting login to {service_name}...")
    
    # This will trigger the terminal interaction
    result = await terminal_handler.request_login(service_name, url)
    
    if result:
        print(f"\n✅ Login confirmed! The agent would now continue with the task.")
    else:
        print(f"\n❌ Login not confirmed. The agent would wait or try an alternative approach.")

async def test_confirmation_interaction():
    """Test function to demonstrate a simple confirmation prompt"""
    print("\n==== CONFIRMATION INTERACTION TEST ====")
    print("This test shows a simple yes/no confirmation prompt.\n")
    
    # Show a simple confirmation prompt
    result = await terminal_handler.request_confirmation(
        "Do you want to continue with this action?",
        "This is a test to show how confirmation prompts appear in the terminal."
    )
    
    if result:
        print("\n✅ Action confirmed!")
    else:
        print("\n❌ Action declined.")

async def run_tests():
    """Run all terminal interaction tests"""
    # First test a login interaction
    await test_login_interaction()
    
    print("\n" + "-" * 50 + "\n")
    
    # Then test a simple confirmation
    await test_confirmation_interaction()
    
    print("\n==== Tests Complete ====")

if __name__ == "__main__":
    # Run the tests
    asyncio.run(run_tests())
