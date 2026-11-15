import http from './http'

export const memberApi = {
  getMe() {
    return http.get('/members/me').then(r => r.data)
  },
  updateMe(payload) {
    return http.patch('/members/me', payload).then(r => r.data)
  },
  deleteMe() {
    return http.delete('/members/me').then(r => r.data)
  }
}