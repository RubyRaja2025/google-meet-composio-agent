"""OAuth flow management for Google Meet and Google Drive connections via Composio."""

import logging
import webbrowser
from typing import Any

from composio import Composio

from .exceptions import (
    AuthConfigNotFoundError,
    ConnectionExpiredError,
    OAuthTimeoutError,
    ComposioConnectionError,
)

logger = logging.getLogger(__name__)

# App names in Composio
GOOGLEMEET_APP_NAME = "googlemeet"
GOOGLEDRIVE_APP_NAME = "googledrive"


class GoogleAuthManager:
    """Manages OAuth authentication flow for Google app connections (Meet, Drive, etc.)."""

    def __init__(self, composio: Composio, app_name: str = GOOGLEMEET_APP_NAME):
        """Initialize the auth manager.

        Args:
            composio: Initialized Composio client instance.
            app_name: The app name to manage (e.g., "googlemeet", "googledrive").
        """
        self._composio = composio
        self._app_name = app_name
        self._integration_id: str | None = None

    def _get_integration_id(self) -> str:
        """Get the integration ID for the app from Composio.

        Returns:
            The integration ID (UUID) for the app.

        Raises:
            AuthConfigNotFoundError: If no integration found.
        """
        if self._integration_id:
            return self._integration_id

        try:
            integrations = self._composio.integrations.get()

            for integ in integrations:
                if getattr(integ, "appName", "") == self._app_name:
                    self._integration_id = integ.id
                    logger.info(f"Found {self._app_name} integration: {integ.id}")
                    return integ.id

            raise AuthConfigNotFoundError(
                f"No {self._app_name} integration found. Create one at https://app.composio.dev"
            )

        except AuthConfigNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error finding {self._app_name} integration: {e}")
            raise AuthConfigNotFoundError(
                f"Failed to find {self._app_name} integration: {e}",
                cause=e,
            )

    def get_existing_connection(self, entity_id: str) -> Any | None:
        """Check for an existing active connection.

        Args:
            entity_id: The entity ID (user identifier) to check.

        Returns:
            The connected account if found, None otherwise.
        """
        try:
            # Get active connected accounts for this entity
            accounts = self._composio.connected_accounts.get(
                entity_ids=[entity_id],
                active=True,
            )

            if not accounts:
                logger.debug(f"No active connections found for entity: {entity_id}")
                return None

            # Handle single account or list
            if not isinstance(accounts, list):
                accounts = [accounts]

            # Find connection for this app
            for account in accounts:
                app_name = getattr(account, "appName", "") or getattr(account, "app_name", "")
                if app_name.lower() == self._app_name.lower():
                    logger.info(f"Found existing {self._app_name} connection for entity: {entity_id}")
                    return account

            logger.debug(f"No {self._app_name} connection found for entity: {entity_id}")
            return None

        except Exception as e:
            logger.error(f"Error checking for existing connection: {e}")
            return None

    def initiate_oauth(
        self,
        entity_id: str,
        open_browser: bool = True,
    ) -> Any:
        """Initiate OAuth flow for a new connection.

        Args:
            entity_id: The entity ID (user identifier) to connect.
            open_browser: Whether to automatically open the browser.

        Returns:
            Connection request object with redirectUrl.

        Raises:
            AuthConfigNotFoundError: If integration not found.
        """
        try:
            integration_id = self._get_integration_id()
            logger.info(f"Initiating OAuth for {self._app_name}, entity: {entity_id}")

            # Initiate the connection request
            connection_request = self._composio.connected_accounts.initiate(
                integration_id=integration_id,
                entity_id=entity_id,
            )

            # Get the redirect URL
            redirect_url = getattr(connection_request, "redirectUrl", None)

            if not redirect_url:
                raise AuthConfigNotFoundError(
                    "Could not get OAuth URL from Composio."
                )

            logger.info(f"OAuth URL obtained: {redirect_url[:50]}...")

            # Open browser if requested
            if open_browser:
                logger.info("Opening browser for authentication...")
                webbrowser.open(redirect_url)

            return connection_request

        except AuthConfigNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to initiate OAuth: {e}")
            raise AuthConfigNotFoundError(
                f"Failed to initiate OAuth: {e}",
                cause=e,
            )

    def wait_for_connection(
        self,
        connection_request: Any,
        timeout: int = 300,
    ) -> Any:
        """Wait for user to complete OAuth flow.

        Args:
            connection_request: The connection request from initiate_oauth.
            timeout: Maximum seconds to wait.

        Returns:
            The connected account.

        Raises:
            OAuthTimeoutError: If timeout is reached.
            ConnectionExpiredError: If connection expires.
        """
        logger.info(f"Waiting up to {timeout}s for OAuth completion...")

        try:
            # Use Composio's built-in wait method
            # API may require client parameter in some versions
            try:
                connected_account = connection_request.wait_until_active(
                    client=self._composio,
                    timeout=timeout,
                )
            except TypeError:
                # Fallback for older API
                connected_account = connection_request.wait_until_active(timeout=timeout)

            if connected_account:
                logger.info("OAuth completed successfully!")
                return connected_account
            else:
                raise OAuthTimeoutError(timeout)

        except OAuthTimeoutError:
            raise
        except Exception as e:
            error_msg = str(e).lower()
            if "timeout" in error_msg or "timed out" in error_msg:
                raise OAuthTimeoutError(timeout, cause=e)
            elif "expired" in error_msg:
                raise ConnectionExpiredError(cause=e)
            else:
                raise ComposioConnectionError(
                    f"Failed while waiting for OAuth: {e}",
                    cause=e,
                )


