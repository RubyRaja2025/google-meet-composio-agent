#!/usr/bin/env python3
"""Discover available Google Meet tools from Composio.

Lists all available tools and their schemas.

Usage:
    python scripts/discover_tools.py
    python scripts/discover_tools.py --full  # Show full schemas
"""

import json
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv

load_dotenv()


def main():
    from composio import Composio

    from google_meet_agent.auth import ensure_google_meet_connection
    from google_meet_agent.tools import get_google_meet_tools, GOOGLEMEET_APP_NAME

    # Get config
    composio_api_key = os.getenv("COMPOSIO_API_KEY")
    entity_id = os.getenv("GOOGLE_MEET_USER_ID", "default")

    if not composio_api_key:
        print("Error: COMPOSIO_API_KEY not set")
        sys.exit(1)

    print("=" * 60)
    print("Google Meet Tool Discovery")
    print("=" * 60)
    print(f"\nApp Name: {GOOGLEMEET_APP_NAME}")
    print(f"Entity ID: {entity_id}")

    # Initialize Composio
    composio = Composio(api_key=composio_api_key)

    # Ensure connection exists
    print("\nEnsuring OAuth connection...")
    try:
        ensure_google_meet_connection(
            composio=composio,
            entity_id=entity_id,
        )
        print("Connection verified!")
    except Exception as e:
        print(f"Warning: Could not verify connection: {e}")
        print("Attempting to discover tools anyway...")

    # Get tools
    print("\nFetching tools...")
    try:
        tools = get_google_meet_tools(composio, entity_id)
    except Exception as e:
        print(f"Error fetching tools: {e}")
        sys.exit(1)

    if not tools:
        print("\nNo tools found!")
        print("This could mean:")
        print("  - OAuth connection is not active")
        print("  - Google Meet app is not available")
        print("  - There's an issue with the Composio configuration")
        sys.exit(1)

    print(f"\nFound {len(tools)} tools:")
    print("-" * 40)

    for i, tool in enumerate(tools, 1):
        name = tool.get("name", "unknown")
        description = tool.get("description", "No description")

        print(f"\n{i}. {name}")
        print(f"   Description: {description[:100]}{'...' if len(description) > 100 else ''}")

        # Show input schema if available
        input_schema = tool.get("input_schema", {})
        if input_schema:
            properties = input_schema.get("properties", {}) or {}
            required = input_schema.get("required", []) or []
            if properties:
                print("   Parameters:")
                for param_name, param_info in list(properties.items())[:5]:  # Show first 5
                    param_type = param_info.get("type", "any")
                    param_desc = param_info.get("description", "")[:50]
                    req = " (required)" if param_name in required else ""
                    print(f"     - {param_name}: {param_type}{req}")
                    if param_desc:
                        print(f"       {param_desc}")
                if len(properties) > 5:
                    print(f"     ... and {len(properties) - 5} more parameters")

    print("\n" + "=" * 60)
    print(f"Total: {len(tools)} tools available")
    print("=" * 60)

    # Optionally dump full schema
    if "--full" in sys.argv:
        print("\n\nFull tool schemas:")
        print(json.dumps(tools, indent=2, default=str))


if __name__ == "__main__":
    main()
