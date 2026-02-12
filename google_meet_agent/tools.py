"""Tool fetching and execution for Google Meet and Google Drive via Composio."""

import logging
from typing import Any

from composio import Composio
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .exceptions import (
    ComposioConnectionError,
    GoogleMeetAPIError,
    RateLimitError,
)

logger = logging.getLogger(__name__)

# App names in Composio
GOOGLEMEET_APP_NAME = "googlemeet"
GOOGLEDRIVE_APP_NAME = "googledrive"


def _is_new_sdk(composio: Composio) -> bool:
    """Check if using new SDK (v0.8+) based on available attributes."""
    return hasattr(composio, 'tools') and not hasattr(composio, 'actions')

# Expected Google Meet tools (READ-ONLY subset)
EXPECTED_MEET_TOOLS = [
    "GOOGLEMEET_LIST_CONFERENCE_RECORDS",
    "GOOGLEMEET_GET_CONFERENCE_RECORD",
    "GOOGLEMEET_LIST_PARTICIPANT_SESSIONS",
    "GOOGLEMEET_GET_PARTICIPANT_SESSION",
    "GOOGLEMEET_GET_TRANSCRIPTS_BY_CONFERENCE_RECORD_ID",
]

# Google Drive tools for fetching Gemini meeting notes
GOOGLEDRIVE_TOOLS_FOR_NOTES = [
    "GOOGLEDRIVE_LIST_FILES",        # Search for meeting notes documents
    "GOOGLEDRIVE_DOWNLOAD_FILE",     # Read file content (returns S3 URL)
    "GOOGLEDRIVE_GET_FILE_METADATA", # Get file details
]


def fetch_file_content_from_url(url: str, timeout: int = 30) -> str:
    """Fetch file content from a temporary S3/CDN URL.

    Args:
        url: The temporary URL to fetch content from.
        timeout: Request timeout in seconds.

    Returns:
        The file content as text.
    """
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GoogleMeetAgent/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content = response.read()
            # Try to decode as UTF-8
            try:
                return content.decode("utf-8")
            except UnicodeDecodeError:
                return content.decode("latin-1")
    except urllib.error.URLError as e:
        logger.error(f"Failed to fetch URL content: {e}")
        return f"Error fetching content: {e}"
    except Exception as e:
        logger.error(f"Error fetching URL: {e}")
        return f"Error: {e}"


def _extract_tool_list(tools: Any) -> list:
    """Extract tool list from various response formats."""
    if hasattr(tools, "items"):
        return tools.items
    elif hasattr(tools, "data"):
        return tools.data
    elif isinstance(tools, list):
        return tools
    else:
        return list(tools) if hasattr(tools, "__iter__") else []


def _get_tool_name(tool: Any) -> str:
    """Extract tool name from various formats."""
    if isinstance(tool, dict):
        # New SDK format: {'function': {'name': '...'}, 'type': 'function'}
        if "function" in tool and isinstance(tool["function"], dict):
            return tool["function"].get("name", "")
        # Old SDK format: {'name': '...'}
        return tool.get("name", "")
    elif hasattr(tool, "name"):
        return tool.name
    return str(tool)


def _tool_to_anthropic(tool: Any) -> dict[str, Any]:
    """Convert a single tool to Anthropic format."""
    if isinstance(tool, dict):
        # New SDK returns tools already in Anthropic format with 'function' key
        if "function" in tool and isinstance(tool["function"], dict):
            func = tool["function"]
            return {
                "name": func.get("name", "unknown"),
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
            }
        # Old SDK format - convert directly
        return _convert_to_anthropic_format(tool)
    elif hasattr(tool, "model_dump"):
        return _convert_to_anthropic_format(tool.model_dump())
    elif hasattr(tool, "to_dict"):
        return _convert_to_anthropic_format(tool.to_dict())
    elif hasattr(tool, "__dict__"):
        return _convert_to_anthropic_format(tool.__dict__)
    else:
        return {"name": str(tool), "description": "", "input_schema": {"type": "object", "properties": {}}}


