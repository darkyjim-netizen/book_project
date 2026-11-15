<template>
  <div class="min-h-screen">
    <AppHeader v-if="$route.name !== 'login' && $route.name !== 'register'" />
    <main><RouterView /></main>
    <footer v-if="$route.name !== 'login' && $route.name !== 'register'" class="site-footer">
      © 2026 북적북적 · FastAPI와 Vue로 만든 회원 서비스
    </footer>
  </div>
</template>
<script setup>
import AppHeader from './components/AppHeader.vue'
</script>
