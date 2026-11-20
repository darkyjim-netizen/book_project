<template>
  <div class="app">
    <Teleport to="head">
      <link v-for="sheet in stylesheets" :key="sheet" rel="stylesheet" :href="'/styles/storefront/' + sheet + '.css' + (sheet === 'home' ? '?v=header-alignment-20261120' : '')" />
    </Teleport>
    <StorefrontHeader />
    <main class="content" :class="{ 'content-dashboard': ['adminDashboard', 'adminOrderDetail'].includes($route.name) }"><RouterView /></main>
    <footer class="footer storefront-footer">
      <div class="storefront-footer-grid">
        <div class="footer-brand"><RouterLink to="/main"><img src="/assets/bookjjeok-logo-new.png" alt="북적북적" /></RouterLink><p>책을 좋아하는 사람들을 위한 서점</p><p class="footer-copyright">© 2026 북적북적</p></div>
        <nav class="footer-support" aria-label="고객지원 바로가기"><strong>고객지원</strong><RouterLink v-for="item in supportLinks" :key="item.id" :to="{ name: 'support', query: { tab: item.id } }">{{ item.label }}</RouterLink></nav>
        <nav class="footer-support" aria-label="약관 및 정책"><strong>이용 안내</strong><RouterLink to="/terms">이용약관</RouterLink><RouterLink to="/privacy">개인정보처리방침</RouterLink></nav>
      </div>
    </footer>
    <StorefrontOverlays />
  </div>
</template>

<script setup>
import { provide } from 'vue';
import StorefrontHeader from './StorefrontHeader.vue';
import StorefrontOverlays from './StorefrontOverlays.vue';
import { storefrontKey } from './context.js';
import { useStorefront } from './useStorefront.js';
import './member-polish.css';

const stylesheets = ['base', 'admin', 'checkout', 'discovery', 'curation', 'mypage', 'home', 'account-support'];
const supportLinks = [{ id: 'notices', label: '공지사항' }, { id: 'faq', label: 'FAQ' }, { id: 'qna', label: '1:1 문의' }];
provide(storefrontKey, useStorefront());
</script>
