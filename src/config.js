const API_BASE_URL = import.meta.env.DEV
  ? 'http://localhost:8765'
  : 'http://8.153.195.92:8765'

export const BACKEND_ENDPOINTS = {
  register: `${API_BASE_URL}/register`,
  submitForm: `${API_BASE_URL}/submit-form`,
  group: `${API_BASE_URL}/group`,
  lessonComplete: `${API_BASE_URL}/lesson-complete`,
  completion: `${API_BASE_URL}/completion`,
}

export function getApiBaseUrl() {
  return API_BASE_URL
}
