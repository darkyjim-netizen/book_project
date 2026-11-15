<template>
  <section class="page">
    <div class="mb-7"><p class="text-sm font-bold uppercase tracking-widest text-blue-600">Administration</p><h1 class="mt-2 text-3xl font-extrabold">회원 관리</h1><p class="mt-2 text-slate-500">관리자 전용 전체 회원 목록</p></div>
    <AlertMessage :message="error" />
    <div class="card mt-4">
      <div class="mb-4 flex flex-wrap items-center justify-between gap-3"><h2 class="font-bold">회원 목록</h2><span class="muted">총 {{ total }}명</span></div>
      <div class="mb-4 flex items-center gap-2"><label class="text-sm text-slate-500">페이지 크기</label><select v-model.number="size" class="field mt-0 w-24" @change="load(1)"><option :value="10">10</option><option :value="20">20</option><option :value="50">50</option><option :value="100">100</option></select><button class="btn-secondary ml-auto" @click="load(page)">새로고침</button></div>
      <div v-if="loading" class="p-10 text-center text-slate-500">불러오는 중...</div>
      <div v-else class="overflow-x-auto">
        <table class="w-full min-w-[700px] text-left text-sm">
          <thead class="bg-slate-50 text-xs uppercase text-slate-500"><tr><th class="px-3 py-3">번호</th><th class="px-3 py-3">아이디</th><th class="px-3 py-3">이름</th><th class="px-3 py-3">이메일</th><th class="px-3 py-3">권한</th><th class="px-3 py-3">상태</th><th class="px-3 py-3">관리</th></tr></thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-for="m in members" :key="m.id" class="hover:bg-slate-50">
              <td class="px-3 py-3">{{ m.id }}</td><td class="px-3 py-3 font-semibold">{{ m.username }}</td><td class="px-3 py-3">{{ m.display_name }}</td><td class="px-3 py-3">{{ m.email }}</td>
              <td class="px-3 py-3"><span class="rounded-full px-2 py-1 text-xs font-bold" :class="m.role === 'admin' ? 'bg-violet-100 text-violet-700' : 'bg-slate-100 text-slate-600'">{{ m.role }}</span></td>
              <td class="px-3 py-3"><span class="rounded-full px-2 py-1 text-xs font-bold" :class="m.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'">{{ m.is_active ? '활성' : '비활성' }}</span></td>
              <td class="px-3 py-3"><RouterLink :to="`/admin/members/${m.id}`" class="font-semibold text-blue-600 hover:underline">상세</RouterLink></td>
            </tr>
            <tr v-if="!members.length"><td colspan="7" class="px-3 py-10 text-center text-slate-400">회원 데이터가 없습니다.</td></tr>
          </tbody>
        </table>
      </div>
      <div class="mt-5 flex items-center justify-center gap-3"><button class="btn-secondary" :disabled="page <= 1 || loading" @click="load(page - 1)">이전</button><span class="text-sm text-slate-600">{{ page }} 페이지</span><button class="btn-secondary" :disabled="members.length < size || loading" @click="load(page + 1)">다음</button></div>
    </div>
  </section>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { adminApi } from '../api/adminApi'
import { apiError } from '../utils/format'
import AlertMessage from '../components/AlertMessage.vue'
const members = ref([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const loading = ref(false)
const error = ref('')
async function load(nextPage = 1) {
  loading.value = true; error.value = ''
  try {
    const data = await adminApi.list({ page: nextPage, size: size.value })
    members.value = data.items || []
    total.value = data.total || 0
    page.value = data.page || nextPage
  } catch (e) { error.value = apiError(e) }
  finally { loading.value = false }
}
onMounted(() => load())
</script>