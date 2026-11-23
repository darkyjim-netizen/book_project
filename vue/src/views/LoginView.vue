<template>
  <section class="login-page">
    <div class="login-panel">
      <RouterLink to="/login" class="login-brand" aria-label="북적북적 로그인">
        <img class="login-logo" src="/assets/bookjjeok-logo-new.png" alt="북적북적 로고" />
      </RouterLink>
      <h1>다시 만나 반가워요</h1>
      <p class="login-intro">로그인하고 나만의 책장을 이어가세요.</p>
      <AlertMessage :message="error || (typeof route.query.oauth_error === 'string' ? route.query.oauth_error : '')" />
      <AlertMessage v-if="route.query.registered === '1'" message="회원가입이 완료되었습니다. 로그인해 주세요." type="success" />
      <form class="login-form" @submit.prevent="submit">
        <label class="sr-only" for="login-username">이메일</label>
        <input id="login-username" v-model.trim="form.email" type="email" autocomplete="username" required
          maxlength="190" placeholder="이메일" />
        <label class="sr-only" for="login-password">비밀번호</label>
        <input id="login-password" v-model="form.password" type="password" autocomplete="current-password" required
          placeholder="비밀번호" />
        <button class="login-button" type="submit" :disabled="auth.loading">{{ auth.loading ? '로그인 중...' : '로그인'
          }}</button>
      </form>
      <div class="login-alternatives" aria-label="비회원 주문 조회">
        <div class="login-divider"><span>또는</span></div>
        <a class="alternative-button google-button" :href="googleLoginUrl">
          <svg class="google-icon" viewBox="0 0 48 48" aria-hidden="true"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>
          Google로 로그인
        </a>
        <RouterLink class="alternative-button guest-button" :to="{ name: 'guestOrder' }">비회원 주문조회</RouterLink>
      </div>
      <div class="account-links">
        <RouterLink to="/register">회원가입</RouterLink>
      </div>
      <a class="shop-entry-link" href="/main">메인 쇼핑몰 보기 <span aria-hidden="true">→</span></a>
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
const form = reactive({ email: '', password: '' })
// 구글 로그인: 백엔드가 구글 로그인 페이지로 보내고, 끝나면 이 화면 주소(origin)로 돌아온다.
const googleLoginUrl = `/api/v1/auth/google/login?origin=${encodeURIComponent(window.location.origin)}`

async function submit() {
  error.value = ''
  try {
    await auth.login(form)
    const safeRedirect = typeof route.query.redirect === 'string' && route.query.redirect.startsWith('/') && !route.query.redirect.startsWith('//') ? route.query.redirect : null
    // 관리자는 redirect 주소와 상관없이 항상 대시보드로
    const redirect = auth.isAdmin ? '/store-admin/dashboard' : (safeRedirect || '/main')
    await router.push(redirect) 
  } catch (e) { error.value = apiError(e) }
}
</script>

<style scoped>
/* .alternative-button(아래쪽에 정의)의 border:0 보다 우선하도록 클래스 두 개로 지정 */
.alternative-button.google-button {
  gap: 10px;
  min-height: 52px;
  background: #fff;
  border: 1.5px solid #d9d2e3;
  color: #2b2430;
  font-size: 16px;
  font-weight: 700;
  box-shadow: 0 2px 6px rgba(60, 40, 90, .08);
  transition: background .15s, border-color .15s, box-shadow .15s
}

.alternative-button.google-button:hover {
  background: #faf8fd;
  border-color: #b9a6d6;
  box-shadow: 0 4px 12px rgba(60, 40, 90, .12)
}

.alternative-button.google-button:focus-visible {
  outline: 3px solid #bca4df;
  outline-offset: 2px
}

.google-icon {
  width: 22px;
  height: 22px;
  flex: none
}

.login-alternatives {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  margin-top: 20px
}

.login-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #8b8090;
  font-size: 13px
}

.login-divider::before,
.login-divider::after {
  content: '';
  height: 1px;
  flex: 1;
  background: #e8e1ec
}

.alternative-button {
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 48px;
  border: 0;
  border-radius: 14px;
  font: inherit;
  font-weight: 700;
  text-decoration: none
}

.login-button {
  border-radius: 14px
}

.login-button,
.guest-button {
  background: #65419a;
  color: #fff
}

.login-button:hover,
.guest-button:hover {
  background: #51316e
}

.login-button:disabled {
  background: #a99ab9
}

.account-links a {
  color: #65419a
}
</style>
