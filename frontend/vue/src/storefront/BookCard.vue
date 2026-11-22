<template>
    <article class="book-card" role="link" tabindex="0" @click="$emit('detail',book)" @keydown.enter.self="$emit('detail',book)" @keydown.space.prevent.self="$emit('detail',book)">
      <div class="book-art" :style="{background:book.bg}">
        <span v-if="rank != null" class="rank">{{ String(rank).padStart(2,'0') }}</span>
        <button v-if="auth.initialized && !auth.isAdmin" type="button" class="wish" :class="{on:wished}" @click.stop="$emit('wish',book)" :aria-pressed="wished" :aria-label="book.title + (wished?' 찜 해제':' 찜하기')">{{ wished?'♥':'♡' }}</button>
        <img v-if="bookCoverUrl(book)" class="book-cover-img" :src="bookCoverUrl(book)" :alt="book.isDatabaseBook && !book.cover_image ? '도서 분야 안내 이미지' : book.title + ' 표지'" @error="$event.target.onerror=null; $event.target.src='/assets/covers/category-default.png'; $event.target.alt='도서 분야 안내 이미지'" loading="lazy" />
        <span v-if="book.isDatabaseBook && !book.cover_image" class="cover-category-label">{{ book.major || book.cat }}</span>
        <div v-if="!bookCoverUrl(book)" class="book-cover" :style="{background:book.color}"><strong>{{ book.title }}</strong><small>{{ book.author }} 지음</small></div>
      </div>
      <div class="book-meta"><div class="category">{{ book.major||book.cat }}</div><h3>{{ book.title }}</h3><div class="author">{{ book.author }} · {{ book.publisher }}</div>
        <div class="price-line"><del v-if="book.discount" class="original-price">{{ Number(book.price).toLocaleString('ko-KR') }}원</del><span class="price">{{ Math.round(book.price*(1-(book.discount||0)/100)).toLocaleString('ko-KR') }}원</span><span v-if="book.discount" class="discount">{{ book.discount }}%</span></div>
        <div v-if="book.rate" class="rating">★ {{ book.rate }}<span>독자 평점</span></div><div v-else class="rating new-book-label">새로 추가된 책</div><div class="buy-row"><button @click.stop="$emit('detail',book)">상세</button><button @click.stop="$emit('buy',book)">담기</button></div>
      </div>
    </article>
</template>

<script setup>
import { bookCoverUrl } from './useStorefront.js';
import { useAuthStore } from '../stores/authStore.js';
const auth = useAuthStore();
defineProps({ book: { type: Object, required: true }, rank: Number, wished: Boolean });
defineEmits(['wish', 'buy', 'detail']);
</script>

<style scoped>
/* Let the artwork grow with the card width while preserving the entire cover. */
.book-card .book-art{display:flex;align-items:center;justify-content:center;box-sizing:border-box;padding:28px 0;min-width:0;min-height:0;height:auto!important;aspect-ratio:auto;overflow:hidden;border-radius:8px}
.book-card .book-art .book-cover-img{display:block;width:62%;height:auto!important;aspect-ratio:2 / 3;max-width:100%!important;max-height:none;min-width:0;min-height:0;object-fit:contain;object-position:center;flex:0 1 auto;box-sizing:border-box;box-shadow:0 8px 20px rgba(0,0,0,.15);border-radius:4px;filter:none}
/* Move the whole card so the cover does not animate independently. */
.book-card{transition:transform .2s ease,box-shadow .2s ease}
@media(hover:hover) and (pointer:fine){
  .book-card:hover{transform:translateY(-4px);box-shadow:0 12px 28px rgba(0,0,0,.08)}
}
.book-card:focus-visible{transform:translateY(-4px);box-shadow:0 12px 28px rgba(0,0,0,.08)}
.book-card:hover .book-art .book-cover-img,.book-card:hover .book-art .book-cover{transform:none}
@media(prefers-reduced-motion:reduce){.book-card{transition:none}.book-card:hover,.book-card:focus-visible{transform:none}}
.book-card .book-art .book-cover{box-sizing:border-box;width:62%;height:auto;aspect-ratio:2 / 3;max-width:100%;border-radius:4px;box-shadow:0 8px 20px rgba(0,0,0,.15)}
@media(max-width:600px){.book-card .book-art{padding:22px 0}}
</style>
