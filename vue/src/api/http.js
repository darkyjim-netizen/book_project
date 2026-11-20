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
    const data = error.response?.data
    // [백엔드 연동 수정] 원래는 FastAPI 기본 오류 형식(detail)만 읽었습니다.
    // 이 백엔드는 { success: false, error: { code, message, detail } } 형식으로 응답하므로
    // error.message / error.detail 을 읽도록 바꿨습니다. (바꾸지 않으면 오류 메시지가 항상 "요청에 실패했습니다."로 나옵니다.)
    const body = data?.error || {}
    const detail = body.detail ?? data?.detail
    const message = Array.isArray(detail)
      ? detail.map(v => v.msg || v.message || JSON.stringify(v)).join(', ')
      : typeof detail === 'string' && detail
        ? detail
        : body.message || data?.message || (status ? '요청에 실패했습니다.' : error.message) || '요청에 실패했습니다.'
    error.userMessage = status
      ? message
      : `API 서버에 연결할 수 없습니다. (${message})`
    return Promise.reject(error)
  }
)

export default http