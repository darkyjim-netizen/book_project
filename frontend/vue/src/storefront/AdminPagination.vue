<template>
  <nav v-if="pages > 1" class="admin-pagination" aria-label="목록 페이지">
    <button :disabled="start <= 1" aria-label="이전 5페이지" @click="$emit('change', Math.max(1, start - 5))">«</button>
    <button :disabled="page <= 1" @click="$emit('change', page - 1)">이전</button>
    <button v-for="number in numbers" :key="number" :aria-current="number === page ? 'page' : null" :aria-label="`${number}페이지`" @click="$emit('change', number)">{{ number }}</button>
    <button :disabled="page >= pages" @click="$emit('change', page + 1)">다음</button>
    <button :disabled="start + 5 > pages" aria-label="다음 5페이지" @click="$emit('change', start + 5)">»</button>
  </nav>
</template>
<script setup>
import { computed } from 'vue';
const props = defineProps({ page: { type: Number, required: true }, pages: { type: Number, required: true } });
defineEmits(['change']);
const start = computed(() => Math.floor((props.page - 1) / 5) * 5 + 1);
const numbers = computed(() => Array.from({length: Math.min(5, props.pages - start.value + 1)}, (_, i) => start.value + i));
</script>
<style scoped>
.admin-pagination{display:flex;align-items:center;justify-content:center;flex-wrap:wrap;gap:8px;margin:28px 0;font-size:17px}.admin-pagination button{min-width:42px;min-height:42px;padding:8px 12px;border:1px solid #ded3ea;border-radius:8px;background:white;color:#51316e;font:inherit;cursor:pointer}.admin-pagination button[aria-current=page]{background:#65419a;border-color:#65419a;color:white;font-weight:700}.admin-pagination button:disabled{opacity:.4;cursor:default}.admin-pagination button:focus-visible{outline:2px solid #7952a2;outline-offset:3px}@media(max-width:600px){.admin-pagination{gap:4px;font-size:15px}.admin-pagination button{min-width:34px;padding:6px;min-height:38px}}
</style>
