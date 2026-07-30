# ForgeGov v2.0.0 RC1

## Purpose
This release candidate resolves every issue reported by the ForgeGov production validation run dated July 30, 2026.

## Corrections
- Vendor profile loading is deferred through a cancellable effect timer, satisfying React's set-state-in-effect rule.
- Global search state changes are deferred through the search timer, satisfying React's set-state-in-effect rule.
- Pursuit deadline calculations use a stable component timestamp rather than calling Date.now during render.
- Opportunity data is memoized before being used by the timeline memo, stabilizing hook dependencies.
- No ESLint rules were disabled and no inline lint suppressions were added.

## Required release gate
Run:

```bash
./scripts/validate_release.sh
```

Release only when all seven stages complete successfully:
1. Django system check
2. Migration check
3. Backend test suite
4. TypeScript typecheck
5. ESLint
6. Next.js production build
7. Container status
