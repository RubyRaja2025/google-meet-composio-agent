#!/usr/bin/env python3
"""Example: Using Google Meet Agent as a sub-agent.

This demonstrates how a supervisor agent can call the Google Meet agent
for meeting-related queries.

Usage:
    python supervisor_example.py
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()


def example_direct_calls():
    """Pattern 1: Direct function calls from supervisor."""
    from google_meet_agent import GoogleMeetAgent

    print("=" * 60)
    print("Pattern 1: Direct Function Calls")
    print("=" * 60)

    # Create the Google Meet agent
    meet_agent = GoogleMeetAgent()

    # Setup (handles OAuth if needed)
    print("\nSetting up Google Meet agent...")
    meet_agent.setup()
    print("Agent ready!\n")

    # Supervisor can now call the agent for meeting-related tasks
    queries = [
        "List my recent meetings",
        "How many meetings did I have this week?",
    ]

    for query in queries:
        print(f"\n[Supervisor] Delegating query: '{query}'")
        print("-" * 40)

        response = meet_agent.query(query)

        if response.success:
            print(f"[Meet Agent] {response.data}")
        else:
            print(f"[Meet Agent] Error: {response.error}")


def example_as_tool():
    """Pattern 2: Wrapping agent as a callable tool."""
    from google_meet_agent import GoogleMeetAgent

    print("\n" + "=" * 60)
    print("Pattern 2: Agent as Tool Wrapper")
    print("=" * 60)

    # Create and setup agent
    meet_agent = GoogleMeetAgent()
    meet_agent.setup()

    # Wrap as a tool function that supervisor can call
    def google_meet_tool(query: str) -> str:
        """Tool for querying Google Meet meetings.

        Args:
            query: Natural language query about meetings.

        Returns:
            String response with meeting information.
        """
        response = meet_agent.query(query)
        if response.success:
            return response.data or "No data returned"
        else:
            return f"Error: {response.error}"

    # Supervisor can now use this as a tool
    print("\n[Supervisor] Using Google Meet tool...")

    result = google_meet_tool("Show me who attended my most recent meeting")
    print(f"\n[Tool Result]\n{result}")


def example_convenience_methods():
    """Pattern 3: Using convenience methods for common operations."""
    from google_meet_agent import GoogleMeetAgent

    print("\n" + "=" * 60)
    print("Pattern 3: Convenience Methods")
    print("=" * 60)

    # Create and setup agent
    meet_agent = GoogleMeetAgent()
    meet_agent.setup()

    # Use convenience methods for common operations
    print("\n[Supervisor] Getting list of conferences...")
    response = meet_agent.list_conferences(limit=5)

    if response.success:
        print(f"\n[Result]\n{response.data}")
    else:
        print(f"Error: {response.error}")

    # If you have a specific conference ID, you can query it directly:
    # response = meet_agent.get_participants("conferenceRecords/abc123")
    # response = meet_agent.get_transcript("conferenceRecords/abc123")


def main():
    """Run all examples."""
    print("\n" + "#" * 60)
    print("# Google Meet Agent - Supervisor Integration Examples")
    print("#" * 60)

    try:
        # Pattern 1: Direct calls
        example_direct_calls()

        # Pattern 2: As tool
        example_as_tool()

        # Pattern 3: Convenience methods
        example_convenience_methods()

        print("\n" + "=" * 60)
        print("All examples completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
