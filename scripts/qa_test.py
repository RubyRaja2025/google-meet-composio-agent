#!/usr/bin/env python3
"""QA Test Script for Google Meet Agent.

This script tests all functionality of the Google Meet agent.
Run this to verify the agent is working correctly.

Usage:
    python scripts/qa_test.py
"""

import os
import sys
import json
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()


def print_header(text: str):
    print("\n" + "=" * 60)
    print(f" {text}")
    print("=" * 60)


def print_test(name: str, passed: bool, details: str = ""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\n{status}: {name}")
    if details:
        print(f"   Details: {details[:200]}{'...' if len(details) > 200 else ''}")


def main():
    from composio import Composio
    from composio.client.enums import Action

    from google_meet_agent import GoogleMeetAgent, ConfigurationError
    from google_meet_agent.auth import GoogleMeetAuthManager
    from google_meet_agent.tools import get_google_meet_tools, execute_google_meet_tool, get_connected_account_id

    print_header("Google Meet Agent - QA Test Suite")
    print(f"Timestamp: {datetime.now().isoformat()}")

    results = {
        "passed": 0,
        "failed": 0,
        "tests": []
    }

    def record_test(name: str, passed: bool, details: str = ""):
        print_test(name, passed, details)
        results["tests"].append({"name": name, "passed": passed, "details": details})
        if passed:
            results["passed"] += 1
        else:
            results["failed"] += 1

    # ==========================================================================
    # Test 1: Environment Configuration
    # ==========================================================================
    print_header("Test 1: Environment Configuration")

    composio_key = os.getenv("COMPOSIO_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    record_test(
        "COMPOSIO_API_KEY is set",
        bool(composio_key),
        f"Key length: {len(composio_key) if composio_key else 0}"
    )

    record_test(
        "ANTHROPIC_API_KEY is set",
        bool(anthropic_key),
        f"Key length: {len(anthropic_key) if anthropic_key else 0}"
    )

    if not composio_key or not anthropic_key:
        print("\n❌ Missing required API keys. Cannot continue.")
        return

    # ==========================================================================
    # Test 2: Composio Client Initialization
    # ==========================================================================
    print_header("Test 2: Composio Client Initialization")

    try:
        composio = Composio(api_key=composio_key)
        record_test("Composio client created", True)
    except Exception as e:
        record_test("Composio client created", False, str(e))
        return

    # ==========================================================================
    # Test 3: Google Meet Integration Discovery
    # ==========================================================================
    print_header("Test 3: Google Meet Integration Discovery")

    try:
        integrations = composio.integrations.get()
        googlemeet_integ = None
        for integ in integrations:
            if integ.appName == "googlemeet":
                googlemeet_integ = integ
                break

        record_test(
            "Google Meet integration found",
            googlemeet_integ is not None,
            f"Integration ID: {googlemeet_integ.id if googlemeet_integ else 'Not found'}"
        )
    except Exception as e:
        record_test("Google Meet integration found", False, str(e))

    # ==========================================================================
    # Test 4: OAuth Connection Status
    # ==========================================================================
    print_header("Test 4: OAuth Connection Status")

    entity_id = os.getenv("GOOGLE_MEET_USER_ID", "default")

    try:
        auth_manager = GoogleMeetAuthManager(composio)
        existing = auth_manager.get_existing_connection(entity_id)

        record_test(
            f"Active connection for entity '{entity_id}'",
            existing is not None,
            f"Account ID: {existing.id if existing else 'No connection'}"
        )

        if not existing:
            print("\n⚠️  No active connection. Run: python scripts/setup_connection.py")
    except Exception as e:
        record_test("OAuth connection check", False, str(e))

    # ==========================================================================
    # Test 5: Tool Discovery
    # ==========================================================================
    print_header("Test 5: Tool Discovery")

    try:
        tools = get_google_meet_tools(composio, entity_id)

        record_test(
            "Tools discovered",
            len(tools) > 0,
            f"Found {len(tools)} tools"
        )

        # Check for expected tools
        tool_names = [t.get("name", "") for t in tools]
        expected_tools = [
            "GOOGLEMEET_LIST_CONFERENCE_RECORDS",
            "GOOGLEMEET_GET_CONFERENCE_RECORD_FOR_MEET",
            "GOOGLEMEET_CREATE_MEET",
        ]

        for expected in expected_tools:
            found = expected in tool_names
            record_test(f"Tool '{expected}' available", found)

    except Exception as e:
        record_test("Tool discovery", False, str(e))

    # ==========================================================================
    # Test 6: Connected Account ID Retrieval
    # ==========================================================================
    print_header("Test 6: Connected Account ID")

    try:
        acc_id = get_connected_account_id(composio, entity_id)
        record_test(
            "Connected account ID retrieved",
            acc_id is not None,
            f"Account ID: {acc_id}"
        )
    except Exception as e:
        record_test("Connected account ID", False, str(e))

    # ==========================================================================
    # Test 7: Direct Tool Execution - List Conferences
    # ==========================================================================
    print_header("Test 7: Direct Tool Execution - List Conferences")

    try:
        result = execute_google_meet_tool(
            composio=composio,
            entity_id=entity_id,
            tool_slug="GOOGLEMEET_LIST_CONFERENCE_RECORDS",
            arguments={}
        )

        record_test(
            "List conferences executed successfully",
            result.get("success", False),
            f"Data: {json.dumps(result.get('data', {}))[:150]}"
        )
    except Exception as e:
        record_test("List conferences execution", False, str(e))

    # ==========================================================================
    # Test 8: Direct Tool Execution - Create Meeting
    # ==========================================================================
    print_header("Test 8: Direct Tool Execution - Create Meeting")

    created_meeting = None
    try:
        result = execute_google_meet_tool(
            composio=composio,
            entity_id=entity_id,
            tool_slug="GOOGLEMEET_CREATE_MEET",
            arguments={}
        )

        success = result.get("success", False)
        data = result.get("data", {})

        # Extract meeting info
        if isinstance(data, dict):
            meeting_code = data.get("meetingCode", "")
            meeting_uri = data.get("meetingUri", "")
            space_name = data.get("name", "")
            created_meeting = {
                "code": meeting_code,
                "uri": meeting_uri,
                "name": space_name
            }

        record_test(
            "Create meeting executed successfully",
            success,
            f"Meeting Code: {created_meeting.get('code') if created_meeting else 'N/A'}, URI: {created_meeting.get('uri') if created_meeting else 'N/A'}"
        )

        if created_meeting and created_meeting.get("uri"):
            print(f"\n   🔗 Join URL: {created_meeting['uri']}")

    except Exception as e:
        record_test("Create meeting execution", False, str(e))

    # ==========================================================================
    # Test 9: Agent Initialization
    # ==========================================================================
    print_header("Test 9: Agent Initialization")

    try:
        agent = GoogleMeetAgent()
        record_test("Agent created", True)
    except ConfigurationError as e:
        record_test("Agent created", False, str(e))
        return
    except Exception as e:
        record_test("Agent created", False, str(e))
        return

    # ==========================================================================
    # Test 10: Agent Setup
    # ==========================================================================
    print_header("Test 10: Agent Setup")

    try:
        agent.setup(open_browser=False)
        record_test("Agent setup completed", True, f"Loaded {len(agent._tools)} tools")
    except Exception as e:
        record_test("Agent setup", False, str(e))

    # ==========================================================================
    # Test 11: Agent Query - List Meetings
    # ==========================================================================
    print_header("Test 11: Agent Query - List Meetings")

    try:
        response = agent.query("List my Google Meet conferences")
        record_test(
            "Agent query executed",
            response.success,
            response.data[:200] if response.data else response.error
        )
    except Exception as e:
        record_test("Agent query", False, str(e))

    # ==========================================================================
    # Test 12: Agent Query - With Created Meeting
    # ==========================================================================
    if created_meeting and created_meeting.get("code"):
        print_header("Test 12: Agent Query - Get Meeting Details")

        try:
            response = agent.query(f"Get details for the meeting with code {created_meeting['code']}")
            record_test(
                "Get meeting details query",
                response.success,
                response.data[:200] if response.data else response.error
            )
        except Exception as e:
            record_test("Get meeting details query", False, str(e))
    else:
        print_header("Test 12: Skipped (no meeting created)")

    # ==========================================================================
    # Test 13: Convenience Methods
    # ==========================================================================
    print_header("Test 13: Convenience Methods")

    try:
        response = agent.list_conferences(limit=5)
        record_test(
            "list_conferences() method",
            response.success,
            f"Success: {response.success}"
        )
    except Exception as e:
        record_test("list_conferences() method", False, str(e))

    # ==========================================================================
    # Test 14: Available Tools List
    # ==========================================================================
    print_header("Test 14: Available Tools List")

    try:
        tools = agent.list_available_tools()
        record_test(
            "list_available_tools() method",
            len(tools) > 0,
            f"Found {len(tools)} tools"
        )
    except Exception as e:
        record_test("list_available_tools() method", False, str(e))

    # ==========================================================================
    # Summary
    # ==========================================================================
    print_header("QA Test Summary")

    total = results["passed"] + results["failed"]
    print(f"\nTotal Tests: {total}")
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"Success Rate: {(results['passed']/total*100):.1f}%")

    if created_meeting and created_meeting.get("uri"):
        print(f"\n📋 Created Test Meeting:")
        print(f"   Code: {created_meeting.get('code')}")
        print(f"   Join: {created_meeting.get('uri')}")
        print(f"\n   To test with real data:")
        print(f"   1. Join this meeting in your browser")
        print(f"   2. Stay for a minute, then leave")
        print(f"   3. Wait 1-2 minutes")
        print(f"   4. Run: python scripts/quick_test.py")

    if results["failed"] > 0:
        print("\n⚠️  Some tests failed. Check the details above.")
        return 1
    else:
        print("\n✅ All tests passed!")
        return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
