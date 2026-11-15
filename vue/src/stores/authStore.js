import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { authApi } from '../api/authApi'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const initialized = ref(false)
  const loading = ref(false)
  const isAuthenticated = computed(() => Boolean(user.value))
  // [백엔드 연동 수정] 백엔드의 권한 값은 소문자 'admin' 이 아니라 대문자 'USER' / 'ADMIN' 입니다.
  const isAdmin = computed(() => user.value?.role === 'ADMIN')

  async function fetchMe() {
    loading.value = true
    try {
      user.value = await authApi.me()
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
      user.value = result.member
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
    try {
      await authApi.logout()
    } finally {
      user.value = null
      initialized.value = true
    }
  }

  function setUser(value) { user.value = value }

  return {
    user, initialized, loading, isAuthenticated, isAdmin,
    fetchMe, login, register, logout, setUser
  }
})