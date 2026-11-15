import http from './http'

export const adminApi = {
  list(params = {}) {
    return http.get('/admin/members', { params }).then(r => r.data)
  },
  detail(id) {
    return http.get(`/admin/members/${id}`).then(r => r.data)
  },
  update(id, payload) {
    return http.patch(`/admin/members/${id}`, payload).then(r => r.data)
  },
  remove(id) {
    return http.delete(`/admin/members/${id}`).then(r => r.data)
  }
}