"""Custom exceptions for the Google Meet agent."""


class GoogleMeetAgentError(Exception):
    """Base exception for Google Meet agent errors."""

    def __init__(self, message: str, cause: Exception | None = None):
        super().__init__(message)
        self.cause = cause


class ConfigurationError(GoogleMeetAgentError):
    """Raised when configuration is invalid or missing."""

    pass


class AuthConfigNotFoundError(GoogleMeetAgentError):
    """Raised when no auth config exists in Composio for Google Meet."""

    def __init__(self, message: str | None = None, cause: Exception | None = None):
        default_msg = (
            "No Google Meet auth config found. Please create one at "
            "https://app.composio.dev (Auth Configs > Create > Google Meet)"
        )
        super().__init__(message or default_msg, cause)


class OAuthTimeoutError(GoogleMeetAgentError):
    """Raised when user doesn't complete OAuth in time."""

    def __init__(self, timeout: int, cause: Exception | None = None):
        message = f"OAuth flow timed out after {timeout} seconds. Please try again."
        super().__init__(message, cause)
        self.timeout = timeout


class ConnectionExpiredError(GoogleMeetAgentError):
    """Raised when the Google Meet connection has expired and needs re-authentication."""

    def __init__(self, message: str | None = None, cause: Exception | None = None):
        default_msg = "Google Meet connection has expired. Please reconnect your account."
        super().__init__(message or default_msg, cause)


class ComposioConnectionError(GoogleMeetAgentError):
    """Raised when connection to Composio fails."""

    pass


class GoogleMeetAPIError(GoogleMeetAgentError):
    """Raised when Google Meet API returns an error."""

    def __init__(
        self, message: str, status_code: int | None = None, cause: Exception | None = None
    ):
        super().__init__(message, cause)
        self.status_code = status_code


class RateLimitError(GoogleMeetAPIError):
    """Raised when Google Meet API rate limit is exceeded (429)."""

    def __init__(
        self,
        message: str | None = None,
        retry_after: int | None = None,
        cause: Exception | None = None,
    ):
        if message is None:
            message = "Google Meet API rate limit exceeded."
            if retry_after:
                message += f" Retry after {retry_after} seconds."
        super().__init__(message, status_code=429, cause=cause)
        self.retry_after = retry_after


class NoConferencesError(GoogleMeetAgentError):
    """Raised when no conferences are found."""

    def __init__(self, message: str | None = None, cause: Exception | None = None):
        default_msg = "No conference records found. You may not have any past meetings, or they may be outside the query range."
        super().__init__(message or default_msg, cause)


class AgentExecutionError(GoogleMeetAgentError):
    """Raised when agent execution fails."""

    pass
