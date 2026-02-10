"""Google Meet agent with Claude for natural language queries."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import anthropic
from composio import Composio

from .auth import ensure_google_meet_connection
from .config import Settings, get_settings
from .exceptions import (
    AgentExecutionError,
    ComposioConnectionError,
    ConfigurationError,
    GoogleMeetAgentError,
)
from .tools import get_google_meet_tools, execute_google_meet_tool

logger = logging.getLogger(__name__)

def get_system_prompt() -> str:
    """Generate system prompt with current date context."""
    current_date = datetime.now().strftime("%B %d, %Y")
    current_year = datetime.now().year
    current_weekday = datetime.now().strftime("%A")

    return f"""You are a Google Meet Assistant agent. You help users query their past Google Meet meetings to retrieve meeting details, attendees, transcripts, and Gemini-generated notes.

CURRENT DATE CONTEXT:
- Today's date is: {current_weekday}, {current_date}
- Current year is: {current_year}
- Use this as reference for "today", "this week", "this month", "this year", "recent", etc.

You have access to Google Meet tools that can:
- List past conference records (meetings that have occurred)
- Get details about specific conferences (date, time, duration)
- List participants who attended meetings
- Get participant session details (join/leave times)
- Retrieve meeting transcripts (if enabled during the meeting)
- Search Google Drive for Gemini-generated meeting notes

You also have access to Google Drive tools to:
- Search for meeting notes documents created by Gemini (use GOOGLEDRIVE_LIST_FILES)
- Download and read the content of documents (use GOOGLEDRIVE_DOWNLOAD_FILE with mime_type="text/plain")

HOW TO GET GEMINI MEETING NOTES:
1. Search: Use GOOGLEDRIVE_LIST_FILES with query like: name contains "Notes by Gemini"
2. Download: Use GOOGLEDRIVE_DOWNLOAD_FILE with the file_id and mime_type="text/plain"
3. The file_content field in the response contains the actual notes text - display this to the user

IMPORTANT CONCEPTS:
- A "space" is the meeting room itself (has a meeting code like abc-defg-hij)
- A "conference record" is a record of an actual meeting that happened in a space
- Participants are people who joined a conference
- Transcripts are only available if someone enabled them during the meeting
- Gemini notes are saved as Google Docs in the user's Drive (search for "Meeting notes" documents)

When responding to queries:
1. Use the appropriate tool to fetch the requested data
2. Present the information in a clear, organized format
3. For listing meetings, show: meeting code, date/time, duration
4. For participants, show: display name, email (if available), join/leave times
5. For transcripts, include speaker names and timestamps when available
6. For Gemini notes, search Google Drive for documents titled "Meeting notes" or containing the meeting code

You can handle queries like:
- "Show me my recent meetings" or "List my past conferences"
- "Who attended the meeting with code abc-defg-hij?"
- "Get the transcript from my last meeting"
- "What meetings did I have this week?"
- "Show me details for meeting XYZ"
- "Get the Gemini notes from my last meeting"
- "Find meeting notes from today"

