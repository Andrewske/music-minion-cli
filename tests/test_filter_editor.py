#!/usr/bin/env python3
"""Manual validation of filter editor functionality."""

from music_minion.ui.blessed.state import (
    UIState,
    PlaylistBuilderState,
    BuilderFilter,
    start_adding_filter,
    start_editing_filter,
    update_filter_editor_field,
    update_filter_editor_operator,
    update_filter_editor_value,
    save_filter_editor_changes,
    delete_filter,
    BUILDER_SORT_FIELDS,
    BUILDER_TEXT_OPERATORS,
    BUILDER_NUMERIC_OPERATORS,
)


def test_filter_editor():
    """Test filter editor functionality manually."""
    print("🧪 Testing Filter Editor Functionality")
    print("=" * 50)

    # Sample tracks
    sample_tracks = [
        {
            "title": "Song A",
            "artist": "Artist 1",
            "year": 2020,
            "album": "Album 1",
            "genre": "Rock",
            "bpm": 120,
        },
        {
            "title": "Song B",
            "artist": "Artist 2",
            "year": 2021,
            "album": "Album 2",
            "genre": "Pop",
            "bpm": 130,
        },
        {
            "title": "Song C",
            "artist": "Artist 1",
            "year": 2022,
            "album": "Album 1",
            "genre": "Rock",
            "bpm": 125,
        },
    ]

    # Initial state
    initial_builder = PlaylistBuilderState(
        target_playlist_name="Test Playlist",
        all_tracks=sample_tracks,
        displayed_tracks=sample_tracks,
        filters=[],
        sort_field="title",
        sort_direction="asc",
    )
    initial_state = UIState(builder=initial_builder)

    tests_passed = 0
    total_tests = 0

    def assert_test(condition, description):
        nonlocal tests_passed, total_tests
        total_tests += 1
        if condition:
            print(f"✅ {description}")
            tests_passed += 1
        else:
            print(f"❌ {description}")

    # Test 1: Start adding filter
    print("\n📝 Testing Filter Addition:")
    # First enter filter editor mode
    from music_minion.ui.blessed.state import toggle_filter_editor_mode

    state = toggle_filter_editor_mode(initial_state)
    assert_test(
        state.builder.filter_editor_mode is True, "Filter editor mode activated"
    )

    # Then start adding a filter
    state = start_adding_filter(state)
    assert_test(
        state.builder.filter_editor_selected == -1,
        "Selected index set to -1 for new filter",
    )
    assert_test(state.builder.filter_editor_editing is True, "Editing mode activated")
    assert_test(
        state.builder.filter_editor_step == 0, "Started at step 0 (field selection)"
    )
    assert_test(
        state.builder.filter_editor_field == "title", "Started with first field (title)"
    )

    # Test 2: Field cycling
    print("\n🔄 Testing Field Cycling:")
    state = update_filter_editor_field(state, "artist")
    assert_test(
        state.builder.filter_editor_field == "artist", "Field updated to artist"
    )

    # Test 3: Operator selection for text field
    print("\n⚙️ Testing Operator Selection (Text Field):")
    state = update_filter_editor_operator(state, "contains")
    assert_test(
        state.builder.filter_editor_operator == "contains", "Operator set to contains"
    )

    # Test 4: Value input
    print("\n✏️ Testing Value Input:")
    state = update_filter_editor_value(state, "Artist 1")
    assert_test(state.builder.filter_editor_value == "Artist 1", "Value set correctly")

    # Test 5: Save new filter
    print("\n💾 Testing Filter Saving:")
    state = save_filter_editor_changes(state)
    assert_test(len(state.builder.filters) == 1, "Filter added to list")
    assert_test(
        state.builder.filters[0].field == "artist", "Filter field saved correctly"
    )
    assert_test(
        state.builder.filters[0].operator == "contains",
        "Filter operator saved correctly",
    )
    assert_test(
        state.builder.filters[0].value == "Artist 1", "Filter value saved correctly"
    )
    assert_test(
        state.builder.filter_editor_mode is False, "Filter editor mode deactivated"
    )
    assert_test(
        len(state.builder.displayed_tracks) == 2,
        "Tracks filtered correctly (2 tracks by Artist 1)",
    )

    # Test 6: Start editing existing filter
    print("\n✏️ Testing Filter Editing:")
    # Re-enter filter editor mode
    state = toggle_filter_editor_mode(state)
    assert_test(
        state.builder.filter_editor_mode is True, "Filter editor mode re-activated"
    )

    # Then start editing
    state = start_editing_filter(state, 0)
    assert_test(state.builder.filter_editor_editing is True, "Edit mode activated")
    assert_test(
        state.builder.filter_editor_selected == 0, "Correct filter selected for editing"
    )
    assert_test(state.builder.filter_editor_field == "artist", "Existing field loaded")
    assert_test(
        state.builder.filter_editor_operator == "contains", "Existing operator loaded"
    )
    assert_test(
        state.builder.filter_editor_value == "Artist 1", "Existing value loaded"
    )

    # Test 7: Edit filter value
    state = update_filter_editor_value(state, "Artist 2")
    state = save_filter_editor_changes(state)
    assert_test(
        state.builder.filters[0].value == "Artist 2", "Filter value updated correctly"
    )
    assert_test(
        len(state.builder.displayed_tracks) == 1,
        "Tracks re-filtered correctly (1 track by Artist 2)",
    )

    # Test 8: Delete filter
    print("\n🗑️ Testing Filter Deletion:")
    state = delete_filter(state, 0)
    assert_test(len(state.builder.filters) == 0, "Filter deleted from list")
    assert_test(
        len(state.builder.displayed_tracks) == 3,
        "All tracks shown after filter deletion",
    )

    # Test 9: Numeric field operators
    print("\n🔢 Testing Numeric Field Operators:")
    state = start_adding_filter(initial_state)
    state = update_filter_editor_field(state, "year")  # Numeric field
    state = update_filter_editor_operator(state, "gt")
    assert_test(
        state.builder.filter_editor_operator == "gt",
        "Numeric operator accepted for numeric field",
    )

    # Test 10: Text field operators
    print("\n📝 Testing Text Field Operators:")
    state = start_adding_filter(initial_state)
    state = update_filter_editor_field(state, "title")  # Text field
    state = update_filter_editor_operator(state, "starts_with")
    assert_test(
        state.builder.filter_editor_operator == "starts_with",
        "Text operator accepted for text field",
    )

    # Test 11: Constants validation
    print("\n📋 Testing Constants:")
    assert_test("title" in BUILDER_SORT_FIELDS, "BUILDER_SORT_FIELDS contains title")
    assert_test("year" in BUILDER_SORT_FIELDS, "BUILDER_SORT_FIELDS contains year")
    assert_test(len(BUILDER_TEXT_OPERATORS) > 0, "BUILDER_TEXT_OPERATORS defined")
    assert_test(len(BUILDER_NUMERIC_OPERATORS) > 0, "BUILDER_NUMERIC_OPERATORS defined")

    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tests_passed}/{total_tests} tests passed")

    if tests_passed == total_tests:
        print("🎉 All filter editor functionality tests PASSED!")
        return True
    else:
        print("⚠️ Some tests failed. Check implementation.")
        return False


if __name__ == "__main__":
    success = test_filter_editor()
    exit(0 if success else 1)
