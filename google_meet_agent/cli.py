"""Interactive CLI for the Google Meet agent."""

import sys

from dotenv import load_dotenv

# Try to import rich for colorized output
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel

    console = Console()
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def print_styled(text: str, style: str = "default") -> None:
    """Print with optional styling."""
    if RICH_AVAILABLE:
        if style == "header":
            console.print(Panel(text, style="bold cyan"))
        elif style == "success":
            console.print(f"[green]{text}[/green]")
        elif style == "error":
            console.print(f"[red]{text}[/red]")
        elif style == "info":
            console.print(f"[blue]{text}[/blue]")
        elif style == "warning":
            console.print(f"[yellow]{text}[/yellow]")
        elif style == "markdown":
            console.print(Markdown(text))
        else:
            console.print(text)
    else:
        print(text)


def print_help() -> None:
    """Print help information."""
    help_text = """
Commands:
  help           - Show this help message
  tools          - List available Google Meet tools
  list           - List recent conferences (meetings)
  quit/exit/q    - Exit the CLI

Example queries:
  "Show me my recent meetings"
  "Who attended my last meeting?"
  "Get the transcript from the meeting on Monday"
  "What meetings did I have this week?"
  "Show participants for meeting abc-defg-hij"
"""
    print_styled(help_text, "info")


def print_welcome() -> None:
    """Print welcome message."""
    welcome = """
Google Meet Assistant
=====================
Query your past Google Meet meetings using natural language.

Type 'help' for commands, 'quit' to exit.
"""
    print_styled(welcome, "header")


def main() -> None:
    """Interactive CLI entry point."""
    # Load environment variables
    load_dotenv()

    # Lazy import to avoid loading everything at startup
    from .agent import GoogleMeetAgent
    from .exceptions import ConfigurationError, GoogleMeetAgentError

    print_welcome()

    # Try to create agent
    try:
        print_styled("Initializing agent...", "info")
        agent = GoogleMeetAgent()
    except ConfigurationError as e:
        print_styled(f"Configuration Error: {e}", "error")
        print_styled("\nPlease check your .env file has:", "info")
        print_styled("  COMPOSIO_API_KEY=...", "info")
        print_styled("  ANTHROPIC_API_KEY=...", "info")
        print_styled("  COMPOSIO_AUTH_CONFIG_ID=...", "info")
        sys.exit(1)

    # Set up agent (handles OAuth)
    try:
        agent.setup()
        print_styled("\nAgent ready! You can now query your meetings.\n", "success")
    except GoogleMeetAgentError as e:
        print_styled(f"Setup Error: {e}", "error")
        sys.exit(1)

    # Interactive loop
    while True:
        try:
            # Get user input
            if RICH_AVAILABLE:
                query = console.input("[bold cyan]You:[/bold cyan] ").strip()
            else:
                query = input("You: ").strip()

            # Handle empty input
            if not query:
                continue

            # Handle special commands
            if query.lower() in ("quit", "exit", "q"):
                print_styled("Goodbye!", "info")
                break

            if query.lower() == "help":
                print_help()
                continue

            if query.lower() == "tools":
                tools = agent.list_available_tools()
                if tools:
                    print_styled(f"\nAvailable Tools ({len(tools)}):", "info")
                    for tool in tools:
                        print_styled(f"  - {tool['name']}: {tool['description']}", "default")
                else:
                    print_styled("No tools available.", "warning")
                print()
                continue

            if query.lower() == "list":
                query = "List my recent Google Meet conferences"

            # Run the query
            print_styled("Thinking...", "info")
            response = agent.query(query)

            # Display result
            print()
            if response.success:
                print_styled("Assistant:", "success")
                if response.data:
                    print_styled(response.data, "markdown" if RICH_AVAILABLE else "default")
                else:
                    print_styled("No data returned.", "warning")
            else:
                print_styled(f"Error: {response.error}", "error")
            print()

        except KeyboardInterrupt:
            print_styled("\nGoodbye!", "info")
            break
        except EOFError:
            print_styled("\nGoodbye!", "info")
            break
        except Exception as e:
            print_styled(f"Error: {e}", "error")
            print()


if __name__ == "__main__":
    main()
