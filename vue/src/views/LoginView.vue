<template>
  <section class="login-page">
    <div class="login-panel">
      <RouterLink to="/login" class="login-brand" aria-label="북적북적 로그인">
        <img class="login-logo" src="/assets/bookjjeok-logo-new.png" alt="북적북적 로고" />
      </RouterLink>
      <h1>다시 만나 반가워요</h1>
      <p class="login-intro">로그인하고 나만의 책장을 이어가세요.</p>
      <AlertMessage :message="error" />
      <AlertMessage v-if="route.query.registered === '1'" message="회원가입이 완료되었습니다. 로그인해 주세요." type="success" />
      <form class="login-form" @submit.prevent="submit">
        <!-- [백엔드 연동 수정] 아이디(username) 로그인 → 이메일 로그인. 백엔드는 POST /auth/login 에 { email, password } 를 받습니다. -->
        <label class="sr-only" for="login-email">이메일</label>
        <input id="login-email" v-model.trim="form.email" type="email" autocomplete="username" required maxlength="255" placeholder="이메일" />
        <label class="sr-only" for="login-password">비밀번호</label>
        <input id="login-password" v-model="form.password" type="password" autocomplete="current-password" required placeholder="비밀번호" />
        <button class="login-button" type="submit" :disabled="auth.loading">{{ auth.loading ? '로그인 중...' : '로그인' }}</button>
      </form>
      <div class="account-links"><RouterLink to="/register">회원가입</RouterLink><span aria-hidden="true"></span><small>계정 문제가 있으면 관리자에게 문의해 주세요.</small></div>
      <a class="shop-entry-link" href="/shop.html">메인 쇼핑몰 보기 <span aria-hidden="true">→</span></a>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/authStore'
import { apiError } from '../utils/format'
import AlertMessage from '../components/AlertMessage.vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const error = ref('')
// [백엔드 연동 수정] username → email (백엔드 LoginRequest 필드 이름)
const form = reactive({ email: '', password: '' })

async function submit() {
  error.value = ''
  try {
    await auth.login(form)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/dashboard'
    if (redirect.startsWith('/shop.html')) window.location.assign(redirect)
    else await router.push(redirect)
  } catch (e) { error.value = apiError(e) }
}
</script>
