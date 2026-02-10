# Google Meet Agent

AI-powered agent for querying Google Meet meetings via Composio OAuth.

## Features

- **Read-only access** to past Google Meet data:
  - List conference records (past meetings)
  - Get meeting details (date, time, duration)
  - List participants (who attended, join/leave times)
  - Get transcripts (if enabled during meeting)
  - **Gemini meeting notes** (via Google Drive integration)
- **Natural language queries** powered by Claude
- **OAuth authentication** via Composio (no API keys to manage)
- **Supervisor-ready** - can be called as a sub-agent

## Requirements

- Python 3.10+
- **Google Workspace account** (Business Standard or higher) - required for Meet API access
- Composio account with Google Meet + Google Drive auth configs
- Anthropic API key

## Quick Start

### 1. Install

```bash
cd google-meet-composio-agent
pip install -e .
```

### 2. Configure

Copy `.env.example` to `.env` and fill in:

```bash
cp .env.example .env
```

Required variables:
- `COMPOSIO_API_KEY` - Get from [Composio Dashboard](https://app.composio.dev)
- `ANTHROPIC_API_KEY` - Get from [Anthropic Console](https://console.anthropic.com)
- `COMPOSIO_AUTH_CONFIG_ID` - Create in Composio (see below)

### 3. Create Auth Config in Composio

1. Go to [app.composio.dev](https://app.composio.dev)
2. Navigate to **Auth Configs** tab
3. Click **Create Auth Config**
4. Select **Google Meet** → OAuth2
5. Use Composio's managed auth (default) or add your own Google Cloud credentials
6. Copy the `auth_config_id` (starts with `ac_`) to your `.env`

### 4. Run Setup

```bash
python scripts/setup_connection.py
```

This will:
- Open a browser for Google OAuth
- Wait for you to authorize
- Confirm the connection is active

### 5. Test

```bash
python scripts/quick_test.py
```

### 6. Use Interactive CLI

```bash
python -m google_meet_agent.cli
```

## Usage

### In Your Code

```python
from google_meet_agent import GoogleMeetAgent

# Create agent (uses .env for config)
agent = GoogleMeetAgent()

# Setup (handles OAuth if needed - only needed once)
agent.setup()

# Natural language queries
response = agent.query("Show me my recent meetings")
print(response.data)

# Convenience methods
response = agent.list_conferences(limit=10)
response = agent.get_participants("conferenceRecords/abc123")
response = agent.get_transcript("conferenceRecords/abc123")
```

### As a Sub-Agent

```python
from google_meet_agent import GoogleMeetAgent

# Wrap as a tool for your supervisor
meet_agent = GoogleMeetAgent()
meet_agent.setup()

def google_meet_tool(query: str) -> str:
    """Query Google Meet meetings."""
    response = meet_agent.query(query)
    return response.data if response.success else f"Error: {response.error}"

# Supervisor can now call google_meet_tool()
```

See `supervisor_example.py` for more patterns.

## Sample Prompts

### Basic Queries

- "Show me my recent meetings"
- "List my past conferences"
- "Who attended the meeting with code abc-defg-hij?"
- "Get the transcript from my last meeting"
- "What meetings did I have this week?"
- "Get the Gemini notes from my Daily Standup"

### Complete Meeting Briefing (Recommended for supervisor agents)

```
Extract meeting intelligence for [MEETING_NAME] on [DATE].

Return the information in this exact structure:

MEETING_METADATA:
- title: [meeting title]
- date: [YYYY-MM-DD format]
- time: [HH:MM timezone]
- duration_minutes: [number]

ATTENDEES:
- [Name] | [Email if available] | [Role if mentioned]

SUMMARY:
[2-3 sentence executive summary]

KEY_TOPICS:
1. [topic]

ACTION_ITEMS:
- [Owner]: [Task description]

DECISIONS_MADE:
- [Decision]
```

### Comprehensive Meeting Details

```
Get complete details for my [MEETING_NAME] meeting from [DATE], including:
- Meeting summary and key discussion points
- All participant names and email addresses
- Full meeting notes or transcript
```

### Multi-Meeting Search (Weekly/Date Range)

```
Find all "[MEETING_NAME]" meetings from [DATE_RANGE].
For each one found, show:
- Full date and time
- List of participants with names
- Meeting summary or key decisions made
```

### Participant-Focused Query

```
For the [MEETING_NAME] meeting on [DATE]:
1. List all attendees with their full names and email addresses
2. Show who said what (key points per person)
3. Include any action items assigned to specific people
```

### With Explicit Fallback Logic (Most Reliable)

```
I need a complete meeting briefing for [MEETING_NAME] on [DATE].

Please provide:
1. MEETING INFO: Date, time, duration, meeting code
2. PARTICIPANTS: All attendee names and emails (check both Google Meet records AND the meeting notes)
3. CONTENT: Get the meeting transcript from Google Meet. If transcript is not available, fetch the Gemini meeting notes from Google Drive.
4. ACTION ITEMS: List any tasks or follow-ups mentioned

Format the response clearly with headers.
```

### Supervisor Agent Integration Example

```python
def get_meeting_intelligence(meeting_name: str, date: str) -> dict:
    """Extract structured meeting data for downstream processing."""
    prompt = f"""Extract meeting intelligence for {meeting_name} on {date}.

    Return: MEETING_METADATA, ATTENDEES, SUMMARY, KEY_TOPICS, ACTION_ITEMS, DECISIONS_MADE"""

    response = meet_agent.query(prompt)
    return {"success": response.success, "data": response.data}
```

## Google Workspace Requirement

The Google Meet REST API requires a **Google Workspace account**:
- Business Standard ($12/user/mo) or higher
- Enterprise
- Education Fundamentals or higher

**Personal Gmail accounts have very limited API access** - you can only create meetings, not list past meetings or participants.

## Using Your Own Google Cloud OAuth (Production)

For production use, create your own OAuth credentials:

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project
3. Go to **APIs & Services** → **Library**
4. Search for and enable **Google Meet REST API**
5. Go to **OAuth consent screen**:
   - User Type: External (or Internal for Workspace)
   - Add scopes for Google Meet
6. Go to **Credentials** → **Create Credentials** → **OAuth client ID**
   - Application type: Web application
   - Authorized redirect URI: `https://backend.composio.dev/api/v3/toolkits/auth/callback`
7. Copy Client ID and Client Secret
8. In Composio Auth Config, select "Manage authentication with custom credentials"
9. Enter your Client ID and Client Secret

## Project Structure

```
google-meet-composio-agent/
├── google_meet_agent/
│   ├── __init__.py      # Package exports
│   ├── agent.py         # Main agent with Claude
│   ├── auth.py          # OAuth flow management
│   ├── tools.py         # Tool fetching/execution
│   ├── config.py        # Settings from .env
│   ├── exceptions.py    # Custom exceptions
│   └── cli.py           # Interactive CLI
├── scripts/
│   ├── setup_connection.py  # OAuth setup
│   ├── quick_test.py        # Test agent
│   └── discover_tools.py    # List available tools
├── supervisor_example.py    # Sub-agent patterns
└── tests/
```

## Troubleshooting

### "Permission denied" errors
- Ensure you have a Google Workspace account (not personal Gmail)
- Check that Google Meet REST API is enabled in your Google Cloud project

### OAuth not working
- Verify `COMPOSIO_AUTH_CONFIG_ID` is correct
- Try creating a new auth config in Composio
- Check Composio dashboard for connection status

### No meetings found
- The API only shows meetings from the last 30 days by default
- Transcripts are only available if enabled during the meeting
- Some meeting data may take time to appear after the meeting ends

## License

MIT
