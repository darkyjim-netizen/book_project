import http from './http'

// [백엔드 연동 수정] 이 파일은 백엔드의 회원 API(/api/v1/members, /auth)에 맞춰 고쳤습니다.
export const memberApi = {
  getMe() {
    return http.get('/members/me').then(r => r.data)
  },
  // PATCH → PUT : 백엔드는 PATCH 를 쓰지 않고 PUT /members/me 로 내 정보를 수정합니다.
  updateMe(payload) {
    return http.put('/members/me', payload).then(r => r.data)
  },
  // DELETE /members/me → POST /auth/withdraw : 백엔드는 삭제가 아니라 "탈퇴 처리" API를 따로 둡니다.
  deleteMe(payload = {}) {
    return http.post('/auth/withdraw', { reason_code: 'ETC', ...payload }).then(r => r.data)
  },
  // [추가] 맞춤 추천. 배치(recommend_batch.py)가 ai.recommendations 에 저장한 SASRec 결과를 읽습니다.
  // 구매 이력이 없는 신규 회원·비회원은 인기 도서(POPULAR)가 옵니다.
  recommendations(limit = 5) {
    return http.get('/ai/recommendations', { params: { limit } }).then(r => r.data)
  }
}