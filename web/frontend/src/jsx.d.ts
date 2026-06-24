// React 19 removed the global `JSX` namespace in favor of `React.JSX`.
// This codebase uses bare `JSX.Element` return annotations in ~68 places.
// Re-expose the global namespace as an alias of `React.JSX` so existing
// annotations keep resolving to the exact type React produces — no `any`,
// no behavioral change, just a name bridge for the 18 -> 19 types move.
import type * as React from 'react';

declare global {
  namespace JSX {
    type Element = React.JSX.Element;
  }
}

export {};
