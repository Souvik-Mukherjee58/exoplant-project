import axios from 'axios'

const API_BASE_URL = 'http://localhost:8000/api/v1'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor for logging
api.interceptors.request.use(
  (config) => {
    // console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`)
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      // Server responded with error status
      console.error(`API Error ${error.response.status}:`, error.response.data)
    } else if (error.request) {
      // Request made but no response
      console.error('API Error: No response from server')
    } else {
      // Other error
      console.error('API Error:', error.message)
    }
    return Promise.reject(error)
  }
)

export const planetsApi = {
  getAll: async (params = {}) => {
    const response = await api.get('/planets', { params })
    return response.data
  },

  getByName: async (planetName) => {
    const response = await api.get(`/planets/${encodeURIComponent(planetName)}`)
    return response.data
  },

  getTopTargets: async (params = {}) => {
    const response = await api.get('/top-targets', { params })
    return response.data
  }
}

export const analyticsApi = {
  getAnalysis: async () => {
    const response = await api.get('/analysis')
    return response.data
  },

  getAnomalyPCA: async () => {
    const response = await api.get('/anomaly-pca')
    return response.data
  }
}

export const healthApi = {
  check: async () => {
    const response = await api.get('/health')
    return response.data
  }
}

export default api