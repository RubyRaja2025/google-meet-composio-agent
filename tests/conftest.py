"""Pytest configuration and fixtures."""

import os

import pytest
from dotenv import load_dotenv


@pytest.fixture(scope="session", autouse=True)
def load_env():
    """Load environment variables for tests."""
    load_dotenv()


@pytest.fixture
def mock_composio_api_key():
    """Mock Composio API key for testing."""
    return "test_composio_key"


@pytest.fixture
def mock_anthropic_api_key():
    """Mock Anthropic API key for testing."""
    return "test_anthropic_key"


@pytest.fixture
def mock_auth_config_id():
    """Mock auth config ID for testing."""
    return "ac_test_config"


@pytest.fixture
def mock_user_id():
    """Mock user ID for testing."""
    return "test_user"


@pytest.fixture
def env_override(mock_composio_api_key, mock_anthropic_api_key, mock_auth_config_id, mock_user_id):
    """Override environment variables for testing."""
    original_env = os.environ.copy()

    os.environ["COMPOSIO_API_KEY"] = mock_composio_api_key
    os.environ["ANTHROPIC_API_KEY"] = mock_anthropic_api_key
    os.environ["COMPOSIO_AUTH_CONFIG_ID"] = mock_auth_config_id
    os.environ["GOOGLE_MEET_USER_ID"] = mock_user_id

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)
