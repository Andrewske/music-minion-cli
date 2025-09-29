# Music Library Metadata Enhancement Plan

## Core Concept
A conversational AI-driven metadata cleaning and enhancement system that learns your preferences and patterns through interaction, then applies those learnings to bulk processing.

## Phase 1: Conversational Metadata Enhancement (MVP)

### New CLI Command: `music-minion metadata fix`
- Interactive conversation mode with AI
- Process tracks one at a time
- Show current metadata → AI suggests improvements → User provides feedback → Apply changes
- Built-in prompt optimization that learns from user feedback

### Core Components to Build:

#### 1. **Metadata Reader & Analyzer**
- Comprehensive metadata extraction from MP3/M4A files
- Support for ID3v2, MP4 atoms, and custom fields (TXXX, etc.)
- Extract from multiple sources: TPE1, TPE2, TXXX:DISPLAY ARTIST, TXXX:REMIXER, filenames

#### 2. **Pattern-Based Cleanup (Non-AI)**
- **Comment field cleaning**: Remove promotional text (URLs, "Follow us", "OUT NOW", etc.), preserve ratings (60-100 at start)
- **Artist field consolidation**: Merge TPE1, TPE2, TXXX fields intelligently
- **Title standardization**: Parse "Artist1 x Artist2 - Title (Remix Artist Flip)" patterns
- **iTunes metadata removal**: Clean iTunNORM, iTunSMPB, iTunPGAP noise

#### 3. **AI Enhancement Engine**
- Initial prompt for metadata improvement suggestions
- Context: all available metadata, filename, folder structure, existing patterns
- Target format: `Artist1; Artist2; Artist3; Remix Artist` for artist field
- Target title: `Artist1 x Artist2 - Song Title ft. Artist3 (Artist4 Remix/Flip/Edit)`

#### 4. **Conversational Interface**
- Display current vs. suggested metadata side-by-side
- Accept user modifications/corrections
- Apply confirmed changes to file
- Feed corrections back to prompt optimizer

#### 5. **Prompt Optimizer**
- Learn from user feedback patterns
- Automatically enhance AI prompts based on corrections
- Build examples from successful interactions
- Save learned preferences persistently

## Phase 2: Bulk Processing Tools

### Semi-Automated Processing
- Use learned patterns to suggest bulk operations
- Generate processing rules from successful conversational sessions
- Allow review before batch application
- Handle edge cases with manual review flags

### Pattern Recognition
- Identify tracks needing similar fixes
- Group by metadata confidence levels
- Prioritize by user-defined criteria (rating, play count, etc.)

## Phase 3: External Enrichment (Future)

### SoundCloud Integration
- Use WOAF URLs when available
- Fetch additional artist info, genre tags, descriptions
- Extract comments for AI tag generation
- Cache results to avoid repeat API calls

### Scraping Framework
- Extensible system for multiple sources
- Local processing to avoid API limitations
- Support for sites with good subgenre/tag data

## Technical Architecture

### Data Flow
1. **Read** → Extract all metadata from file
2. **Clean** → Apply pattern-based cleanup rules
3. **Enhance** → AI suggests improvements
4. **Review** → User conversation and feedback
5. **Apply** → Write corrected metadata to file
6. **Learn** → Update prompts based on feedback

### File Structure
```
src/music_minion/
├── metadata/
│   ├── __init__.py
│   ├── reader.py          # Comprehensive metadata extraction
│   ├── cleaner.py         # Pattern-based cleanup
│   ├── enhancer.py        # AI improvement suggestions
│   ├── conversational.py  # User interaction interface
│   ├── optimizer.py       # Prompt learning and optimization
│   └── writer.py          # Safe metadata writing
└── commands/
    └── metadata_fix.py    # CLI command implementation
```

### Configuration
- User preferences for artist formats, title patterns
- Learned prompt templates and examples
- Processing rules and confidence thresholds
- Custom field mappings for different file types

## Success Criteria
1. **Conversational accuracy**: AI suggestions improve with feedback
2. **Pattern learning**: System recognizes user preferences over time
3. **Metadata consistency**: Standardized artist/title formats across library
4. **Safe processing**: No data loss, reversible changes
5. **Efficiency**: Faster processing as AI learns user patterns

## Implementation Notes
- Start with single track processing for safety
- Backup metadata before changes
- Support undo functionality
- Progress tracking for large libraries
- Export/import of learned patterns for sharing

This approach puts you in control while building an AI system that gets smarter about your specific library and preferences over time.

## Key Requirements from Analysis

### Library Patterns Found:
- **Multiple artist formats**: Inconsistent storage across TPE1, TPE2, TXXX:DISPLAY ARTIST, TXXX:REMIXER
- **Comment field content**: Mix of DJ ratings (60-100), promotional text, iTunes metadata
- **Title patterns**: "Artist1 x Artist2 - Title (Remix Artist Type)" format preferred
- **File formats**: Primarily MP3 (ID3v2) and M4A (MP4 atoms)
- **DJ metadata**: TKEY, TBPM properly stored by Serato
- **External links**: WOAF tags contain SoundCloud URLs for enrichment

### Target Metadata Format:
- **Artist field**: `Artist1; Artist2; Artist3; Remix Artist` (semicolon separated)
- **Title field**: `Artist1 x Artist2 - Song Title ft. Artist3 (Artist4 Remix/Flip/Edit)`
- **Comments**: Clean format: `83 - User notes` (rating + personal comments only)
- **Standard fields**: Proper use of TKEY, TBPM, genre, album, year

### Cleanup Priorities:
1. Consolidate all artist information into standardized format
2. Clean promotional text from comments while preserving ratings
3. Standardize title formatting for DJ use
4. Remove iTunes normalization metadata clutter
5. Preserve all DJ-specific metadata (BPM, key, Serato data)