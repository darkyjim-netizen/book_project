<template>
  <div class="app">
    <Teleport to="head">
      <link v-for="sheet in stylesheets" :key="sheet" rel="stylesheet" :href="'/styles/storefront/' + sheet + '.css'" />
    </Teleport>
    <StorefrontHeader />
    <main class="content" :class="{ 'content-dashboard': $route.name === 'adminDashboard' }"><RouterView /></main>
    <footer class="footer storefront-footer">
      <span>© 2026 북적북적 · 책을 좋아하는 사람들을 위한 서점</span>
      <nav class="footer-support" aria-label="고객지원 바로가기">
        <RouterLink v-for="item in supportLinks" :key="item.id" :to="{ name: 'support', query: { tab: item.id } }">{{ item.label }}</RouterLink>
      </nav>
      <nav class="footer-support" aria-label="약관 및 정책"><RouterLink to="/terms">이용약관</RouterLink><RouterLink to="/privacy">개인정보처리방침</RouterLink></nav>
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

const stylesheets = ['base', 'admin', 'checkout', 'discovery', 'curation', 'mypage', 'home', 'account-support'];
const supportLinks = [{ id: 'notices', label: '공지사항' }, { id: 'faq', label: 'FAQ' }, { id: 'qna', label: '1:1 문의' }, { id: 'chat', label: '상담채팅' }];
provide(storefrontKey, useStorefront());
</script>