# Alias for backwards compatibility
GoogleMeetAuthManager = GoogleAuthManager


def ensure_google_meet_connection(
    composio: Composio,
    entity_id: str,
    timeout: int = 300,
    open_browser: bool = True,
) -> Any:
    """Ensure user has an active Google Meet connection.

    Checks for existing connection and initiates OAuth if needed.

    Args:
        composio: Initialized Composio client.
        entity_id: The entity ID (user identifier).
        timeout: Timeout for OAuth if needed.
        open_browser: Whether to auto-open browser for OAuth.

    Returns:
        The connected account.

    Raises:
        AuthConfigNotFoundError: If integration not found.
        OAuthTimeoutError: If OAuth times out.
        ConnectionExpiredError: If connection is expired.
    """
    auth_manager = GoogleAuthManager(composio, GOOGLEMEET_APP_NAME)

    # Check for existing connection
    existing = auth_manager.get_existing_connection(entity_id)
    if existing:
        logger.info("Using existing Google Meet connection")
        return existing

    # No existing connection - initiate OAuth
    print("\n" + "=" * 60)
    print("Google Meet Authentication Required")
    print("=" * 60)
    print("\nA browser window will open for you to authorize access.")
    print("Please sign in with your Google Workspace account.\n")

    connection_request = auth_manager.initiate_oauth(
        entity_id=entity_id,
        open_browser=open_browser,
    )

    # Print URL in case browser didn't open
    redirect_url = getattr(connection_request, "redirectUrl", "")
    print(f"If the browser didn't open, visit this URL:")
    print(f"\n  {redirect_url}\n")
    print("Waiting for authentication...")
    print("=" * 60 + "\n")

    # Wait for completion
    connected_account = auth_manager.wait_for_connection(
        connection_request,
        timeout=timeout,
    )

    print("\nAuthentication successful!")
    return connected_account


def ensure_google_drive_connection(
    composio: Composio,
    entity_id: str,
    timeout: int = 300,
    open_browser: bool = True,
) -> Any:
    """Ensure user has an active Google Drive connection.

    Checks for existing connection and initiates OAuth if needed.

    Args:
        composio: Initialized Composio client.
        entity_id: The entity ID (user identifier).
        timeout: Timeout for OAuth if needed.
        open_browser: Whether to auto-open browser for OAuth.

    Returns:
        The connected account.

    Raises:
        AuthConfigNotFoundError: If integration not found.
        OAuthTimeoutError: If OAuth times out.
        ConnectionExpiredError: If connection is expired.
    """
    auth_manager = GoogleAuthManager(composio, GOOGLEDRIVE_APP_NAME)

    # Check for existing connection
    existing = auth_manager.get_existing_connection(entity_id)
    if existing:
        logger.info("Using existing Google Drive connection")
        return existing

    # No existing connection - initiate OAuth
    print("\n" + "=" * 60)
    print("Google Drive Authentication Required")
    print("=" * 60)
    print("\nA browser window will open for you to authorize access.")
    print("This is needed to fetch Gemini meeting notes.\n")

    connection_request = auth_manager.initiate_oauth(
        entity_id=entity_id,
        open_browser=open_browser,
    )

    # Print URL in case browser didn't open
    redirect_url = getattr(connection_request, "redirectUrl", "")
    print(f"If the browser didn't open, visit this URL:")
    print(f"\n  {redirect_url}\n")
    print("Waiting for authentication...")
    print("=" * 60 + "\n")

    # Wait for completion
    connected_account = auth_manager.wait_for_connection(
        connection_request,
        timeout=timeout,
    )

    print("\nGoogle Drive authentication successful!")
    return connected_account


def check_google_drive_connection(composio: Composio, entity_id: str) -> bool:
    """Check if Google Drive connection exists (without initiating OAuth).

    Args:
        composio: Initialized Composio client.
        entity_id: The entity ID (user identifier).

    Returns:
        True if connection exists, False otherwise.
    """
    auth_manager = GoogleAuthManager(composio, GOOGLEDRIVE_APP_NAME)
    return auth_manager.get_existing_connection(entity_id) is not None
