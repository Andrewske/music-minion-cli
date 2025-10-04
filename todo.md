# Music Minion CLI - Current Tasks

## Active Development

### Phase 8: Polish & Testing (In Progress)

See `docs/incomplete-items.md` for comprehensive list of planned enhancements.

#### High Priority
- [ ] File watching for real-time sync (watchdog library)
- [ ] Conflict detection UI for sync conflicts
- [ ] Comprehensive test suite with pytest
- [ ] Performance monitoring and metrics

#### Medium Priority
- [ ] Documentation improvements
  - [ ] Add video demos/screenshots
  - [ ] Create getting started guide
  - [ ] Add troubleshooting section
- [ ] Error handling improvements
  - [ ] Better error messages with context
  - [ ] Error recovery suggestions
  - [ ] Graceful degradation for all features

#### Low Priority
- [ ] Code quality improvements
  - [ ] Type hint coverage (currently ~80%)
  - [ ] Docstring coverage (currently ~70%)
  - [ ] Remove deprecated code (ui.py, etc.)

## Future Features (Post-Phase 8)

See `docs/incomplete-items.md` for full roadmap.

### AI Enhancements
- [ ] Batch review mode (queue multiple tracks)
- [ ] A/B testing for prompts
- [ ] Confidence scoring for tags
- [ ] Tag suggestions based on patterns

### UI Improvements
- [ ] Global hotkey support (daemon mode)
- [ ] Web UI for mobile control
- [ ] Better keyboard navigation hints
- [ ] Customizable color themes

### Integration Features
- [ ] Spotify/streaming integration
- [ ] Import from other music players
- [ ] Export listening history
- [ ] USB button controller support

## Recently Completed (Last 3 Days)

### ✅ Architecture Refactoring
- Layered architecture (core, domain, commands, ui, utils)
- AppContext pattern for explicit state passing
- Absolute imports throughout

### ✅ UI Migration
- Textual → blessed (complete rewrite)
- Partial rendering (anti-flashing)
- Command history navigation
- Enhanced command palette

### ✅ New Features
- AI tag review system with conversational feedback
- AI prompt enhancement with testing
- Hot-reload development mode
- Track viewer UI component
- Smart playlist wizard
- Auto-advance playback

### ✅ Database
- Schema v9 (reasoning field for tags)
- Migration from v7 → v9

## Notes

- This file tracks active development work
- Completed tasks are moved to `docs/playlist-system-plan.md`
- Long-term roadmap is in `docs/incomplete-items.md`
- Pre-refactor tasks archived in `archive/todo-pre-refactor.md`

---

**Last Updated**: 2025-10-03
