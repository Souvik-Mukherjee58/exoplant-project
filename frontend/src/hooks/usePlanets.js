import { useState, useEffect, useCallback, useRef } from 'react';
import { planetsApi } from '../services/api';

export function usePlanets(params = {}) {
  const [planets, setPlanets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const mounted = useRef(true);

  const fetchPlanets = useCallback(async () => {
    if (!mounted.current) return;
    setLoading(true);
    setError(null);
    try {
      const data = await planetsApi.getAll(params);
      if (mounted.current) {
        setPlanets(data);
      }
    } catch (err) {
      if (mounted.current) {
        setError('Failed to load exoplanet data');
        console.error('Error fetching planets:', err);
      }
    } finally {
      if (mounted.current) {
        setLoading(false);
      }
    }
  }, [JSON.stringify(params)]);

  useEffect(() => {
    mounted.current = true;
    fetchPlanets();
    return () => {
      mounted.current = false;
    };
  }, [fetchPlanets]);

  return { planets, loading, error, refetch: fetchPlanets };
}

export function useTopTargets(limit = 10) {
  const [planets, setPlanets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const mounted = useRef(true);

  const fetchTopTargets = useCallback(async () => {
    if (!mounted.current) return;
    setLoading(true);
    setError(null);
    try {
      const data = await planetsApi.getTopTargets({ limit });
      if (mounted.current) {
        setPlanets(data);
      }
    } catch (err) {
      if (mounted.current) {
        setError('Failed to load top targets');
        console.error('Error fetching top targets:', err);
      }
    } finally {
      if (mounted.current) {
        setLoading(false);
      }
    }
  }, [limit]);

  useEffect(() => {
    mounted.current = true;
    fetchTopTargets();
    return () => {
      mounted.current = false;
    };
  }, [fetchTopTargets]);

  return { planets, loading, error, refetch: fetchTopTargets };
}

export function usePlanetDetail(planetName) {
  const [planet, setPlanet] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchPlanet = useCallback(async () => {
    if (!planetName) return;

    setLoading(true);
    setError(null);
    try {
      const data = await planetsApi.getByName(planetName);
      setPlanet(data);
    } catch (err) {
      setError(`Failed to load planet: ${planetName}`);
      console.error('Error fetching planet:', err);
    } finally {
      setLoading(false);
    }
  }, [planetName]);

  useEffect(() => {
    fetchPlanet();
  }, [fetchPlanet]);

  return { planet, loading, error, refetch: fetchPlanet };
}
