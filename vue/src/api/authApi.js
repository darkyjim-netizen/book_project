import http from './http'

export const authApi = {
  checkEmail(email) {
    return http.get('/api/v1/auth/check-email', { params: { email } }).then(r => r.data)
  },
  checkName(name) {
    return http.get('/api/v1/auth/check-name', { params: { name } }).then(r => r.data)
  },
  register(payload) {
    return http.post('/api/v1/auth/signup', payload).then(r => r.data)
  },
  login(payload) {
    return http.post('/api/v1/auth/login', payload).then(r => r.data)
  },
  logout() {
    return http.post('/api/v1/auth/logout').then(r => r.data)
  },
  me() {
    return http.get('/api/v1/auth/me').then(r => r.data)
  }
}