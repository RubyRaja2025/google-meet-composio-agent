"""Google Meet Agent - AI agent for querying Google Meet meetings via Composio.

This agent provides READ-ONLY access to:
- Conference records (past meetings)
- Meeting details (date, time, duration)
- Participants (who attended, join/leave times)
- Transcripts (if enabled during meeting)

Requires Google Workspace account for full API access.
"""

from .agent import GoogleMeetAgent, AgentResponse
from .auth import GoogleMeetAuthManager, ensure_google_meet_connection
from .tools import get_google_meet_tools, execute_google_meet_tool
from .config import Settings, get_settings
from .exceptions import (
    GoogleMeetAgentError,
    ConfigurationError,
    AuthConfigNotFoundError,
    OAuthTimeoutError,
    ConnectionExpiredError,
    ComposioConnectionError,
    GoogleMeetAPIError,
    RateLimitError,
)

__all__ = [
    # Agent
    "GoogleMeetAgent",
    "AgentResponse",
    # Auth
    "GoogleMeetAuthManager",
    "ensure_google_meet_connection",
    # Tools
    "get_google_meet_tools",
    "execute_google_meet_tool",
    # Config
    "Settings",
    "get_settings",
    # Exceptions
    "GoogleMeetAgentError",
    "ConfigurationError",
    "AuthConfigNotFoundError",
    "OAuthTimeoutError",
    "ConnectionExpiredError",
    "ComposioConnectionError",
    "GoogleMeetAPIError",
    "RateLimitError",
]

__version__ = "0.1.0"
