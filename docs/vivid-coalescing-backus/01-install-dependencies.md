# Install TanStack Dependencies

## Files to Modify/Create
- web/frontend/package.json (modify)

## Implementation Details

Install the required TanStack packages for table functionality and virtual scrolling:

```bash
cd web/frontend && npm install @tanstack/react-table @tanstack/react-virtual
```

### Packages
- `@tanstack/react-table` - Headless table logic with sorting, filtering, pagination
- `@tanstack/react-virtual` - Virtualized scrolling for large lists

## Acceptance Criteria
- [ ] Both packages appear in `package.json` dependencies
- [ ] `npm install` completes without errors
- [ ] Packages can be imported in TypeScript without type errors

## Dependencies
None - this is the first task.
