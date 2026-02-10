#!/usr/bin/env python3
"""Quick test script for the Google Meet agent.

Tests basic functionality after OAuth setup.

Usage:
    python scripts/quick_test.py
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv

load_dotenv()


def main():
    from google_meet_agent import GoogleMeetAgent, ConfigurationError, GoogleMeetAgentError

    print("=" * 60)
    print("Google Meet Agent - Quick Test")
    print("=" * 60)

    # Create agent
    try:
        agent = GoogleMeetAgent()
    except ConfigurationError as e:
        print(f"\nConfiguration Error: {e}")
        print("\nCheck your .env file has all required variables.")
        sys.exit(1)

    # Setup (handles OAuth if needed)
    print("\n[Setup] Initializing agent...")
    try:
        agent.setup()
        print("Agent setup complete!")
    except GoogleMeetAgentError as e:
        print(f"\nSetup Error: {e}")
        sys.exit(1)

    # Test 1: List available tools
    print("\n" + "-" * 40)
    print("[Test 1] Listing available tools...")
    tools = agent.list_available_tools()
    if tools:
        print(f"Found {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool['name']}")
    else:
        print("No tools found - this may indicate a problem.")

    # Test 2: List conferences
    print("\n" + "-" * 40)
    print("[Test 2] Listing recent conferences...")
    response = agent.list_conferences(limit=5)
    if response.success:
        print("Success!")
        if response.data:
            # Truncate long output
            data = response.data
            if len(data) > 1500:
                data = data[:1500] + "\n... (truncated)"
            print(data)
        else:
            print("No conferences found (you may not have any recent meetings).")
    else:
        print(f"Error: {response.error}")

    # Test 3: Custom query
    print("\n" + "-" * 40)
    print("[Test 3] Running custom query...")
    query = "What Google Meet meetings do I have? Give me a brief summary."
    print(f"Query: {query}")
    response = agent.query(query)
    if response.success:
        print("Success!")
        if response.data:
            data = response.data
            if len(data) > 1500:
                data = data[:1500] + "\n... (truncated)"
            print(data)
    else:
        print(f"Error: {response.error}")

    print("\n" + "=" * 60)
    print("Tests complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("  - Run the interactive CLI: python -m google_meet_agent.cli")
    print("  - Use in your code: from google_meet_agent import GoogleMeetAgent")


if __name__ == "__main__":
    main()
