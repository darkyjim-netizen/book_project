<template>
  <header class="site-header">
    <div class="site-header-inner">
      <RouterLink to="/dashboard" class="dashboard-brand"><img class="wordmark-logo" src="/assets/bookjjeok-logo-new.png" alt="북적북적" /></RouterLink>
      <nav v-if="auth.isAuthenticated" class="header-actions" aria-label="계정 메뉴">
        <RouterLink :to="auth.isAdmin ? '/store-admin/dashboard' : '/dashboard'">대시보드</RouterLink>
        <RouterLink to="/profile">마이페이지</RouterLink>
        
        <a class="shop-entry-button" href="/main">메인 쇼핑몰</a>
        <button class="logout-button" @click="signOut">로그아웃</button>
      </nav>
      <nav v-else class="header-actions" aria-label="계정 메뉴">
        <a class="shop-entry-button" href="/main">메인 쇼핑몰</a>
        <RouterLink to="/login">로그인</RouterLink>
        <RouterLink class="header-register" to="/register">회원가입</RouterLink>
      </nav>
    </div>
  </header>
</template>
<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/authStore'
const auth = useAuthStore()
const router = useRouter()
async function signOut() {
  await auth.logout()
  await router.push('/login')
}
</script>
