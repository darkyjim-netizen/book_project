import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { authApi } from '../api/authApi'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const initialized = ref(false)
  const loading = ref(false)
  const isAuthenticated = computed(() => Boolean(user.value))
  const isAdmin = computed(() => ['ADMIN', 'STAFF'].includes(user.value?.role))

  function normalizeMember(member) {
    return member ? { ...member, id: member.member_id, username: member.email, display_name: member.nickname || member.name, is_active: member.status === 'ACTIVE' } : null
  }

  async function fetchMe() {
    loading.value = true
    try {
      user.value = normalizeMember(await authApi.me())
      return user.value
    } catch (error) {
      user.value = null
      return null
    } finally {
      initialized.value = true
      loading.value = false
    }
  }

  async function login(payload) {
    loading.value = true
    try {
      const result = await authApi.login(payload)
      // 응답의 member는 화면 상태에 반영하고, 세션 쿠키는 브라우저가 관리합니다.
      user.value = normalizeMember(result.member)
      initialized.value = true
      return result
    } finally {
      loading.value = false
    }
  }

  async function register(payload) {
    return authApi.register(payload)
  }

  async function logout() {
    await authApi.logout()
    user.value = null
    initialized.value = true
  }

  function setUser(value) { user.value = value }

  return {
    user, initialized, loading, isAuthenticated, isAdmin,
    fetchMe, login, register, logout, setUser
  }
})
