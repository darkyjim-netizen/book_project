<template>
<section class="admin-shell"><div class="signup-panel"><button class="signup-back" @click="navigate('adminLogin')">← 로그인으로</button><h1>회원가입</h1><p class="signup-intro">가입에 필요한 정보를 입력해 주세요.</p><form class="signup-form" @submit.prevent="adminSignup"><label for="admin-signup-id">아이디</label><input id="admin-signup-id" v-model.trim="signupForm.id" autocomplete="username" required minlength="4" placeholder="아이디" /><label for="admin-signup-password">비밀번호</label><input id="admin-signup-password" v-model="signupForm.password" type="password" autocomplete="new-password" required minlength="8" placeholder="비밀번호 (8자 이상)" /><label for="admin-signup-name">이름</label><input id="admin-signup-name" v-model.trim="signupForm.name" autocomplete="name" required placeholder="이름" /><label for="admin-signup-phone">전화번호</label><input id="admin-signup-phone" v-model.trim="signupForm.phone" type="tel" autocomplete="tel" required placeholder="전화번호" /><label for="admin-signup-email">이메일</label><input id="admin-signup-email" v-model.trim="signupForm.email" type="email" autocomplete="email" required placeholder="이메일" /><label class="consent-row"><input v-model="signupConsent" type="checkbox" /><span>동의합니다</span></label><p v-if="signupError" class="login-error" role="alert">{{ signupError }}</p><button class="login-button signup-submit" type="submit" :disabled="!signupConsent">가입하기</button></form></div></section>
</template>

<script>
import { useStorefrontContext } from '../context.js';

export default { setup: useStorefrontContext };
</script>