LIMITATIONS:
- This is a READ-ONLY agent - cannot create or modify meetings
- Cannot access live/ongoing meetings in real-time
- Transcripts require someone to have enabled them during the meeting
- Transcript entries only available for 30 days after meeting
- Gemini notes require user to have enabled "Take notes for me" during the meeting
- Requires Google Workspace account
"""


@dataclass
class AgentResponse:
    """Structured response from the agent."""

    success: bool
    data: str | None
    error: str | None
    raw_response: Any = None


class GoogleMeetAgent:
    """AI agent for querying Google Meet meetings via Composio."""

    def __init__(
        self,
        composio_api_key: str | None = None,
        anthropic_api_key: str | None = None,
        entity_id: str | None = None,
        settings: Settings | None = None,
    ):
        """Initialize the Google Meet agent.

        Args:
            composio_api_key: Composio API key (or from settings/env).
            anthropic_api_key: Anthropic API key (or from settings/env).
            entity_id: Entity ID for this user (or from settings/env).
            settings: Optional settings override.

        Raises:
            ConfigurationError: If required settings are missing.
        """
        self._settings = settings or get_settings()

        # Override settings with explicit parameters
        self._composio_api_key = composio_api_key or self._settings.composio_api_key
        self._anthropic_api_key = anthropic_api_key or self._settings.anthropic_api_key
        self._entity_id = entity_id or self._settings.google_meet_user_id

        # Lazy-initialized clients
        self._composio: Composio | None = None
        self._anthropic_client: anthropic.Anthropic | None = None
        self._tools: list[dict[str, Any]] | None = None
        self._is_setup = False

        self._validate_settings()

    def _validate_settings(self) -> None:
        """Validate required settings are present."""
        if not self._composio_api_key:
            raise ConfigurationError(
                "COMPOSIO_API_KEY is required. Get one from https://app.composio.dev"
            )
        if not self._anthropic_api_key:
            raise ConfigurationError(
                "ANTHROPIC_API_KEY is required. Get one from https://console.anthropic.com"
            )

    @property
    def entity_id(self) -> str:
        """Get the entity ID for this agent."""
        return self._entity_id

    @property
    def is_setup(self) -> bool:
        """Check if the agent has been set up."""
        return self._is_setup

    def setup(self, open_browser: bool = True) -> None:
        """Set up the agent: authenticate and load tools.

        This must be called before making queries.

        Args:
            open_browser: Whether to auto-open browser for OAuth.

        Raises:
            AuthConfigNotFoundError: If Google Meet integration not found.
            OAuthTimeoutError: If OAuth times out.
        """
        if self._is_setup:
            logger.info("Agent already set up, skipping")
            return

        logger.info(f"Setting up Google Meet agent for entity: {self._entity_id}")

        # Initialize Composio client
        self._composio = Composio(api_key=self._composio_api_key)

        # Ensure Google Meet connection (OAuth if needed)
        ensure_google_meet_connection(
            composio=self._composio,
            entity_id=self._entity_id,
            timeout=self._settings.oauth_timeout,
            open_browser=open_browser,
        )

        # Load tools
        self._tools = get_google_meet_tools(
            composio=self._composio,
            entity_id=self._entity_id,
        )

        # Initialize Anthropic client
        self._anthropic_client = anthropic.Anthropic(
            api_key=self._anthropic_api_key,
        )

        self._is_setup = True
        logger.info(f"Agent setup complete. Loaded {len(self._tools)} tools.")

    def _ensure_setup(self) -> None:
        """Ensure agent is set up before operations."""
        if not self._is_setup:
            self.setup()

    def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Execute a tool and return result as string.

        Args:
            tool_name: Name of the tool to execute.
            tool_input: Tool input parameters.

        Returns:
            JSON string of the result.
        """
        try:
            result = execute_google_meet_tool(
                composio=self._composio,
                entity_id=self._entity_id,
                tool_slug=tool_name,
                arguments=tool_input,
            )
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return json.dumps({
                "error": str(type(e).__name__),
                "message": str(e),
            })

    def _run_agent_loop(self, prompt: str, max_turns: int) -> str:
        """Run the agent loop with tool calling.

        Args:
            prompt: User's query.
            max_turns: Maximum conversation turns.

        Returns:
            Final text response from the agent.
        """
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

        for turn in range(max_turns):
            logger.debug(f"Agent turn {turn + 1}/{max_turns}")

            # Call Claude with tools
            response = self._anthropic_client.messages.create(
                model=self._settings.model_name,
                max_tokens=4096,
                system=get_system_prompt(),
                tools=self._tools,
                messages=messages,
            )

            logger.debug(f"Response stop_reason: {response.stop_reason}")

            # Check if we need to handle tool calls
            if response.stop_reason == "tool_use":
                # Add assistant's response to messages
                messages.append({"role": "assistant", "content": response.content})

                # Execute each tool call
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        logger.debug(f"Executing tool: {block.name}")
                        result = self._execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                # Add tool results to messages
                messages.append({"role": "user", "content": tool_results})
                logger.debug(f"Executed {len(tool_results)} tool calls")

            elif response.stop_reason == "end_turn":
                # Extract text response
                text_blocks = [
                    block.text for block in response.content if hasattr(block, "text")
                ]
                return "\n".join(text_blocks) if text_blocks else ""

            else:
                logger.warning(f"Unexpected stop_reason: {response.stop_reason}")
                break

        return "Max turns reached without completing the task."

    def query(self, user_message: str, max_turns: int | None = None) -> AgentResponse:
        """Send a natural language query to the agent.

        Args:
            user_message: The query to send.
            max_turns: Optional max turns override.

        Returns:
            AgentResponse with success status and data/error.
        """
        self._ensure_setup()
        max_turns = max_turns or self._settings.agent_max_turns
        logger.info(f"Query: {user_message[:100]}...")

        try:
            result = self._run_agent_loop(user_message, max_turns)

            logger.info("Query completed successfully")
            return AgentResponse(
                success=True,
                data=result,
                error=None,
                raw_response=result,
            )

        except GoogleMeetAgentError as e:
            logger.error(f"Agent error: {e}")
            return AgentResponse(
                success=False,
                data=None,
                error=str(e),
                raw_response=None,
            )
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            return AgentResponse(
                success=False,
                data=None,
                error=f"Claude API error: {e}",
                raw_response=None,
            )
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return AgentResponse(
                success=False,
                data=None,
                error=f"Unexpected error: {e}",
                raw_response=None,
            )

    # =========================================================================
    # Convenience Methods (READ-ONLY)
    # =========================================================================

    def list_conferences(self, limit: int = 20) -> AgentResponse:
        """List recent conference records (past meetings).

        Args:
            limit: Maximum number of conferences to return.

        Returns:
            AgentResponse with list of conferences.
        """
        return self.query(
            f"List my {limit} most recent Google Meet conferences. "
            f"For each, show the meeting code, date/time, and duration."
        )

    def get_conference(self, conference_id: str) -> AgentResponse:
        """Get details for a specific conference.

        Args:
            conference_id: The conference record ID or meeting code.

        Returns:
            AgentResponse with conference details.
        """
        return self.query(
            f"Get full details for Google Meet conference: {conference_id}"
        )

    def get_participants(self, conference_id: str) -> AgentResponse:
        """Get participants for a specific conference.

        Args:
            conference_id: The conference record ID or meeting code.

        Returns:
            AgentResponse with participant list.
        """
        return self.query(
            f"List all participants who attended Google Meet conference: {conference_id}. "
            f"Include their names, emails (if available), and join/leave times."
        )

    def get_transcript(self, conference_id: str) -> AgentResponse:
        """Get the transcript for a conference.

        Args:
            conference_id: The conference record ID or meeting code.

        Returns:
            AgentResponse with transcript content.
        """
        return self.query(
            f"Get the full transcript for Google Meet conference: {conference_id}. "
            f"Include speaker names and timestamps."
        )

    def list_available_tools(self) -> list[dict[str, str]]:
        """List all available Google Meet tools.

        Returns:
            List of tool info dicts with name and description.
        """
        self._ensure_setup()

        result = []
        for tool in self._tools or []:
            name = tool.get("name", "unknown")
            description = tool.get("description", "No description")
            if len(description) > 100:
                description = description[:97] + "..."
            result.append({"name": name, "description": description})
        return result
