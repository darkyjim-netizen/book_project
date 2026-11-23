<template>
  <section class="login-page signup-page">
    <div class="signup-panel">
      <RouterLink to="/login" class="signup-back">← 로그인으로</RouterLink>
      <div class="signup-heading"><h1>회원가입</h1><p class="signup-intro">북적북적과 함께 나만의 책장을 만들어 보세요.</p></div>
      <!-- 구글 간편 가입: 로그인과 같은 API. 처음 오는 구글 계정이면 자동으로 회원가입된다. -->
      <div class="signup-social">
        <a class="signup-google-button" :href="googleLoginUrl">
          <svg class="google-icon" viewBox="0 0 48 48" aria-hidden="true"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>
          Google로 가입하기
        </a>
        <small>구글 계정으로 바로 가입하고 로그인돼요. 가입 축하 혜택도 똑같이 받아요.</small>
        <div class="signup-social-divider"><span>또는 이메일로 가입</span></div>
      </div>
      <p class="signup-required-note"><span aria-hidden="true">*</span> 필수 입력 항목</p>
      <AlertMessage :message="error" />
      <form class="signup-form" @submit.prevent="submit">
        <div class="signup-row"><label for="signup-email">이메일 <span aria-hidden="true">*</span></label><div><div class="signup-check-row"><input id="signup-email" v-model.trim="form.email" type="email" required maxlength="190" autocomplete="email" placeholder="이메일을 입력해 주세요" /><button class="signup-check-button" type="button" :disabled="saving || checking.email || !form.email" aria-label="이메일 중복 확인" @click="checkDuplicate('email')">{{ checking.email ? '확인 중…' : '중복 확인' }}</button></div><small v-if="duplicateMessage.email" class="signup-check-result" :class="checked.email ? 'is-available' : 'is-unavailable'" role="status">{{ checked.email ? '✓ ' : '' }}{{ duplicateMessage.email }}</small><small>로그인할 때 아이디로 사용됩니다.</small></div></div>
        <div class="signup-row"><label for="signup-password">비밀번호 <span aria-hidden="true">*</span></label><div><div class="signup-password"><input id="signup-password" v-model="form.password" :type="showPassword ? 'text' : 'password'" required minlength="8" maxlength="64" autocomplete="new-password" placeholder="비밀번호를 입력해 주세요" aria-describedby="signup-password-hint" /><button type="button" :aria-label="showPassword ? '비밀번호 숨기기' : '비밀번호 보기'" @click="showPassword = !showPassword">{{ showPassword ? '숨기기' : '보기' }}</button></div><small id="signup-password-hint">8~64자, 영문과 숫자를 포함해 주세요.</small></div></div>
        <div class="signup-row"><label for="signup-password-confirm">비밀번호 확인 <span aria-hidden="true">*</span></label><div><input id="signup-password-confirm" v-model="passwordConfirm" type="password" required minlength="8" maxlength="64" autocomplete="new-password" placeholder="비밀번호를 다시 입력해 주세요" /></div></div>
        <div class="signup-row"><label for="signup-name">이름 <span aria-hidden="true">*</span></label><div><input id="signup-name" v-model.trim="form.name" required maxlength="60" autocomplete="name" placeholder="이름을 입력해 주세요" /></div></div>
        <div class="signup-row"><label for="signup-nickname">닉네임 <span aria-hidden="true">*</span></label><div><div class="signup-check-row"><input id="signup-nickname" v-model.trim="form.nickname" required maxlength="60" autocomplete="nickname" placeholder="닉네임을 입력해 주세요" /><button class="signup-check-button" type="button" :disabled="saving || checking.nickname || !form.nickname" aria-label="닉네임 중복 확인" @click="checkDuplicate('nickname')">{{ checking.nickname ? '확인 중…' : '중복 확인' }}</button></div><small v-if="duplicateMessage.nickname" class="signup-check-result" :class="checked.nickname ? 'is-available' : 'is-unavailable'" role="status">{{ checked.nickname ? '✓ ' : '' }}{{ duplicateMessage.nickname }}</small><small>마이페이지에서 표시되는 이름입니다.</small></div></div>
        <div class="signup-row"><label for="signup-phone">휴대전화 <span aria-hidden="true">*</span></label><div><input id="signup-phone" v-model.trim="form.phone" type="tel" maxlength="20" autocomplete="tel" placeholder="010-1234-5678" /></div></div>
        <div class="signup-row"><label for="signup-birth">생년월일 <span aria-hidden="true">*</span></label><div><input id="signup-birth" v-model.trim="birthDate" type="text" inputmode="numeric" pattern="[0-9]{4}-[0-9]{2}-[0-9]{2}" maxlength="10" required autocomplete="bday" placeholder="YYYY-MM-DD (예: 1999-01-01)" @input="formatBirthDate" /></div></div>
        <div class="signup-actions"><RouterLink to="/login">취소</RouterLink><button class="signup-submit" type="submit" :disabled="saving">{{ saving ? '가입 처리 중...' : '가입하기' }}</button></div>
      </form>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/authStore'
import { apiError } from '../utils/format'
import { authApi } from '../api/authApi'
import AlertMessage from '../components/AlertMessage.vue'

const auth = useAuthStore()
const router = useRouter()
const form = reactive({ email: '', name: '', nickname: '', phone: '', password: '' })
const birthDate = ref('')
const showPassword = ref(false)
const passwordConfirm = ref('')
// 구글 간편 가입 (로그인과 같은 백엔드 API. 처음 오는 구글 계정은 자동 가입)
const googleLoginUrl = `/api/v1/auth/google/login?origin=${encodeURIComponent(window.location.origin)}`
const error = ref('')
const saving = ref(false)