def _get_tools_for_app(composio: Composio, app_name: str, entity_id: str) -> Any:
    """Get tools for an app, handling both old and new SDK versions."""
    if _is_new_sdk(composio):
        # New SDK: use composio.tools.get() with toolkits parameter
        return composio.tools.get(
            user_id=entity_id,
            toolkits=[app_name],
        )
    else:
        # Old SDK: use composio.actions.get() with apps parameter
        return composio.actions.get(apps=[app_name])


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(ComposioConnectionError),
    reraise=True,
)
def get_google_meet_tools(
    composio: Composio,
    entity_id: str,
    include_drive: bool = True,
) -> list[dict[str, Any]]:
    """Fetch Google Meet and optionally Google Drive tools from Composio.

    Args:
        composio: Initialized Composio client.
        entity_id: Entity ID for tool context.
        include_drive: Whether to include Google Drive tools for Gemini notes.

    Returns:
        List of tool definitions in Anthropic-compatible format.

    Raises:
        ComposioConnectionError: If fetching tools fails.
    """
    try:
        logger.info(f"Fetching Google Meet tools for entity: {entity_id}")
        anthropic_tools = []

        # Get Google Meet tools
        meet_tools = _get_tools_for_app(composio, GOOGLEMEET_APP_NAME, entity_id)
        meet_tool_list = _extract_tool_list(meet_tools)

        meet_tool_names = []
        for tool in meet_tool_list:
            name = _get_tool_name(tool)
            if name:
                meet_tool_names.append(name)
            anthropic_tools.append(_tool_to_anthropic(tool))

        logger.info(f"Discovered {len(meet_tool_names)} Google Meet tools: {meet_tool_names}")

        # Get Google Drive tools for Gemini notes (filtered subset)
        if include_drive:
            try:
                drive_tools = _get_tools_for_app(composio, GOOGLEDRIVE_APP_NAME, entity_id)
                drive_tool_list = _extract_tool_list(drive_tools)

                drive_tool_names = []
                for tool in drive_tool_list:
                    name = _get_tool_name(tool)
                    # Only include specific Drive tools needed for notes
                    if name and name in GOOGLEDRIVE_TOOLS_FOR_NOTES:
                        drive_tool_names.append(name)
                        anthropic_tools.append(_tool_to_anthropic(tool))

                logger.info(f"Discovered {len(drive_tool_names)} Google Drive tools for notes: {drive_tool_names}")

            except Exception as e:
                logger.warning(f"Could not fetch Google Drive tools (Drive integration may not be set up): {e}")

        return anthropic_tools

    except Exception as e:
        logger.error(f"Failed to fetch tools: {e}")
        raise ComposioConnectionError(
            f"Failed to fetch tools: {e}",
            cause=e,
        )


def _convert_to_anthropic_format(tool: dict[str, Any]) -> dict[str, Any]:
    """Convert a Composio tool to Anthropic format.

    Args:
        tool: Tool definition from Composio.

    Returns:
        Tool in Anthropic format.
    """
    # Get the tool name
    name = tool.get("name") or tool.get("slug") or tool.get("action") or "unknown"

    # Get description
    description = tool.get("description") or tool.get("desc") or ""

    # Get input schema
    input_schema = tool.get("input_schema") or tool.get("inputSchema") or tool.get("parameters") or {}

    # Ensure input_schema has required fields
    if not isinstance(input_schema, dict):
        input_schema = {"type": "object", "properties": {}}
    if "type" not in input_schema:
        input_schema["type"] = "object"
    if "properties" not in input_schema:
        input_schema["properties"] = {}

    return {
        "name": name,
        "description": description,
        "input_schema": input_schema,
    }


def list_available_tools(tools: list[dict[str, Any]]) -> list[dict[str, str]]:
    """List available tools with names and descriptions.

    Args:
        tools: List of tool definitions.

    Returns:
        List of dicts with name and description.
    """
    result = []
    for tool in tools:
        name = tool.get("name", "unknown")
        description = tool.get("description", "No description")
        # Truncate long descriptions
        if len(description) > 100:
            description = description[:97] + "..."
        result.append({"name": name, "description": description})
    return result


def get_connected_account_id(
    composio: Composio,
    entity_id: str,
    app_name: str | None = None,
) -> str | None:
    """Get the connected account ID for a specific app.

    Args:
        composio: Initialized Composio client.
        entity_id: Entity ID to look up.
        app_name: Specific app to find (e.g., "googlemeet", "googledrive").
                  If None, returns the first active account.

    Returns:
        The connected account ID or None.
    """
    try:
        accounts = None

        # Try new SDK first (list with user_ids)
        try:
            result = composio.connected_accounts.list(
                user_ids=[entity_id],
                statuses=["ACTIVE"],
            )
            accounts = result.items if hasattr(result, 'items') else result
        except (TypeError, AttributeError):
            # Fall back to old SDK (get with entity_ids)
            accounts = composio.connected_accounts.get(entity_ids=[entity_id], active=True)

        if not accounts:
            return None

        if not isinstance(accounts, list):
            accounts = [accounts]

        # Helper to get app name from account
        def get_app_name(acc):
            if hasattr(acc, "toolkit") and hasattr(acc.toolkit, "slug"):
                return acc.toolkit.slug
            return getattr(acc, "appName", "") or getattr(acc, "app_name", "")

        # If specific app requested, find that account
        if app_name:
            for acc in accounts:
                if get_app_name(acc).lower() == app_name.lower():
                    return acc.id

        # For Google Meet tools, prefer googlemeet account
        for acc in accounts:
            if get_app_name(acc).lower() == GOOGLEMEET_APP_NAME:
                return acc.id

        # If no specific account found, use the first one
        return accounts[0].id if accounts else None

    except Exception as e:
        logger.error(f"Error getting connected account: {e}")
        return None


