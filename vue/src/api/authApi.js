import http from './http'

export const authApi = {
  register(payload) {
    // [백엔드 연동 수정] 회원가입 경로 /auth/register → /auth/signup (백엔드 라우터의 이름에 맞춤)
    return http.post('/auth/signup', payload).then(r => r.data)
  },
  login(payload) {
    return http.post('/auth/login', payload).then(r => r.data)
  },
  logout() {
    return http.post('/auth/logout').then(r => r.data)
  },
  me() {
    return http.get('/auth/me').then(r => r.data)
  }
}