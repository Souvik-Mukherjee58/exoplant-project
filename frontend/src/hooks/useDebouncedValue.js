import { useEffect, useState } from 'react';

/** The value, but only after it has stopped changing for `delayMs` (typing, dragging a slider). */
export function useDebouncedValue(value, delayMs = 250) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}
