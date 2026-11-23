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
