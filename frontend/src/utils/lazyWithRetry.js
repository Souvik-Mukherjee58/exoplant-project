import { createElement, lazy } from 'react';

/**
 * React.lazy whose failed import can be tried again.
 *
 * React.lazy remembers a rejected import for good, so after one failed download the component could never
 * render again without a page reload. This wrapper starts a fresh lazy component after a failure when
 * `retry()` is called; a component that loaded successfully is never reloaded.
 */
export function lazyWithRetry(factory) {
  let failed = false;
  const create = () =>
    lazy(() =>
      factory().catch((error) => {
        failed = true;
        throw error;
      })
    );
  let current = create();

  function LazyWithRetry(props) {
    return createElement(current, props);
  }
  LazyWithRetry.retry = () => {
    if (failed) {
      failed = false;
      current = create();
    }
  };
  return LazyWithRetry;
}

/** True for the errors browsers and Vite raise when a code chunk cannot be downloaded. */
export function isChunkLoadError(error) {
  const text = `${error?.name ?? ''} ${error?.message ?? ''}`;
  return /Failed to fetch dynamically imported module|error loading dynamically imported module|Importing a module script failed|Unable to preload CSS|ChunkLoadError|Loading chunk .* failed/i.test(
    text
  );
}
