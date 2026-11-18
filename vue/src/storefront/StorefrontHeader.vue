<template>
<div class="site-top">
  <div class="topline"><p>책 읽는 즐거움, 오늘도 한권 가까이</p><b>회원가입 시 할인 쿠폰 증정</b></div>
  <header class="header storefront-header">
    <a class="brand" href="/main" aria-label="북적북적 홈" @click.prevent="navigate('home')"><img class="brand-logo" src="/assets/bookjjeok-logo-new.png" alt="" /></a>
    <StorefrontSearch />
    <div class="head-actions">
      <button type="button" class="icon-btn" :aria-label="'장바구니 ' + cart.length + '종'" @click="navigate('cart')"><span aria-hidden="true">🛒<span v-if="cart.length" class="badge">{{ cart.length }}</span></span><small>장바구니</small></button>
      <button type="button" class="icon-btn" aria-label="마이페이지" @click="navigate('mypage')"><span aria-hidden="true">👤</span><small>마이페이지</small></button>
      <button v-if="auth.initialized && auth.isAuthenticated" type="button" class="icon-btn" aria-label="로그아웃" @click="signOut"><span aria-hidden="true">↪</span><small>로그아웃</small></button>
      <a v-if="auth.initialized && auth.isAdmin" class="icon-btn" href="/store-admin/dashboard" aria-label="관리자 대시보드"><span aria-hidden="true">🧑</span><small>관리자</small></a>
      <a v-else-if="auth.initialized && !auth.isAuthenticated" class="icon-btn" href="/login" aria-label="로그인"><span aria-hidden="true">♙</span><small>로그인</small></a>
    </div>
    <nav class="nav" aria-label="주요 메뉴">
      <details ref="headerCategoryMenu" class="header-category-menu"
        @keydown.esc.stop="closeHeaderCategoryMenu(true)"
        @focusout="closeHeaderCategoryMenuOnBlur">
        <summary aria-label="도서 분야" title="도서 분야"><span class="header-category-icon" aria-hidden="true"><span></span></span></summary>
        <div class="header-category-panel" aria-labelledby="header-category-title" role="group">
          <h2 id="header-category-title">국내도서</h2>
          <button type="button" @click="closeHeaderCategoryMenu(); openBestSellers()">베스트셀러</button>
          <button v-for="category in domesticCategories" :key="category.name" type="button"
            :aria-current="view === 'domestic' && activeDomesticCategory === category.name ? 'true' : null"
            @click="selectHeaderCategory(category.name)">{{ category.name }}</button>
        </div>
      </details>
      <a href="/domestic" :class="{active:view==='domestic'||view==='category'}" @click.prevent="navigate('domestic')">국내도서</a>
      <a href="/curation" :class="{active:view==='curation'}" @click.prevent="navigate('curation')">추천도서</a>
      <a v-if="auth.initialized && !auth.isAuthenticated" href="/guest-order" :class="{active:view==='guestOrder'}" @click.prevent="navigate('guestOrder')">비회원 주문조회</a>
      <a href="/support" :class="{active:view==='support'}" @click.prevent="navigate('support')">고객지원</a>
      <a href="/bestsellers" :class="{active:view==='bestsellers'}" @click.prevent="openBestSellers">베스트셀러</a>
    </nav>
  </header>
  </div>
</template>

<script>
import { onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../stores/authStore.js';
import { useStorefrontContext } from './context.js';
import StorefrontSearch from './StorefrontSearch.vue';
export default {
  components: { StorefrontSearch },
  setup() {
    const auth = useAuthStore();
    const router = useRouter();
    async function signOut() {
      if (!window.confirm('로그아웃 하시겠습니까?')) return;
      try { await auth.logout(); } finally { await router.push('/login'); }
    }
    onMounted(() => { if (!auth.initialized) auth.fetchMe(); });
    return { ...useStorefrontContext(), auth, signOut };
  },
};
</script>
