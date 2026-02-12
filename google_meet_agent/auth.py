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
from .config import get_settings

logger = logging.getLogger(__name__)

# App names in Composio
GOOGLEMEET_APP_NAME = "googlemeet"
GOOGLEDRIVE_APP_NAME = "googledrive"


def _is_new_sdk() -> bool:
    """Check if using new SDK (v0.8+) based on available attributes."""
    try:
        # New SDK uses auth_configs, old SDK uses integrations
        composio = Composio()
        return hasattr(composio, 'auth_configs')
    except Exception:
        return True  # Default to new SDK behavior


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
        self._auth_config_id: str | None = None
        self._new_sdk = _is_new_sdk()

    def _get_auth_config_id(self) -> str:
        """Get the auth config ID for the app from Composio or config.

        Returns:
            The auth config ID for the app.

        Raises:
            AuthConfigNotFoundError: If no auth config found.
        """
        if self._auth_config_id:
            return self._auth_config_id

        # Try to get from settings first
        try:
            settings = get_settings()
            if settings.composio_auth_config_id:
                self._auth_config_id = settings.composio_auth_config_id
                logger.info(f"Using auth config from settings: {self._auth_config_id}")
                return self._auth_config_id
        except Exception:
            pass

        # Try to find from auth_configs (new SDK) or integrations (old SDK)
        try:
            if self._new_sdk:
                # New SDK: use auth_configs
                try:
                    auth_configs = self._composio.auth_configs.list()
                    configs = auth_configs.items if hasattr(auth_configs, 'items') else auth_configs
                    for config in configs:
                        toolkit_slug = getattr(config, "toolkit", {})
                        if hasattr(toolkit_slug, "slug"):
                            toolkit_slug = toolkit_slug.slug
                        elif isinstance(toolkit_slug, dict):
                            toolkit_slug = toolkit_slug.get("slug", "")
                        else:
                            toolkit_slug = str(toolkit_slug)
                        if toolkit_slug.lower() == self._app_name.lower():
                            self._auth_config_id = config.id
                            logger.info(f"Found {self._app_name} auth config: {config.id}")
                            return config.id
                except AttributeError:
                    logger.warning("auth_configs not available, trying legacy integrations")
                    self._new_sdk = False

            # Old SDK: use integrations
            if not self._new_sdk:
                integrations = self._composio.integrations.get()
                for integ in integrations:
                    if getattr(integ, "appName", "") == self._app_name:
                        self._auth_config_id = integ.id
                        logger.info(f"Found {self._app_name} integration: {integ.id}")
                        return integ.id

            raise AuthConfigNotFoundError(
                f"No {self._app_name} auth config found. Create one at https://app.composio.dev"
            )

        except AuthConfigNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error finding {self._app_name} auth config: {e}")
            raise AuthConfigNotFoundError(
                f"Failed to find {self._app_name} auth config: {e}",
                cause=e,
            )

    def get_existing_connection(self, user_id: str) -> Any | None:
        """Check for an existing active connection.

        Args:
            user_id: The user ID (user identifier) to check.

        Returns:
            The connected account if found, None otherwise.
        """
        try:
            accounts = None

            if self._new_sdk:
                # New SDK: use list() with user_ids and statuses
                try:
                    result = self._composio.connected_accounts.list(
                        user_ids=[user_id],
                        statuses=["ACTIVE"],
                    )
                    accounts = result.items if hasattr(result, 'items') else result
                except TypeError:
                    # Fall back to old SDK
                    self._new_sdk = False

            if not self._new_sdk:
                # Old SDK: use get() with entity_ids
                accounts = self._composio.connected_accounts.get(
                    entity_ids=[user_id],
                    active=True,
                )

            if not accounts:
                logger.debug(f"No active connections found for user: {user_id}")
                return None

            # Handle single account or list
            if not isinstance(accounts, list):
                accounts = [accounts]

            # Find connection for this app
            for account in accounts:
                # Try different attribute names for app name
                app_name = ""
                if hasattr(account, "toolkit") and hasattr(account.toolkit, "slug"):
                    app_name = account.toolkit.slug
                elif hasattr(account, "appName"):
                    app_name = account.appName
                elif hasattr(account, "app_name"):
                    app_name = account.app_name

                if app_name.lower() == self._app_name.lower():
                    logger.info(f"Found existing {self._app_name} connection for user: {user_id}")
                    return account

            logger.debug(f"No {self._app_name} connection found for user: {user_id}")
            return None

        except Exception as e:
            logger.error(f"Error checking for existing connection: {e}")
            return None

    def initiate_oauth(
        self,
        user_id: str,
        open_browser: bool = True,
    ) -> Any:
        """Initiate OAuth flow for a new connection.

        Args:
            user_id: The user ID (user identifier) to connect.
            open_browser: Whether to automatically open the browser.

        Returns:
            Connection request object with redirect_url.

        Raises:
            AuthConfigNotFoundError: If auth config not found.
        """
        try:
            auth_config_id = self._get_auth_config_id()
            logger.info(f"Initiating OAuth for {self._app_name}, user: {user_id}")

            # Initiate the connection request
            if self._new_sdk:
                connection_request = self._composio.connected_accounts.initiate(
                    user_id=user_id,
                    auth_config_id=auth_config_id,
                )
            else:
                connection_request = self._composio.connected_accounts.initiate(
                    integration_id=auth_config_id,
                    entity_id=user_id,
                )

            # Get the redirect URL (try both new and old attribute names)
            redirect_url = (
                getattr(connection_request, "redirect_url", None) or
                getattr(connection_request, "redirectUrl", None)
            )

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
            connected_account = None

            # Try wait_for_connection (new SDK) first
            if hasattr(connection_request, "wait_for_connection"):
                try:
                    connected_account = connection_request.wait_for_connection(timeout=timeout)
                except TypeError:
                    connected_account = connection_request.wait_for_connection()

            # Try wait_until_active (old SDK) if needed
            if connected_account is None and hasattr(connection_request, "wait_until_active"):
                try:
                    connected_account = connection_request.wait_until_active(
                        client=self._composio,
                        timeout=timeout,
                    )
                except TypeError:
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
        user_id=entity_id,
        open_browser=open_browser,
    )

    # Print URL in case browser didn't open
    redirect_url = (
        getattr(connection_request, "redirect_url", "") or
        getattr(connection_request, "redirectUrl", "")
    )
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
        user_id=entity_id,
        open_browser=open_browser,
    )

    # Print URL in case browser didn't open
    redirect_url = (
        getattr(connection_request, "redirect_url", "") or
        getattr(connection_request, "redirectUrl", "")
    )
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
