#!/usr/bin/env python3
"""Test the shared filter_input integration in playlist builder."""

from music_minion.ui.blessed.state import (
    UIState,
    PlaylistBuilderState,
    advance_filter_editor_step,
    replace,
)
from music_minion.ui.blessed.helpers.filter_input import get_value_options


def test_genre_filter_integration():
    """Test that genre selection uses the shared helper."""
    print("🧪 Testing Shared Filter Input Integration")
    print("=" * 50)

    # Create initial state
    builder = PlaylistBuilderState(
        target_playlist_name="Test Playlist",
        all_tracks=[],
        displayed_tracks=[],
        filters=[],
        sort_field="title",
        sort_direction="asc",
    )
    initial_state = UIState(builder=builder)

    # Enter filter editor mode
    from music_minion.ui.blessed.state import (
        toggle_filter_editor_mode,
        start_adding_filter,
    )

    state = toggle_filter_editor_mode(initial_state)
    state = start_adding_filter(state)

    # Simulate going through the filter editor steps
    # Step 0: Select field (genre) - find the index of "genre" in the options
    field_options = sorted(list(state.builder.filter_editor_options))
    genre_index = field_options.index("genre")
    state = replace(
        state, builder=replace(state.builder, filter_editor_selected=genre_index)
    )

    # Step 1: Advance to operator selection
    state = advance_filter_editor_step(state)

    # Step 2: Select operator (equals) - find the index of "equals" in the operator options
    operator_options = state.builder.filter_editor_options
    equals_index = operator_options.index("equals")  # "equals" is the display text
    state = replace(
        state, builder=replace(state.builder, filter_editor_selected=equals_index)
    )

    # Step 3: Advance to value step - this should call get_value_options
    state = advance_filter_editor_step(state)

    # Check that value options were set correctly
    display_options, raw_values = get_value_options("genre", "equals")

    assert state.builder.filter_editor_value_options == display_options, (
        "Display options should match get_value_options"
    )
    assert state.builder.filter_editor_value_raw == raw_values, (
        "Raw values should match get_value_options"
    )

    assert state.builder.filter_editor_value_options == display_options, (
        "Display options should match get_value_options"
    )
    assert state.builder.filter_editor_value_raw == raw_values, (
        "Raw values should match get_value_options"
    )
    assert len(display_options) > 0, "Should have genre options for selection"
    assert len(raw_values) > 0, "Should have raw genre values"

    # Check that the first option contains a count (format: "Genre (count)")
    first_option = display_options[0]
    assert "(" in first_option and ")" in first_option, (
        f"First option should show count: {first_option}"
    )

    print("✅ Genre selection properly uses shared filter_input helper")
    print(f"   Found {len(display_options)} genre options")
    print(f"   First option: {first_option}")

    # Test that non-genre fields still work (should be empty lists for text input)
    display_options_text, raw_values_text = get_value_options("title", "contains")
    assert display_options_text == [], "Text fields should return empty display options"
    assert raw_values_text == [], "Text fields should return empty raw values"

    print("✅ Text input fields correctly return empty options for shared helper")

    print("\n" + "=" * 50)
    print("🎉 Shared filter_input integration test PASSED!")
    return True


if __name__ == "__main__":
    success = test_genre_filter_integration()
    exit(0 if success else 1)
