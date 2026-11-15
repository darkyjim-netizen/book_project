<template>
  <section class="page max-w-3xl">
    <div class="mb-6"><RouterLink to="/admin/members" class="text-sm font-semibold text-blue-600">← 회원 목록</RouterLink><h1 class="mt-3 text-3xl font-extrabold">회원 상세 관리</h1></div>
    <AlertMessage :message="error" />
    <AlertMessage :message="success" type="success" />
    <div v-if="member" class="card mt-4">
      <div class="mb-5 flex items-center justify-between"><h2 class="text-lg font-bold">회원 #{{ member.id }}</h2><span class="text-xs text-slate-400">{{ formatDate(member.created_at) }} 가입</span></div>
      <dl class="grid gap-4 sm:grid-cols-2">
        <div><dt class="text-xs text-slate-400">아이디</dt><dd class="mt-1 font-semibold">{{ member.username }}</dd></div>
        <div><dt class="text-xs text-slate-400">표시 이름</dt><dd class="mt-1 font-semibold">{{ member.display_name }}</dd></div>
        <div><dt class="text-xs text-slate-400">이메일</dt><dd class="mt-1 font-semibold">{{ member.email }}</dd></div>
        <div><dt class="text-xs text-slate-400">수정일</dt><dd class="mt-1 font-semibold">{{ formatDate(member.updated_at) }}</dd></div>
      </dl>
      <div class="mt-6 grid gap-4 border-t border-slate-100 pt-5 sm:grid-cols-2">
        <div><label class="label">회원 권한</label><select v-model="form.role" class="field"><option value="member">member</option><option value="admin">admin</option></select></div>
        <div><label class="label">계정 상태</label><select v-model="activeValue" class="field"><option value="true">활성</option><option value="false">비활성</option></select></div>
      </div>
      <div class="mt-5 flex flex-wrap justify-end gap-2"><button class="btn-primary" :disabled="saving" @click="save">변경사항 저장</button><button class="btn-danger" @click="remove">회원 삭제</button></div>
    </div>
  </section>
</template>
<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { adminApi } from '../api/adminApi'
import { useAuthStore } from '../stores/authStore'
import { apiError, formatDate } from '../utils/format'
import AlertMessage from '../components/AlertMessage.vue'
const props = defineProps({ id: { type: String, required: true } })
const router = useRouter()
const auth = useAuthStore()
const member = ref(null)
const form = reactive({ role: 'member' })
const activeValue = ref('true')
const saving = ref(false)
const error = ref('')
const success = ref('')
async function load() {
  try {
    member.value = await adminApi.detail(props.id)
    form.role = member.value.role
    activeValue.value = String(member.value.is_active)
  } catch (e) { error.value = apiError(e) }
}
async function save() {
  error.value = ''; success.value = ''; saving.value = true
  try {
    member.value = await adminApi.update(props.id, { role: form.role, is_active: activeValue.value === 'true' })
    success.value = '회원 권한 및 상태가 변경되었습니다.'
    // 자기 자신의 권한이 바뀌었다면 서버 상태를 다시 확인합니다.
    if (Number(props.id) === auth.user?.id) await auth.fetchMe()
  } catch (e) { error.value = apiError(e) }
  finally { saving.value = false }
}
async function remove() {
  if (!confirm('이 회원을 삭제하시겠습니까?')) return
  try {
    await adminApi.remove(props.id)
    await router.push('/admin/members')
  } catch (e) { error.value = apiError(e) }
}
onMounted(load)
</script>