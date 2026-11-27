import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';

/**
 * Loads data from the API for the current inputs, safely under fast-changing inputs.
 *
 * Every run of the effect has its own AbortController. A newer run, or unmounting, cancels the older
 * request, so an older response can never overwrite newer data, and a cancellation is not shown as an error.
 *
 * @param {(signal: AbortSignal) => Promise<any>} load  fetches the data; must pass `signal` to the request
 * @param {string} key          identifies the inputs: the request runs again when it changes
 * @param {object} options
 * @param {any} options.initialData     data before the first response
 * @param {string} options.errorMessage message shown when the request fails
 * @param {boolean} [options.enabled]   false: no request (for example while an input is missing)
 */
export function useApiResource(load, key, { initialData, errorMessage, enabled = true }) {
  const [data, setData] = useState(initialData);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState(null);
  const [reloadCount, setReloadCount] = useState(0);

  // The latest load function, without making every render a new request.
  const loadRef = useRef(load);
  const messageRef = useRef(errorMessage);
  useEffect(() => {
    loadRef.current = load;
    messageRef.current = errorMessage;
  });

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return undefined;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    loadRef
      .current(controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((err) => {
        if (controller.signal.aborted || axios.isCancel(err)) return;
        setError(messageRef.current);
        console.error(messageRef.current, err);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [key, reloadCount, enabled]);

  const refetch = useCallback(() => setReloadCount((n) => n + 1), []);
  return { data, loading, error, refetch };
}
