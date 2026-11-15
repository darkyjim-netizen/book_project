import axios from 'axios'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: Number(import.meta.env.VITE_API_TIMEOUT || 15000),
  withCredentials: true,
  headers: { Accept: 'application/json' }
})

http.interceptors.response.use(
  response => response,
  error => {
    const status = error.response?.status
    const detail = error.response?.data?.detail
    const message = typeof detail === 'string'
      ? detail
      : Array.isArray(detail)
        ? detail.map(v => v.msg || JSON.stringify(v)).join(', ')
        : error.response?.data?.message || error.message || '요청에 실패했습니다.'
    error.userMessage = status
      ? `${status}: ${message}`
      : `API 서버에 연결할 수 없습니다. (${message})`
    return Promise.reject(error)
  }
)

export default http