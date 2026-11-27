import axios from 'axios';

const rawApiUrl = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || '/api/v1';
const API_BASE_URL =
  rawApiUrl.startsWith('http') && !rawApiUrl.includes('/api/v1')
    ? `${rawApiUrl.replace(/\/+$/, '')}/api/v1`
    : rawApiUrl;

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging
api.interceptors.request.use(
  (config) => {
    // console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`)
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isCancel(error)) {
      // A newer request replaced this one, or the component unmounted: not an API error.
    } else if (error.response) {
      // Server responded with error status
      console.error(`API Error ${error.response.status}:`, error.response.data);
    } else if (error.request) {
      // Request made but no response
      console.error('API Error: No response from server');
    } else {
      // Other error
      console.error('API Error:', error.message);
    }
    return Promise.reject(error);
  }
);

export const planetsApi = {
  getAll: async (params = {}, config = {}) => {
    const response = await api.get('/planets', { params, ...config });
    return response.data;
  },

  getByName: async (planetName, config = {}) => {
    const response = await api.get(`/planets/${encodeURIComponent(planetName)}`, config);
    return response.data;
  },

  getTopTargets: async (params = {}, config = {}) => {
    const response = await api.get('/top-targets', { params, ...config });
    return response.data;
  },

  getKnownTargets: async () => {
    const response = await api.get('/validation/known-targets');
    return response.data;
  },

  getRecommendations: async (params = {}) => {
    const response = await api.get('/recommendations', { params });
    return response.data;
  },
};

export const analyticsApi = {
  getAnalysis: async (config = {}) => {
    const response = await api.get('/analysis', config);
    return response.data;
  },

  getAnomalyPCA: async (config = {}) => {
    const response = await api.get('/anomaly-pca', config);
    return response.data;
  },
};

export const explainabilityApi = {
  getPlanetExplanation: async (planetName) => {
    const response = await api.get(`/planets/${encodeURIComponent(planetName)}/explain`);
    return response.data;
  },

  getComparisonExplanation: async (planetA, planetB) => {
    const response = await api.get('/planets/compare-explain', {
      params: { planet_a: planetA, planet_b: planetB },
    });
    return response.data;
  },
};

export const modelsApi = {
  getLTRInfo: async () => {
    const response = await api.get('/models/ltr/info');
    return response.data;
  },

  getFeatureImportance: async () => {
    const response = await api.get('/models/ltr/feature-importance');
    return response.data;
  },

  getBenchmark: async (split = 'test') => {
    const response = await api.get('/evaluation/benchmark', { params: { split } });
    return response.data;
  },

  getMethodologyWeights: async () => {
    const response = await api.get('/methodology/weights');
    return response.data;
  },
};

export const methodologyApi = {
  getWeights: async () => {
    const response = await api.get('/methodology/weights');
    return response.data;
  },
};

export const healthApi = {
  check: async () => {
    const response = await api.get('/health');
    return response.data;
  },
};

export const registryApi = {
  getVersions: async () => {
    const response = await api.get('/models/registry/versions');
    return response.data;
  },

  getActive: async () => {
    const response = await api.get('/models/registry/active');
    return response.data;
  },

  validate: async (version) => {
    const response = await api.get(`/models/registry/validate/${version}`);
    return response.data;
  },

  compare: async (versionA, versionB) => {
    const response = await api.get('/models/registry/compare', {
      params: { version_a: versionA, version_b: versionB },
    });
    return response.data;
  },

  // There is no endpoint that changes the live model: promotion is by deployment (see DEPLOY.md).
};

export const systemApi = {
  getMetrics: async () => {
    const response = await api.get('/metrics');
    return response.data;
  },

  getLatencyBenchmark: async (iterations = 20) => {
    const response = await api.get('/system/latency-benchmark', {
      params: { iterations },
    });
    return response.data;
  },
};

export default api;
