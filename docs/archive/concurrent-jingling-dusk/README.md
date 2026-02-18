# Unify Player Systems: Single Global Audio

## Overview
Merge three separate player systems (global player, playlist builder, comparison mode) into a single unified player so only one audio stream plays at a time. Currently, each system creates its own Audio element, allowing dual/triple playback.

**Solution:** Share a single Audio element via React Context. WaveSurfer uses the shared element for visualization.

## Task Sequence
1. [01-shared-audio-context.md](./01-shared-audio-context.md) - Create AudioElementContext and provider
2. [02-integrate-useplayer.md](./02-integrate-useplayer.md) - Switch usePlayer hook to shared audio
3. [03-wavesurfer-external-audio.md](./03-wavesurfer-external-audio.md) - Add external audio support to WaveSurfer
4. [04-smartplaylist-global-player.md](./04-smartplaylist-global-player.md) - Wire SmartPlaylistEditor to global player
5. [05-comparison-global-player.md](./05-comparison-global-player.md) - Wire ComparisonView to global player
6. [06-cleanup-and-verify.md](./06-cleanup-and-verify.md) - Final cleanup and end-to-end testing

## Success Criteria
- Only ONE audio stream plays at any time
- Playlist builder play/seek controls global player
- Comparison mode play/seek controls global player
- A/B comparison looping still works
- WebSocket device sync still works
- No UI changes (same waveforms, buttons, layout)

## Dependencies
- WaveSurfer.js `media` option for external audio element
- Existing playerStore context types already support 'builder' and 'comparison'
