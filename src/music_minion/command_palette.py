"""
Inline command palette for Music Minion CLI
Provides a clean separated input and results interface inline in the terminal
"""

import sys
import tty
import termios
from typing import Optional

from rich.console import Console

from music_minion.utils import autocomplete


def show_command_palette() -> Optional[str]:
    """
    Show an inline command palette with live filtering.

    Returns:
        Selected command name, or None if cancelled
    """
    console = Console()
    commands = autocomplete.MusicMinionCompleter.COMMANDS

    # State
    query = ""
    selected_index = 0
    results_line_count = 0  # Track how many result lines we've drawn

    def get_filtered_commands():
        """Get filtered and sorted commands based on query."""
        filtered = [
            (cmd, icon, desc)
            for cmd, (icon, desc) in commands.items()
            if query.lower() in cmd.lower()
        ]
        filtered.sort(key=lambda x: x[0])
        return filtered[:15]  # Limit to 15 results

    def draw_input_section():
        """Draw the static input section (separators + input line)."""
        # Top separator
        console.print("─" * 80, style="dim")

        # Input line with > prompt (no "/" prefix needed)
        console.print(f"> {query}█")

        # Bottom separator
        console.print("─" * 80, style="dim")

    def draw_results():
        """Draw the filtered results section."""
        nonlocal results_line_count

        # Clear exactly the number of result lines we drew before
        # (Don't use \033[J as it clears too much)
        if results_line_count > 0:
            for _ in range(results_line_count):
                console.file.write("\033[2K\n")  # Clear line and move down
            # Move back up to start of results
            for _ in range(results_line_count):
                console.file.write("\033[A")

        filtered = get_filtered_commands()

        # Count lines we're about to draw
        new_line_count = 0

        # Empty line for spacing
        console.file.write("\n")
        new_line_count += 1

        if filtered:
            for idx, (cmd, icon, desc) in enumerate(filtered):
                # Highlight selected row
                if idx == selected_index:
                    line = f"  ▶ {cmd:<20} {icon}  {desc}\n"
                else:
                    line = f"    {cmd:<20} {icon}  {desc}\n"
                console.file.write(line)
                new_line_count += 1
        else:
            console.file.write("  No matches found\n")
            new_line_count += 1

        # Help text
        console.file.write("\n")
        console.file.write("  ↑↓ navigate  Enter select  Esc cancel")
        new_line_count += 2

        console.file.flush()

        # Update line count for next clear
        results_line_count = new_line_count

    def redraw_input_line():
        """Redraw just the input line (when query changes)."""
        # Move up to input line: results + separator
        for _ in range(results_line_count + 1):
            console.file.write("\033[A")

        # Clear the input line and redraw (no "/" prefix)
        console.file.write("\r\033[2K")
        console.file.write(f"> {query}█\n")

        # Move down past the separator to position for draw_results()
        console.file.write("\033[B")

        console.file.flush()

    # Save terminal settings
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        # Set terminal to raw mode for character-by-character input
        tty.setraw(fd)

        # Initial draw - input section then results
        draw_input_section()
        draw_results()

        while True:
            # Read a character
            char = sys.stdin.read(1)

            # Handle special keys
            if char == '\x1b':  # ESC or arrow key
                # Check if it's an arrow key sequence
                next_chars = sys.stdin.read(2)

                if next_chars == '[A':  # Up arrow
                    filtered = get_filtered_commands()
                    if filtered:
                        selected_index = max(0, selected_index - 1)
                        draw_results()  # Only redraw results
                elif next_chars == '[B':  # Down arrow
                    filtered = get_filtered_commands()
                    if filtered:
                        selected_index = min(len(filtered) - 1, selected_index + 1)
                        draw_results()  # Only redraw results
                else:
                    # Plain ESC - cancel, cleanup done in finally
                    return None

            elif char == '\r' or char == '\n':  # Enter
                filtered = get_filtered_commands()
                if filtered and selected_index < len(filtered):
                    return filtered[selected_index][0]
                return None

            elif char == '\x7f':  # Backspace
                if query:
                    query = query[:-1]
                    selected_index = 0
                    redraw_input_line()
                    draw_results()

            elif char == '\x03':  # Ctrl+C
                raise KeyboardInterrupt

            elif char.isprintable():
                query += char
                selected_index = 0
                redraw_input_line()
                draw_results()

    finally:
        # Restore terminal settings
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        # Clean up - clear the input section (3 lines) and results
        total_lines = 3 + results_line_count
        for _ in range(total_lines):
            console.file.write("\033[A\033[2K")
        console.file.flush()
