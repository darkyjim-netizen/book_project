<template>
<section class="admin-shell"><div class="login-panel" aria-labelledby="admin-login-heading"><img class="login-logo" src="/assets/bookjjeok-logo-new.png" alt="북적북적 로고" /><h1 id="admin-login-heading" class="sr-only">관리자 로그인</h1><form class="login-form" @submit.prevent="adminLogin"><input v-model.trim="adminUserId" autocomplete="username" placeholder="아이디" aria-label="아이디" required /><div class="password-field"><input v-model="adminPassword" :type="showAdminPassword?'text':'password'" autocomplete="current-password" placeholder="비밀번호" aria-label="비밀번호" required /><button class="eye-button" type="button" @click="showAdminPassword=!showAdminPassword" :aria-label="showAdminPassword?'비밀번호 숨기기':'비밀번호 보기'">◉</button></div><label class="remember-row"><input v-model="rememberAdminId" type="checkbox" /><span>아이디 저장</span></label><button class="login-button" type="submit">로그인</button><p v-if="adminLoginError" class="login-error" role="alert">{{ adminLoginError }}</p></form><nav class="account-links"><button @click="navigate('adminSignup')">회원가입</button><span></span><button @click="showToast('아이디 찾기는 준비 중입니다.')">아이디 찾기</button><span></span><button @click="showToast('비밀번호 찾기는 준비 중입니다.')">비밀번호 찾기</button></nav><p v-if="toastMessage" class="notice" role="status">{{ toastMessage }}</p><button class="admin-back-link" @click="navigate('home')">← 쇼핑몰로 돌아가기</button></div></section>
</template>

<script>
import { useStorefrontContext } from '../context.js';

export default { setup: useStorefrontContext };
</script>
