# Fix Frontend State Management for Playlist Comparisons

## Files to Modify/Create
- web/frontend/src/components/ComparisonView.tsx

## Implementation Details
Local state variables conflict with store variables, causing playlist comparison requests to omit ranking parameters.

**Steps:**
1. Rename local state variables `rankingMode` → `setupRankingMode`, `selectedPlaylistId` → `setupSelectedPlaylistId`
2. Update all setup UI references to use renamed variables
3. Ensure `handleSwipeRight` uses store values for API requests
4. Add logging to verify correct values are sent

**Constraints:**
- Follow CLAUDE.md FP + type-safety rules
- Never use `any`, `unknown` without guards, or `!` assertions
- Explicit return types on functions
- Type predicates for runtime checks

## Acceptance Criteria
- Frontend sends correct `ranking_mode` and `playlist_id` in `recordComparison` requests
- Backend filters to playlist tracks correctly
- No TypeScript errors or linting issues
- Tests pass with 70-80% coverage

## Dependencies
- None