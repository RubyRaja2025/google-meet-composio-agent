#!/usr/bin/env python3
"""Setup OAuth connection for Google Meet via Composio.

This script helps establish the initial OAuth connection. Run it once
to authenticate, then use the agent for queries.

Usage:
    python scripts/setup_connection.py
    python scripts/setup_connection.py --entity-id my-user-123
"""

import argparse
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Set up Google Meet OAuth connection")
    parser.add_argument(
        "--entity-id",
        default=os.getenv("GOOGLE_MEET_USER_ID", "default"),
        help="Entity ID for this connection (default: from env or 'default')",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't auto-open browser (print URL instead)",
    )
    args = parser.parse_args()

    # Import after path setup
    from composio import Composio

    from google_meet_agent.auth import GoogleMeetAuthManager, ensure_google_meet_connection
    from google_meet_agent.exceptions import GoogleMeetAgentError

    # Get config from environment
    composio_api_key = os.getenv("COMPOSIO_API_KEY")

    if not composio_api_key:
        print("Error: COMPOSIO_API_KEY not set")
        print("Get your key from: https://app.composio.dev")
        sys.exit(1)

    print("=" * 60)
    print("Google Meet OAuth Setup")
    print("=" * 60)
    print(f"\nEntity ID: {args.entity_id}")

    # Initialize Composio
    composio = Composio(api_key=composio_api_key)
    auth_manager = GoogleMeetAuthManager(composio)

    # Check for existing connection
    print("\nChecking for existing connection...")
    existing = auth_manager.get_existing_connection(args.entity_id)

    if existing:
        account_id = getattr(existing, "id", None) or getattr(existing, "connectedAccountId", "unknown")
        print(f"\nFound existing active connection!")
        print(f"  Account ID: {account_id}")
        print("\nYou can use this connection with the agent.")
        return

    # No existing connection - set up OAuth
    print("\nNo existing connection found. Starting OAuth flow...")

    try:
        connected_account = ensure_google_meet_connection(
            composio=composio,
            entity_id=args.entity_id,
            open_browser=not args.no_browser,
        )

        account_id = getattr(connected_account, "id", None) or \
                    getattr(connected_account, "connectedAccountId", "unknown")

        print("\n" + "=" * 60)
        print("Connection Successful!")
        print("=" * 60)
        print(f"\nAccount ID: {account_id}")
        print(f"Entity ID: {args.entity_id}")
        print("\nYou can now use the Google Meet agent!")
        print("\nTest with:")
        print("  python scripts/quick_test.py")
        print("  python -m google_meet_agent.cli")

    except GoogleMeetAgentError as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
