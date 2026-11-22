<template>
  <div class="topline storefront-top-banner"><p>책 읽는 즐거움, 오늘도 한 권 가까이 / 회원은 배송비 무료</p><RouterLink v-if="auth.initialized && !auth.isAuthenticated" to="/register">회원가입하고 시작하기 →</RouterLink></div>
</template>
<script setup>
import { useAuthStore } from '../stores/authStore.js';
const auth = useAuthStore();
</script>
<style scoped>
.storefront-top-banner.topline{display:flex;align-items:center;justify-content:center;box-sizing:border-box;width:100%;height:auto;min-height:34px;padding:7px 20px;gap:20px;background:#f3edf9;color:#68478c;font-size:13px;line-height:1.5}.storefront-top-banner p{margin:0}.storefront-top-banner a{color:inherit;font-weight:700;white-space:nowrap}@media(max-width:600px){.storefront-top-banner.topline{flex-wrap:wrap;gap:4px 12px;padding:6px 14px;font-size:12px}}
</style>
