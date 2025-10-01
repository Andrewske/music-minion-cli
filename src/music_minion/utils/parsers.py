"""
Argument and command parsing utilities.

Cross-cutting utilities for parsing user input and command arguments.
"""

from typing import List


def parse_quoted_args(args: List[str]) -> List[str]:
    """
    Parse command arguments respecting quoted strings.
    Handles both single and double quotes.

    Args:
        args: Raw argument list from command split

    Returns:
        List of parsed arguments with quotes removed

    Example:
        ['playlist', 'rename', '"Old', 'Name"', '"New', 'Name"']
        -> ['playlist', 'rename', 'Old Name', 'New Name']
    """
    parsed = []
    current = []
    in_quote = False
    quote_char = None

    for arg in args:
        # Check if this arg starts a quote
        if not in_quote and arg and arg[0] in ('"', "'"):
            quote_char = arg[0]
            in_quote = True
            # Check if quote also ends in same arg
            if len(arg) > 1 and arg[-1] == quote_char:
                parsed.append(arg[1:-1])
                in_quote = False
                quote_char = None
            else:
                current.append(arg[1:])
        # Check if this arg ends the current quote
        elif in_quote and arg and arg[-1] == quote_char:
            current.append(arg[:-1])
            parsed.append(' '.join(current))
            current = []
            in_quote = False
            quote_char = None
        # Inside a quote
        elif in_quote:
            current.append(arg)
        # Regular arg outside quotes
        else:
            parsed.append(arg)

    # If we have unclosed quotes, join what we have
    if current:
        parsed.append(' '.join(current))

    return parsed


def parse_command(user_input: str) -> tuple[str, List[str]]:
    """
    Parse user input into command and arguments.

    Args:
        user_input: Raw user input string

    Returns:
        Tuple of (command, args) where command is lowercase and args is a list
    """
    parts = user_input.strip().split()
    if not parts:
        return "", []

    command = parts[0].lower()
    args = parts[1:] if len(parts) > 1 else []
    return command, args


__all__ = ['parse_quoted_args', 'parse_command']
