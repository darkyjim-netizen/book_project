<template>
  <section class="page max-w-3xl">
    <!-- [백엔드 연동 수정] 백엔드에는 회원 권한 변경·삭제 API가 없어 해당 UI를 없애고,
         상태 변경(PUT /admin/members/{id}/status, ADMIN 전용)만 남겼습니다.
         상세 응답은 { member, order_stats, segment, churn } 형태이며, AI 분석(segment/churn)이 있으면 함께 보여 줍니다. -->
    <div class="mb-6"><RouterLink to="/admin/members" class="text-sm font-semibold text-blue-600">← 회원 목록</RouterLink><h1 class="mt-3 text-3xl font-extrabold">회원 상세 관리</h1></div>
    <AlertMessage :message="error" />
    <AlertMessage :message="success" type="success" />
    <div v-if="member" class="card mt-4">
      <div class="mb-5 flex items-center justify-between"><h2 class="text-lg font-bold">회원 #{{ member.member_id }}</h2><span class="text-xs text-slate-400">{{ formatDate(member.created_at) }} 가입</span></div>
      <dl class="grid gap-4 sm:grid-cols-2">
        <div><dt class="text-xs text-slate-400">이름</dt><dd class="mt-1 font-semibold">{{ member.name }}</dd></div>
        <div><dt class="text-xs text-slate-400">닉네임</dt><dd class="mt-1 font-semibold">{{ member.nickname || '-' }}</dd></div>
        <div><dt class="text-xs text-slate-400">이메일</dt><dd class="mt-1 font-semibold">{{ member.email }}</dd></div>
        <div><dt class="text-xs text-slate-400">권한</dt><dd class="mt-1 font-semibold">{{ member.role }}</dd></div>
        <div><dt class="text-xs text-slate-400">등급</dt><dd class="mt-1 font-semibold">{{ member.grade?.grade_name || '-' }}</dd></div>
        <div><dt class="text-xs text-slate-400">포인트 / 주문 / 누적 결제</dt><dd class="mt-1 font-semibold">{{ member.point_balance }}P / {{ member.order_count }}건 / {{ Number(member.total_paid || 0).toLocaleString('ko-KR') }}원</dd></div>
        <div><dt class="text-xs text-slate-400">마지막 로그인</dt><dd class="mt-1 font-semibold">{{ formatDate(member.last_login_at) }}</dd></div>
      </dl>
      <div class="mt-6 border-t border-slate-100 pt-5">
        <label class="label">계정 상태</label>
        <select v-model="status" class="field sm:max-w-xs"><option value="ACTIVE">활성</option><option value="DORMANT">휴면</option><option value="SUSPENDED">정지</option></select>
        <p class="mt-2 text-xs text-slate-400">상태 변경은 최고 관리자(ADMIN)만 가능합니다. 현재 상태: {{ member.status }}</p>
      </div>
      <div class="mt-5 flex justify-end"><button class="btn-primary" :disabled="saving || status === member.status" @click="save">상태 저장</button></div>
    </div>
    <div v-if="detail && (detail.segment || detail.churn)" class="card mt-4">
      <h2 class="mb-3 text-lg font-bold">AI 고객 분석</h2>
      <dl v-if="detail.segment" class="grid gap-3 sm:grid-cols-2">
        <div v-for="(v, k) in detail.segment" :key="k"><dt class="text-xs text-slate-400">{{ k }}</dt><dd class="mt-1 font-semibold">{{ v ?? '-' }}</dd></div>
      </dl>
      <dl v-if="detail.churn" class="mt-4 grid gap-3 sm:grid-cols-2">
        <div v-for="(v, k) in detail.churn" :key="k"><dt class="text-xs text-slate-400">{{ k }}</dt><dd class="mt-1 font-semibold">{{ typeof v === 'object' ? JSON.stringify(v) : (v ?? '-') }}</dd></div>
      </dl>
    </div>
  </section>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { adminApi } from '../api/adminApi'
import { useAuthStore } from '../stores/authStore'
import { apiError, formatDate } from '../utils/format'
import AlertMessage from '../components/AlertMessage.vue'
const props = defineProps({ id: { type: String, required: true } })
const auth = useAuthStore()
const detail = ref(null)
const member = ref(null)
const status = ref('ACTIVE')
const saving = ref(false)
const error = ref('')
const success = ref('')
async function load() {
  try {
    detail.value = await adminApi.detail(props.id)
    member.value = detail.value.member
    status.value = member.value.status
  } catch (e) { error.value = apiError(e) }
}
async function save() {
  error.value = ''; success.value = ''; saving.value = true
  try {
    member.value = await adminApi.updateStatus(props.id, status.value)
    status.value = member.value.status
    success.value = '계정 상태가 변경되었습니다.'
    if (Number(props.id) === auth.user?.member_id) await auth.fetchMe()
  } catch (e) { error.value = apiError(e) }
  finally { saving.value = false }
}
onMounted(load)
</script>