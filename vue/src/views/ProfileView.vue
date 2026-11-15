<template>
  <section class="page max-w-3xl">
    <div class="mb-6"><p class="text-sm font-bold uppercase tracking-widest text-blue-600">My account</p><h1 class="mt-2 text-3xl font-extrabold">마이페이지</h1><p class="mt-2 text-slate-500">본인 계정 정보 조회 및 수정</p></div>
    <AlertMessage :message="error" />
    <AlertMessage :message="success" type="success" />
    <div v-if="profile" class="card mt-4">
      <div class="mb-5 flex items-center justify-between"><h2 class="text-lg font-bold">회원 정보</h2><span class="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700">{{ profile.role }}</span></div>
      <form class="space-y-4" @submit.prevent="save">
        <div><label class="label">회원 번호</label><input :value="profile.id" class="field bg-slate-50" disabled /></div>
        <div><label class="label">아이디</label><input :value="profile.username" class="field bg-slate-50" disabled /></div>
        <div><label class="label">이메일</label><input v-model.trim="form.email" type="email" class="field" required /></div>
        <div><label class="label">표시 이름</label><input v-model.trim="form.display_name" class="field" required maxlength="100" /></div>
        <div><label class="label">가입일</label><input :value="formatDate(profile.created_at)" class="field bg-slate-50" disabled /></div>
        <div class="flex justify-end"><button class="btn-primary" :disabled="saving">{{ saving ? '저장 중...' : '변경사항 저장' }}</button></div>
      </form>
    </div>
    <div class="mt-5 rounded-2xl border border-rose-200 bg-rose-50 p-5">
      <h2 class="font-bold text-rose-800">회원 탈퇴</h2><p class="mt-1 text-sm text-rose-700">탈퇴하면 계정이 삭제되고 현재 로그인 세션이 종료됩니다.</p>
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
const form = reactive({ email: '', display_name: '' })
const error = ref('')
const success = ref('')
const saving = ref(false)
async function load() {
  try {
    profile.value = await memberApi.getMe()
    form.email = profile.value.email
    form.display_name = profile.value.display_name
  } catch (e) { error.value = apiError(e) }
}
async function save() {
  error.value = ''; success.value = ''; saving.value = true
  try {
    profile.value = await memberApi.updateMe({ ...form })
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