# AI Tag Review & Learning System

## Overview

A conversational AI tag review system that allows you to provide feedback on AI-generated tags, accumulate learnings, and continuously improve the tagging prompt over time.

**Status**: ✅ Fully Implemented (2025-10-03)

## Features

### 1. Tags with Reasoning (Phase 1)
- **What**: AI now returns tags with explanations
- **Format**: JSON with tag:reasoning pairs
  ```json
  {
    "energetic": "Fast tempo (140 BPM), driving drums",
    "synth-heavy": "Dominant synthesizer throughout",
    "dark": "Minor key with brooding atmosphere"
  }
  ```
- **Storage**: Reasoning stored in database `tags.reasoning` field
- **Migration**: Database schema v9 adds reasoning column

### 2. Conversational Tag Review (Phase 2)
- **Command**: `ai review`
- **Workflow**:
  1. Shows currently playing track's tags with reasoning
  2. Enters conversation mode (all input goes to AI)
  3. You provide freeform feedback
  4. AI regenerates tags based on feedback
  5. Preview new tags, confirm to save
  6. AI extracts learnings and saves to file

**Example Conversation**:
```
> This track is actually half-time, so it's not very energetic.
  And don't tag with the key because that is kept in metadata.

AI: Got it! I'll remove 'energetic' and 'E-minor'. Should I add
    'half-time' as a tag instead?

> Yes, and make it more chill/downtempo focused

AI: Updated tags: half-time, chill, synth-heavy, filthy

> Perfect. done
```

### 3. Learning Accumulation (Phase 3)
- **Storage**: `~/.config/music-minion/ai/learnings.md`
- **Structure**:
  ```markdown
  ## Rules - Don't Tag These
  - Don't tag key - already in metadata
  - Don't tag BPM numbers

  ## Vocabulary - Approved Terms
  - half-time: slower groove feel
  - filthy: aggressive distorted bass

  ## Vocabulary - Avoid These Terms
  - energetic: too vague without context

  ## Genre-Specific Guidance
  - For electronic: focus on bass character
  ```

### 4. Prompt Enhancement (Phase 4)
- **Command**: `ai enhance prompt`
- **Workflow**:
  1. AI analyzes accumulated learnings
  2. Proposes prompt improvements (diff-style)
  3. Tests new prompt on 3 random tracks
  4. Shows before/after tag comparison
  5. You approve or reject changes
  6. Saves as new prompt version if approved

- **Prompt Versioning**:
  - Stored in `~/.config/music-minion/ai/prompts/`
  - Format: `v-YYYYMMDD-HHMMSS.txt`
  - Active prompt: `prompts/active.txt`
  - History preserved for rollback

## File Structure

```
~/.config/music-minion/
├── ai/
│   ├── prompts/
│   │   ├── v-20251003-120000.txt  # Version history
│   │   ├── v-20251003-150000.txt
│   │   └── active.txt              # Current active prompt
│   └── learnings.md                # Accumulated learnings
└── config.toml
```

## Database Changes

### Schema v9
```sql
ALTER TABLE tags ADD COLUMN reasoning TEXT;
```

### Migration
- Automatically runs on next app start
- Idempotent (safe to run multiple times)
- Backward compatible (reasoning is optional)

## Usage

### Initial Setup
```bash
# 1. Configure AI (if not done)
ai setup sk-...

# 2. Analyze a track (generates tags with reasoning)
ai analyze
```

### Review Workflow
```bash
# 3. Review current track's tags
ai review

# Conversation mode starts:
> This is half-time, not energetic. Don't tag the key.
# ... AI responds and regenerates tags ...
> done

# Preview new tags, confirm [y/n]
# Learnings automatically extracted and saved
```

### Prompt Improvement Workflow
```bash
# After reviewing 5-10 tracks, enhance the prompt
ai enhance prompt

# AI proposes changes based on learnings
# Shows 3-track test comparison
# Approve or reject [y/n]
```

### Other AI Commands
```bash
ai test           # Test prompt on random track
ai usage          # Show AI usage stats
ai usage today    # Today's usage
ai usage month    # Last 30 days
```

## Implementation Details

### New Modules

1. **`domain/ai/prompt_manager.py`**
   - Prompt versioning and storage
   - Learnings file management
   - Active prompt management

2. **`domain/ai/review.py`**
   - Tag conversation system
   - Learning extraction
   - Tag regeneration with feedback

