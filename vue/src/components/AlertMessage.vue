<template>
  <div v-if="message" class="whitespace-pre-line rounded-xl border px-4 py-3 text-sm"
       :class="type === 'error' ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'">
    {{ message }}
  </div>
</template>
<script setup>
defineProps({ message: { type: String, default: '' }, type: { type: String, default: 'error' } })
</script>