import { planetsApi } from '../services/api';
import { useApiResource } from './useApiResource';

const EMPTY = [];

export function usePlanets(params = {}) {
  const key = JSON.stringify(params);
  const { data, loading, error, refetch } = useApiResource(
    (signal) => planetsApi.getAll(JSON.parse(key), { signal }),
    key,
    { initialData: EMPTY, errorMessage: 'Failed to load exoplanet data' }
  );
  return { planets: data, loading, error, refetch };
}

export function useTopTargets(limit = 10, excludeObserved = true) {
  const { data, loading, error, refetch } = useApiResource(
    (signal) => planetsApi.getTopTargets({ limit, exclude_observed: excludeObserved }, { signal }),
    `${limit}|${excludeObserved}`,
    { initialData: EMPTY, errorMessage: 'Failed to load top targets' }
  );
  return { planets: data, loading, error, refetch };
}

export function usePlanetDetail(planetName) {
  const { data, loading, error, refetch } = useApiResource(
    (signal) => planetsApi.getByName(planetName, { signal }),
    planetName ?? '',
    {
      initialData: null,
      errorMessage: `Failed to load planet: ${planetName}`,
      enabled: Boolean(planetName),
    }
  );
  return { planet: data, loading, error, refetch };
}
