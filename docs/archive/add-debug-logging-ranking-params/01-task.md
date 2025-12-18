# Add Comprehensive Logging for Ranking Parameters

## Files to Modify/Create
- web/frontend/src/stores/comparisonStore.ts
- web/frontend/src/components/ComparisonView.tsx
- web/backend/routers/comparisons.py

## Implementation Details
Context: Frontend still not sending ranking_mode and playlist_id in recordComparison requests. Need to trace where parameters are lost.

Constraints: Add logging only, no functional changes

1. Store logging: Log setSession parameters received
2. Component logging: Log store values in handleSwipeRight and useEffect
3. Backend logging: Log ranking_mode and playlist_id received in recordComparison
4. Test: Start playlist session and record comparison, check all logs

## Acceptance Criteria
- Logs clearly show where ranking parameters are lost or if they're being sent correctly
- Test: Start playlist session and record comparison, check all logs

## Dependencies
None