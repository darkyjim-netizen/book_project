<template>
  <section class="page max-w-3xl">
    <!-- [백엔드 연동 수정] 백엔드 회원 정보 형식에 맞춤: id → member_id, display_name → name, 아이디(username) 삭제.
         이메일은 수정할 수 없고(PUT /members/me 는 이름·닉네임·전화번호 등만 받음) 읽기 전용으로 표시합니다.
         탈퇴는 DELETE 가 아니라 POST /auth/withdraw 입니다. 등급·포인트 표시를 추가했습니다. -->
    <div class="mb-6"><p class="text-sm font-bold uppercase tracking-widest text-blue-600">My account</p><h1 class="mt-2 text-3xl font-extrabold">마이페이지</h1><p class="mt-2 text-slate-500">본인 계정 정보 조회 및 수정</p></div>
    <AlertMessage :message="error" />
    <AlertMessage :message="success" type="success" />
    <div v-if="profile" class="card mt-4">
      <div class="mb-5 flex items-center justify-between"><h2 class="text-lg font-bold">회원 정보</h2><span class="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700">{{ profile.role }}</span></div>
      <form class="space-y-4" @submit.prevent="save">
        <div><label class="label">회원 번호</label><input :value="profile.member_id" class="field bg-slate-50" disabled /></div>
        <div><label class="label">이메일 (로그인 아이디)</label><input :value="profile.email" class="field bg-slate-50" disabled /></div>
        <div><label class="label">이름</label><input v-model.trim="form.name" class="field" required maxlength="60" /></div>
        <div><label class="label">닉네임</label><input v-model.trim="form.nickname" class="field" maxlength="60" /></div>
        <div><label class="label">전화번호</label><input v-model.trim="form.phone" class="field" maxlength="20" /></div>
        <div><label class="label">등급 / 포인트</label><input :value="`${profile.grade?.grade_name || '-'} / ${profile.point_balance ?? 0}P`" class="field bg-slate-50" disabled /></div>
        <div><label class="label">가입일</label><input :value="formatDate(profile.created_at)" class="field bg-slate-50" disabled /></div>
        <div class="flex justify-end"><button class="btn-primary" :disabled="saving">{{ saving ? '저장 중...' : '변경사항 저장' }}</button></div>
      </form>
    </div>
    <div class="mt-5 rounded-2xl border border-rose-200 bg-rose-50 p-5">
      <h2 class="font-bold text-rose-800">회원 탈퇴</h2><p class="mt-1 text-sm text-rose-700">탈퇴하면 계정을 더 이상 이용할 수 없고 현재 로그인 세션이 종료됩니다.</p>
      <button class="btn-danger mt-4" @click="withdraw">회원 탈퇴</button>
    </div>
  </section>
</template>
<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { memberApi } from '../api/memberApi'
import { useAuthStore } from '../stores/authStore'
import { apiError, formatDate } from '../utils/format'
import AlertMessage from '../components/AlertMessage.vue'
const auth = useAuthStore()
const router = useRouter()
const profile = ref(null)
const form = reactive({ name: '', nickname: '', phone: '' })
const error = ref('')
const success = ref('')
const saving = ref(false)
function fill(p) {
  form.name = p.name || ''
  form.nickname = p.nickname || ''
  form.phone = p.phone || ''
}
async function load() {
  try {
    profile.value = await memberApi.getMe()
    fill(profile.value)
  } catch (e) { error.value = apiError(e) }
}
async function save() {
  error.value = ''; success.value = ''; saving.value = true
  try {
    profile.value = await memberApi.updateMe({ name: form.name, nickname: form.nickname || null, phone: form.phone || null })
    fill(profile.value)
    auth.setUser(profile.value)
    success.value = '회원 정보가 수정되었습니다.'
  } catch (e) { error.value = apiError(e) }
  finally { saving.value = false }
}
async function withdraw() {
  if (!confirm('정말 탈퇴하시겠습니까? 이 작업은 되돌릴 수 없습니다.')) return
  try {
    await memberApi.deleteMe()
    auth.setUser(null)
    await router.push('/register')
  } catch (e) { error.value = apiError(e) }
}
onMounted(load)
</script>