def get_connected_account_for_tool(
    composio: Composio,
    entity_id: str,
    tool_slug: str,
) -> str | None:
    """Get the appropriate connected account ID based on tool type.

    Args:
        composio: Initialized Composio client.
        entity_id: Entity ID to look up.
        tool_slug: Tool name to determine which app account to use.

    Returns:
        The connected account ID or None.
    """
    if tool_slug.startswith("GOOGLEDRIVE_"):
        return get_connected_account_id(composio, entity_id, GOOGLEDRIVE_APP_NAME)
    elif tool_slug.startswith("GOOGLEMEET_"):
        return get_connected_account_id(composio, entity_id, GOOGLEMEET_APP_NAME)
    else:
        return get_connected_account_id(composio, entity_id)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((ComposioConnectionError, RateLimitError)),
    reraise=True,
)
def execute_google_meet_tool(
    composio: Composio,
    entity_id: str,
    tool_slug: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute a Google Meet or Google Drive tool via Composio.

    Args:
        composio: Initialized Composio client.
        entity_id: Entity ID for execution context.
        tool_slug: Tool name/slug (e.g., "GOOGLEMEET_LIST_CONFERENCE_RECORDS").
        arguments: Tool arguments.

    Returns:
        Tool execution result.

    Raises:
        GoogleMeetAPIError: If tool execution fails.
        RateLimitError: If rate limited.
    """
    try:
        logger.debug(f"Executing tool: {tool_slug} with args: {arguments}")

        # Get the appropriate connected account ID based on tool type
        connected_account_id = get_connected_account_for_tool(composio, entity_id, tool_slug)
        if not connected_account_id:
            if tool_slug.startswith("GOOGLEDRIVE_"):
                raise GoogleMeetAPIError(
                    "No active Google Drive connection found. Please set up Google Drive integration.",
                    status_code=401,
                )
            else:
                raise GoogleMeetAPIError(
                    "No active Google Meet connection found. Please run setup first.",
                    status_code=401,
                )

        # Execute using appropriate SDK version
        if _is_new_sdk(composio):
            # New SDK: use composio.tools.execute()
            result = composio.tools.execute(
                tool_slug,
                user_id=entity_id,
                arguments=arguments or {},
            )
        else:
            # Old SDK: use composio.actions.execute() with Action enum
            from composio.client.enums import Action
            try:
                action = getattr(Action, tool_slug)
            except AttributeError:
                action = Action(tool_slug)

            result = composio.actions.execute(
                action=action,
                entity_id=entity_id,
                connected_account=connected_account_id,
                params=arguments or {},
            )

        # Handle result
        if isinstance(result, dict):
            data = result.get("data", result)
            error = result.get("error")
            if error:
                raise GoogleMeetAPIError(f"API Error: {error}")

            # Special handling for GOOGLEDRIVE_DOWNLOAD_FILE - fetch actual content
            if tool_slug == "GOOGLEDRIVE_DOWNLOAD_FILE":
                downloaded = data.get("downloaded_file_content", {})
                s3url = downloaded.get("s3url")
                if s3url:
                    logger.info("Fetching file content from temporary URL...")
                    file_content = fetch_file_content_from_url(s3url)
                    # Add the actual content to the response
                    data["file_content"] = file_content
                    data["content_fetched"] = True
                    # Remove the S3 URL from response (it's temporary and not useful)
                    if "downloaded_file_content" in data:
                        del data["downloaded_file_content"]["s3url"]

            return {"success": True, "data": data}
        else:
            return {"success": True, "data": str(result)}

    except GoogleMeetAPIError:
        raise
    except Exception as e:
        error_msg = str(e).lower()

        # Check for rate limiting
        if "429" in error_msg or "rate limit" in error_msg:
            raise RateLimitError(cause=e)

        # Check for common API errors
        if "403" in error_msg or "permission" in error_msg:
            raise GoogleMeetAPIError(
                "Permission denied. Ensure you have a Google Workspace account with Meet API access.",
                status_code=403,
                cause=e,
            )

        if "404" in error_msg or "not found" in error_msg:
            raise GoogleMeetAPIError(
                f"Resource not found: {tool_slug}",
                status_code=404,
                cause=e,
            )

        logger.error(f"Tool execution failed: {e}")
        raise GoogleMeetAPIError(
            f"Failed to execute {tool_slug}: {e}",
            cause=e,
        )
