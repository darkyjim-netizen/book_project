import http from './http'

// [백엔드 연동 수정] 백엔드의 관리자 회원 API(/api/v1/admin/members)에 맞춰 고쳤습니다.
// 백엔드에는 회원 "권한 변경"과 "삭제" API가 없어서 update/remove 는 없애고 상태 변경만 남겼습니다.
export const adminApi = {
  // 응답: { success, items: [...], meta: { page, size, total, total_pages } }
  list(params = {}) {
    return http.get('/admin/members', { params }).then(r => r.data)
  },
  // 응답: { member, order_stats, segment, churn }  (segment/churn 은 AI 분석 결과이며 없을 수 있음)
  detail(id) {
    return http.get(`/admin/members/${id}`).then(r => r.data)
  },
  // PATCH /admin/members/{id} → PUT /admin/members/{id}/status
  // 상태 값: ACTIVE | DORMANT | SUSPENDED (최고 관리자 ADMIN 만 변경 가능)
  updateStatus(id, status) {
    return http.put(`/admin/members/${id}/status`, { status }).then(r => r.data)
  }
}