3. **`domain/ai/prompt_enhancement.py`**
   - Prompt improvement proposals
   - Multi-track testing
   - Diff generation and display

### Modified Modules

1. **`domain/ai/client.py`**
   - `analyze_track_with_ai()` now returns reasoning
   - JSON response format with tag:reasoning pairs
   - Backward compatible with `return_reasoning=False`

2. **`core/database.py`**
   - `add_tags()` accepts optional `reasoning` dict
   - `get_track_tags()` returns reasoning in results
   - Schema migration v8→v9

3. **`commands/ai.py`**
   - New `handle_ai_review_command()`
   - New `handle_ai_enhance_command()`

4. **`router.py`**
   - Added `ai review` routing
   - Added `ai enhance` routing
   - Updated help text

## AI Prompting Strategy

### Reasoning Extraction
- AI returns JSON: `{"tag": "reasoning (5-10 words)"}`
- Reasoning references actual track metadata
- Fallback parsing from markdown code blocks

### Conversation Context
- Includes track metadata, notes, current tags
- Includes accumulated learnings
- Maintains conversation history
- Natural language feedback processing

### Learning Extraction
- AI extracts structured learnings from conversation
- Categorizes: rules, good vocab, bad vocab, guidance
- Formats as markdown for human editing

### Prompt Enhancement
- AI compares current prompt + learnings
- Generates improved version
- Tests on real tracks for validation
- Preserves version history

## Testing Recommendations

### Manual Testing
1. **Basic Review Flow**:
   ```bash
   # Play a track
   play

   # Analyze it
   ai analyze

   # Review and provide feedback
   ai review
   ```

2. **Learning Accumulation**:
   - Review 5-10 diverse tracks
   - Check `~/.config/music-minion/ai/learnings.md`
   - Verify learnings are categorized correctly

3. **Prompt Enhancement**:
   ```bash
   # After accumulating learnings
   ai enhance prompt

   # Check test results make sense
   # Verify prompt versions saved
   ls ~/.config/music-minion/ai/prompts/
   ```

### Edge Cases to Test
- [ ] No API key configured
- [ ] Track with no existing tags
- [ ] Track with only user tags (no AI tags)
- [ ] Empty conversation (type "done" immediately)
- [ ] API errors during conversation
- [ ] Malformed JSON from AI
- [ ] No learnings file exists yet
- [ ] No tracks with AI tags (for prompt testing)

## Future Enhancements

### Potential Additions
1. **Batch Review Mode**:
   - Queue multiple tracks for review
   - Auto-play next track after review

2. **A/B Testing**:
   - Compare two prompt versions
   - Track which produces better tags

3. **Export Learnings**:
   - Share learnings with other users
   - Import community-curated learnings

4. **Confidence Scoring**:
   - AI returns confidence per tag
   - Low-confidence tags flagged for review

5. **Tag Suggestions**:
   - AI suggests missing tags based on learnings
   - "You usually tag 'filthy' with 'distorted-bass'"

## Known Limitations

1. **No Batch Operations**:
   - Review one track at a time
   - Manual process (future: batch mode)

2. **Learning Format**:
   - Markdown is manually editable but not structured
   - Future: Consider structured JSON storage

3. **Prompt Testing**:
   - Fixed 3-track test sample
   - Future: Allow custom test sets

4. **No Rollback UI**:
   - Can manually edit active.txt
   - Future: `ai prompt history` and `ai prompt rollback`

## Architecture Notes

### Functional Design
- All functions pure with explicit state passing
- No global state or mutations
- Clear data flow through function signatures

### Error Handling
- Graceful degradation for AI failures
- User-friendly error messages
- Preserves workflow on non-critical errors

### Extensibility
- Modular domain functions
- Easy to add new learning categories
- Prompt enhancement logic separate from UI

## Related Documentation

- `CLAUDE.md` - Project architecture and patterns
- `ai-learnings.md` - Development patterns and best practices
- `docs/incomplete-items.md` - Future roadmap

## Changelog

**2025-10-03**: Initial implementation
- Database schema v9 (reasoning field)
- `ai review` command
- `ai enhance prompt` command
- File-based prompt versioning
- Learnings accumulation system
- Conversational tag feedback

---

**Implementation Time**: ~2-3 hours
**Files Modified**: 6
**Files Created**: 4
**Lines of Code**: ~1200