const checked = reactive({ email: '', nickname: '' })
const checking = reactive({ email: false, nickname: false })
const duplicateMessage = reactive({ email: '', nickname: '' })
for (const field of ['email', 'nickname']) {
  watch(() => form[field], () => { checked[field] = ''; duplicateMessage[field] = '' })
}
async function checkDuplicate(field) {
  const value = form[field].trim()
  if (!value) { duplicateMessage[field] = field === 'email' ? '이메일을 입력해 주세요.' : '닉네임을 입력해 주세요.'; return false }
  if (field === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
    checked[field] = ''
    duplicateMessage[field] = '올바른 이메일 형식으로 입력해 주세요. (예: name@example.com)'
    return false
  }
  checking[field] = true
  try {
    const result = await (field === 'email' ? authApi.checkEmail(value) : authApi.checkNickname(value))
    if (form[field].trim() !== value) return false
    checked[field] = result.available ? value : ''
    duplicateMessage[field] = result.available ? '사용할 수 있습니다.' : '이미 사용 중입니다.'
    return result.available
  } catch (e) { duplicateMessage[field] = apiError(e); return false }
  finally { checking[field] = false }
}

function formatBirthDate(event) {
  const digits = event.target.value.replace(/\D/g, '').slice(0, 8)
  birthDate.value = [digits.slice(0, 4), digits.slice(4, 6), digits.slice(6, 8)].filter(Boolean).join('-')
  event.target.value = birthDate.value
}

async function submit() {
  error.value = ''
  if (form.password !== passwordConfirm.value) { error.value = '비밀번호 확인이 일치하지 않습니다.'; return }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(birthDate.value)) { error.value = '생년월일을 YYYY-MM-DD 형식으로 입력해 주세요.'; return }
  const birth = birthDate.value.replace(/-/g, '')
  const year = Number(birth.slice(0, 4)), month = Number(birth.slice(4, 6)), day = Number(birth.slice(6, 8))
  const date = new Date(year, month - 1, day)
  if (year < 1900 || date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day || date > new Date()) { error.value = '올바른 생년월일을 입력해 주세요.'; return }
  saving.value = true
  try {
    for (const field of ['email', 'nickname']) {
      if (checked[field] !== form[field].trim() && !await checkDuplicate(field)) return
    }
    // [백엔드 연동 수정] 백엔드는 password_confirm 을 함께 받아서 서버에서도 일치 여부를 검사합니다.
    await auth.register({ ...form, password_confirm: passwordConfirm.value, phone: form.phone || null, birth_date: `${birth.slice(0, 4)}-${birth.slice(4, 6)}-${birth.slice(6, 8)}` })
    await router.push({ name: 'login', query: { registered: '1' } })
  } catch (e) { error.value = apiError(e) }
  finally { saving.value = false }
}
</script>

<style scoped>
.signup-page .signup-panel{width:min(100%,820px)}
.signup-social{display:flex;flex-direction:column;align-items:center;gap:10px;margin:8px 0 18px}
.signup-google-button{box-sizing:border-box;display:flex;align-items:center;justify-content:center;gap:10px;width:100%;max-width:420px;min-height:52px;background:#fff;border:1.5px solid #d9d2e3;border-radius:14px;color:#2b2430;font:inherit;font-size:16px;font-weight:700;text-decoration:none;box-shadow:0 2px 6px rgba(60,40,90,.08);transition:background .15s,border-color .15s,box-shadow .15s}
.signup-google-button:hover{background:#faf8fd;border-color:#b9a6d6;box-shadow:0 4px 12px rgba(60,40,90,.12)}
.signup-google-button:focus-visible{outline:3px solid #bca4df;outline-offset:2px}
.signup-social .google-icon{width:22px;height:22px;flex:none}
.signup-social small{font-size:13px;color:#8a7f92;text-align:center;word-break:keep-all}
.signup-social-divider{display:flex;align-items:center;gap:12px;width:100%;margin-top:10px;color:#8b8090;font-size:13px}
.signup-social-divider::before,.signup-social-divider::after{content:'';flex:1;height:1px;background:#e6e0ec}
.signup-check-row{display:grid;grid-template-columns:minmax(0,1fr) 112px;align-items:stretch;gap:10px}
.signup-check-row .signup-check-button{display:flex;align-items:center;justify-content:center;height:46px;padding:0 16px;border:1px solid #d8c5ef;border-radius:8px;background:#f3edfb;color:#6841a4;font-size:14px;font-weight:600;white-space:nowrap;cursor:pointer;transition:background .15s,border-color .15s}
.signup-check-row .signup-check-button:hover:not(:disabled){background:#e9ddf8;border-color:#b59ad8}
.signup-check-row .signup-check-button:focus-visible{outline:2px solid #7953aa;outline-offset:3px}
.signup-check-row .signup-check-button:disabled{background:#f7f5f9;border-color:#e8e2ee;color:#a297ad;cursor:default}
.signup-row>div>.signup-check-result{margin-top:8px;font-size:13px;line-height:1.5}
.signup-row>div>.signup-check-result.is-available{color:#6841a4}
.signup-row>div>.signup-check-result.is-unavailable{color:#b44368}
@media(max-width:400px){.signup-check-row{grid-template-columns:minmax(0,1fr) 94px;gap:8px}.signup-check-row .signup-check-button{padding:0 10px;font-size:13px}}
</style>
