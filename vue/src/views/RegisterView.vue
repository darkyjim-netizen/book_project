<template>
  <section class="login-page signup-page">
    <div class="signup-panel">
      <RouterLink to="/login" class="signup-back">← 로그인으로</RouterLink>
      <h1>회원가입</h1>
      <p class="signup-intro">가입에 필요한 정보를 입력해 주세요.</p>
      <AlertMessage :message="error" />
      <form class="signup-form" @submit.prevent="submit">
        <!-- [백엔드 연동 수정] 백엔드 SignupRequest 에 맞춤: 아이디(username) 입력 삭제(이메일이 로그인 아이디),
             display_name → name, 닉네임(선택) 추가, 비밀번호는 8~64자, password_confirm 도 함께 전송 -->
        <label for="signup-email">이메일 (로그인 아이디)</label>
        <input id="signup-email" v-model.trim="form.email" type="email" required maxlength="255" autocomplete="email" placeholder="이메일" />
        <label for="signup-name">이름</label>
        <input id="signup-name" v-model.trim="form.name" required maxlength="60" autocomplete="name" placeholder="이름" />
        <label for="signup-nickname">닉네임 (선택)</label>
        <input id="signup-nickname" v-model.trim="form.nickname" maxlength="60" autocomplete="nickname" placeholder="닉네임" />
        <label for="signup-password">비밀번호</label>
        <input id="signup-password" v-model="form.password" type="password" required minlength="8" maxlength="64" autocomplete="new-password" placeholder="비밀번호 (8~64자)" />
        <label for="signup-password-confirm">비밀번호 확인</label>
        <input id="signup-password-confirm" v-model="passwordConfirm" type="password" required autocomplete="new-password" placeholder="비밀번호를 다시 입력해 주세요" />
        <p class="signup-note">가입 후 기본 권한으로 계정이 생성됩니다.</p>
        <button class="login-button signup-submit" type="submit" :disabled="saving">{{ saving ? '가입 처리 중...' : '가입하기' }}</button>
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
// [백엔드 연동 수정] username/display_name 삭제 → email/name/nickname (백엔드 SignupRequest 필드 이름)
const form = reactive({ email: '', name: '', nickname: '', password: '' })
const passwordConfirm = ref('')
const error = ref('')
const saving = ref(false)

async function submit() {
  error.value = ''
  if (form.password !== passwordConfirm.value) { error.value = '비밀번호 확인이 일치하지 않습니다.'; return }
  saving.value = true
  try {
    // [백엔드 연동 수정] 백엔드는 password_confirm 을 함께 받아서 서버에서도 일치 여부를 검사합니다.
    await auth.register({ ...form, password_confirm: passwordConfirm.value, nickname: form.nickname || null })
    await router.push({ name: 'login', query: { registered: '1' } })
  } catch (e) { error.value = apiError(e) }
  finally { saving.value = false }
}
</script>
