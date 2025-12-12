# Add Explicit Return Types

## Files to Modify/Create
- `web/frontend/src/hooks/useWavesurfer.ts` (modify)

## Implementation Details

Add explicit `: void` return types to all functions in useWavesurfer hook to comply with project guidelines requiring explicit return types for all functions.

### Functions to Update

1. **handleFinish callback** (line ~53)
   ```typescript
   // Before:
   const handleFinish = useCallback(() => {

   // After:
   const handleFinish = useCallback((): void => {
   ```

2. **handleReady callback** (line ~44)
   ```typescript
   // Before:
   const handleReady = useCallback((duration: number) => {

   // After:
   const handleReady = useCallback((duration: number): void => {
   ```

3. **handleSeek callback** (line ~49)
   ```typescript
   // Before:
   const handleSeek = useCallback((progress: number) => {

   // After:
   const handleSeek = useCallback((progress: number): void => {
   ```

4. **togglePlayPause function** (line ~201)
   ```typescript
   // Before:
   const togglePlayPause = () => {

   // After:
   const togglePlayPause = (): void => {
   ```

5. **seekToPercent function** (line ~207)
   ```typescript
   // Before:
   const seekToPercent = (percent: number) => {

   // After:
   const seekToPercent = (percent: number): void => {
   ```

6. **retryLoad callback** (line ~213)
   ```typescript
   // Before:
   const retryLoad = useCallback(() => {

   // After:
   const retryLoad = useCallback((): void => {
   ```

## Acceptance Criteria

- ✅ All 6 functions have explicit `: void` return types
- ✅ TypeScript build succeeds with `npm run build`
- ✅ No TypeScript errors in source files
- ✅ Clean commit with conventional commit message

## Test Commands

```bash
cd web/frontend
npm run build
npx tsc --noEmit  # Verify TypeScript types
```

## Commit Message

```
fix: add explicit return types to all functions per project guidelines
```

## Dependencies

- Task 02 should be complete (to avoid merge conflicts)

## Notes

- This change is purely for type safety and code quality
- No behavioral changes expected
- Aligns with project guidelines requiring explicit return types
- All functions modified return `void` (no return value)
