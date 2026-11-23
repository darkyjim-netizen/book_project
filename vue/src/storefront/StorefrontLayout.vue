<template>
  <div class="app">
    <Teleport to="head">
      <link v-for="sheet in stylesheets" :key="sheet" rel="stylesheet" :href="'/styles/storefront/' + sheet + '.css' + '?v=20261122-footer'" />
    </Teleport>
    <StorefrontHeader />
    <main class="content" :class="{ 'content-dashboard': ['adminDashboard', 'adminOrderDetail'].includes($route.name) }"><RouterView /></main>
    <footer class="footer storefront-footer">
      <div class="storefront-footer-grid">
        <div class="footer-brand"><RouterLink to="/main"><img src="/assets/bookjjeok-logo-new.png" alt="북적북적" /></RouterLink><p>책을 좋아하는 사람들을 위한 서점</p></div>
        <div class="footer-details">
        <p class="footer-copyright">© 2026 북적북적</p>
        <nav class="footer-inline-links" aria-label="이용 안내 및 고객지원"><RouterLink to="/terms">이용약관</RouterLink><RouterLink to="/privacy">개인정보처리방침</RouterLink><RouterLink v-for="item in supportLinks" :key="item.id" class="footer-support-link" :to="{ name: 'support', query: { tab: item.id } }">{{ item.label }}</RouterLink></nav>
        </div>
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
