import { useState, useEffect, useCallback } from 'react';
import { analyticsApi } from '../services/api';

export function useAnalytics() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAnalytics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await analyticsApi.getAnalysis();
      setStats(data);
    } catch (err) {
      setError('Failed to load analytics data');
      console.error('Error fetching analytics:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  return { stats, loading, error, refetch: fetchAnalytics };
}

export function useAnomalyPCA() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchPCA = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await analyticsApi.getAnomalyPCA();
      setData(result);
    } catch (err) {
      setError('Failed to load anomaly PCA data');
      console.error('Error fetching anomaly PCA:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPCA();
  }, [fetchPCA]);

  return { data, loading, error, refetch: fetchPCA };
}
