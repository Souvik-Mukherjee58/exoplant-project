import { analyticsApi } from '../services/api';
import { useApiResource } from './useApiResource';

export function useAnalytics() {
  const { data, loading, error, refetch } = useApiResource(
    (signal) => analyticsApi.getAnalysis({ signal }),
    'analysis',
    { initialData: null, errorMessage: 'Failed to load analytics data' }
  );
  return { stats: data, loading, error, refetch };
}

export function useAnomalyPCA() {
  const { data, loading, error, refetch } = useApiResource(
    (signal) => analyticsApi.getAnomalyPCA({ signal }),
    'anomaly-pca',
    { initialData: null, errorMessage: 'Failed to load anomaly PCA data' }
  );
  return { data, loading, error, refetch };
}
