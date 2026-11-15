import http from './http'

export const authApi = {
  register(payload) {
    return http.post('/auth/register', payload).then(r => r.data)
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