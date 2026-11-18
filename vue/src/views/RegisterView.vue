<template>
  <section class="login-page signup-page">
    <div class="signup-panel">
      <RouterLink to="/login" class="signup-back">← 로그인으로</RouterLink>
      <div class="signup-heading"><p class="signup-kicker">BOOKBOOK ACCOUNT</p><h1>회원가입</h1><p class="signup-intro">북적북적과 함께 나만의 책장을 만들어 보세요.</p></div>
      <p class="signup-required-note"><span aria-hidden="true">*</span> 필수 입력 항목</p>
      <AlertMessage :message="error" />
      <form class="signup-form" @submit.prevent="submit">
        <div class="signup-row"><label for="signup-email">이메일 <span aria-hidden="true">*</span></label><div><input id="signup-email" v-model.trim="form.email" type="email" required maxlength="190" autocomplete="email" placeholder="이메일을 입력해 주세요" /><small>로그인할 때 아이디로 사용됩니다.</small></div></div>
        <div class="signup-row"><label for="signup-password">비밀번호 <span aria-hidden="true">*</span></label><div><div class="signup-password"><input id="signup-password" v-model="form.password" :type="showPassword ? 'text' : 'password'" required minlength="8" maxlength="64" autocomplete="new-password" placeholder="비밀번호를 입력해 주세요" aria-describedby="signup-password-hint" /><button type="button" :aria-label="showPassword ? '비밀번호 숨기기' : '비밀번호 보기'" @click="showPassword = !showPassword">{{ showPassword ? '숨기기' : '보기' }}</button></div><small id="signup-password-hint">8~64자, 영문과 숫자를 포함해 주세요.</small></div></div>
        <div class="signup-row"><label for="signup-password-confirm">비밀번호 확인 <span aria-hidden="true">*</span></label><div><input id="signup-password-confirm" v-model="passwordConfirm" type="password" required minlength="8" maxlength="64" autocomplete="new-password" placeholder="비밀번호를 다시 입력해 주세요" /></div></div>
        <div class="signup-row"><label for="signup-name">이름 <span aria-hidden="true">*</span></label><div><input id="signup-name" v-model.trim="form.name" required maxlength="60" autocomplete="name" placeholder="이름을 입력해 주세요" /></div></div>
        <div class="signup-row"><label for="signup-phone">휴대전화 <small>(선택)</small></label><div><input id="signup-phone" v-model.trim="form.phone" type="tel" maxlength="20" autocomplete="tel" placeholder="010-1234-5678" /></div></div>
        <div class="signup-actions"><RouterLink to="/login">취소</RouterLink><button class="signup-submit" type="submit" :disabled="saving">{{ saving ? '가입 처리 중...' : '가입하기' }}</button></div>
      </form>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/authStore'
import { apiError } from '../utils/format'
import AlertMessage from '../components/AlertMessage.vue'

const auth = useAuthStore()
const router = useRouter()
const form = reactive({ email: '', name: '', phone: '', password: '' })
const showPassword = ref(false)
const passwordConfirm = ref('')
const error = ref('')
const saving = ref(false)

async function submit() {
  error.value = ''
  if (form.password !== passwordConfirm.value) { error.value = '비밀번호 확인이 일치하지 않습니다.'; return }
  saving.value = true
  try {
    // [백엔드 연동 수정] 백엔드는 password_confirm 을 함께 받아서 서버에서도 일치 여부를 검사합니다.
    await auth.register({ ...form, password_confirm: passwordConfirm.value, phone: form.phone || null })
    await router.push({ name: 'login', query: { registered: '1' } })
  } catch (e) { error.value = apiError(e) }
  finally { saving.value = false }
}
</script>
