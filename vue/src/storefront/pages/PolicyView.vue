<template>
  <section class="account-support support-page policy-page">
    <header><h1>{{ title }}</h1></header>
    <div class="as-card"><p>{{ title }} 내용을 준비 중입니다.</p></div>
  </section>
</template>

<script setup>
import { computed } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();
const title = computed(() => route.name === 'privacy' ? '개인정보처리방침' : '이용약관');
</script>
