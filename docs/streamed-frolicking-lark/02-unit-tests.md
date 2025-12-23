# Unit Tests for ELO Metadata Functions

## Files to Modify/Create
- `tests/domain/library/test_metadata_elo.py` (new)

## Implementation Details

Create unit tests for the core ELO metadata functions.

### TestStripEloFromComment
Test edge cases for prefix stripping:
- `test_strips_elo_with_separator` - `'1532 - Original comment'` -> `'Original comment'`
- `test_strips_elo_only` - `'1532'` -> `''`
- `test_preserves_non_elo_comment` - `'No prefix here'` -> `'No prefix here'`
- `test_handles_none` - `None` -> `''`
- `test_handles_empty_string` - `''` -> `''`
- `test_strips_with_extra_spaces` - `'1532  -  Spaced out'` -> `'Spaced out'`

### TestFormatCommentWithElo
Test zero-padding, clamping, rounding:
- `test_formats_with_comment` - `(1532, 'Great track')` -> `'1532 - Great track'`
- `test_formats_without_comment` - `(987, None)` -> `'0987'`
- `test_zero_pads_low_elo` - `(42, 'Test')` -> `'0042 - Test'`
- `test_clamps_high_elo` - `(99999, 'Test')` -> `'9999 - Test'`
- `test_clamps_negative_elo` - `(-100, 'Test')` -> `'0000 - Test'`
- `test_rounds_float_elo` - `(1532.7, 'Test')` -> `'1533 - Test'`
- `test_strips_existing_elo_prefix` - `(1600, '1400 - Old rating')` -> `'1600 - Old rating'`

### Integration tests (optional)
If sample audio files exist in test fixtures:
- Test `write_elo_to_file()` with MP3
- Test `write_elo_to_file()` with Opus/OGG
- Verify ELO tags can be read back

## Acceptance Criteria
- [ ] All unit tests pass
- [ ] Tests cover edge cases (None, empty, clamping, rounding)
- [ ] Test file follows project test conventions

## Dependencies
- Task 01: Core ELO functions must be implemented first
