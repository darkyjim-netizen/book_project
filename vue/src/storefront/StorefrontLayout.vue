<template>
  <div class="app">
    <Teleport to="head">
      <link v-for="sheet in stylesheets" :key="sheet" rel="stylesheet" :href="'/styles/storefront/' + sheet + '.css'" />
    </Teleport>
    <StorefrontHeader />
    <main class="content" :class="{ 'content-dashboard': $route.name === 'adminDashboard' }"><RouterView /></main>
    <footer class="footer"><span>© 2026 북적북적 · 책을 좋아하는 사람들을 위한 서점</span><span>이용약관&nbsp;&nbsp; 개인정보처리방침&nbsp;&nbsp;</span></footer>
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
provide(storefrontKey, useStorefront());
</script>
