"""Command execution."""

import io
from contextlib import redirect_stdout, redirect_stderr
from ..state import UIState, add_history_line, set_feedback


def parse_command_line(line: str) -> tuple[str, list[str]]:
    """
    Parse command line into command and arguments.

    Args:
        line: Full command line (e.g., "playlist new smart test")

    Returns:
        Tuple of (command, args)
    """
    parts = line.strip().split()
    if not parts:
        return "", []
    return parts[0], parts[1:]


def execute_command(state: UIState, command_line: str) -> tuple[UIState, bool]:
    """
    Execute command and return updated state.

    Args:
        state: Current UI state
        command_line: Full command line string

    Returns:
        Tuple of (updated state, should_quit)
    """
    # Parse command
    command, args = parse_command_line(command_line)

    if not command:
        return state, False

    # Special case: QUIT signal from keyboard handler
    if command == 'QUIT':
        return state, True

    # Add command to history
    state = add_history_line(state, f"> {command_line}", 'cyan')

    # Capture output from command execution
    output_buffer = io.StringIO()
    error_buffer = io.StringIO()

    try:
        with redirect_stdout(output_buffer), redirect_stderr(error_buffer):
            # Import router for command handling
            # This is a lazy import to avoid circular dependencies
            from music_minion import router

            # Execute command
            should_continue = router.handle_command(command, args)

            if not should_continue:
                # Command requested exit (quit/exit command)
                return state, True

    except Exception as e:
        # Add error to history
        state = add_history_line(state, f"Error: {e}", 'red')
        return state, False

    # Get captured output
    stdout_output = output_buffer.getvalue()
    stderr_output = error_buffer.getvalue()

    # Add output to history (split by lines)
    if stdout_output:
        for line in stdout_output.strip().split('\n'):
            if line:
                state = add_history_line(state, line, 'white')

    if stderr_output:
        for line in stderr_output.strip().split('\n'):
            if line:
                state = add_history_line(state, line, 'red')

    # Set feedback for certain commands
    if command in ['love', 'like', 'archive', 'skip']:
        state = set_feedback(state, f"✓ {command.capitalize()}", "✓")

    return state, False
